from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from services.column_mapper import recommend_field_mapping, recommend_key_columns
from services.duplicate_detector import find_duplicates
from services.exporter import build_export_workbook
from services.file_loader import list_sheets, read_dataframe
from services.fuzzy_matcher import build_fuzzy_matches
from services.match_engine import reconcile_dataframes
from services.report_generator import generate_report


st.set_page_config(page_title="Excel 智能核对助手", page_icon="📊", layout="wide")
st.title("📊 Excel 智能核对与查询助手")
st.caption("上传两份 Excel / CSV，快速完成匹配、查重、缺失检测、差异分析和结果导出。")


def _render_preview(label: str, dataframe: pd.DataFrame) -> None:
    st.subheader(label)
    st.caption(f"共 {len(dataframe)} 行，{len(dataframe.columns)} 列")
    st.dataframe(dataframe.head(20), use_container_width=True, hide_index=True)


project_root = Path(__file__).parent
sample_a = project_root / "sample_data" / "customers.csv"
sample_b = project_root / "sample_data" / "orders.csv"
source_mode = st.radio("数据来源", options=["上传文件", "示例数据"], horizontal=True)

if source_mode == "示例数据":
    source_a = sample_a
    source_b = sample_b
    st.success("已切换到内置示例数据，可直接点击“开始核对”。")
else:
    source_a = st.file_uploader("上传文件 A", type=["csv", "xlsx", "xls"], key="file_a")
    source_b = st.file_uploader("上传文件 B", type=["csv", "xlsx", "xls"], key="file_b")
    if not source_a or not source_b:
        st.info("请先上传两份文件，或切换到“示例数据”快速体验。")
        st.stop()

try:
    sheets_a = list_sheets(source_a)
    sheets_b = list_sheets(source_b)
except Exception as exc:  # pragma: no cover - Streamlit 交互
    st.error(f"读取文件结构失败：{exc}")
    st.stop()

col_sheet_a, col_sheet_b = st.columns(2)
with col_sheet_a:
    selected_sheet_a = st.selectbox("文件 A 的 Sheet", options=sheets_a, index=0)
with col_sheet_b:
    selected_sheet_b = st.selectbox("文件 B 的 Sheet", options=sheets_b, index=0)

try:
    df_a = read_dataframe(source_a, selected_sheet_a)
    df_b = read_dataframe(source_b, selected_sheet_b)
except Exception as exc:  # pragma: no cover - Streamlit 交互
    st.error(f"读取数据失败：{exc}")
    st.stop()

preview_left, preview_right = st.columns(2)
with preview_left:
    _render_preview("文件 A 预览", df_a)
with preview_right:
    _render_preview("文件 B 预览", df_b)

st.divider()
st.subheader("字段映射")

key_recommendations = recommend_key_columns(df_a.columns.tolist(), df_b.columns.tolist())
default_key_a = key_recommendations[0][0] if key_recommendations else df_a.columns[0]
default_key_b = key_recommendations[0][1] if key_recommendations else df_b.columns[0]

col_key_a, col_key_b, col_threshold = st.columns([1, 1, 1])
with col_key_a:
    key_a = st.selectbox(
        "A 表主匹配列",
        options=df_a.columns.tolist(),
        index=df_a.columns.tolist().index(default_key_a) if default_key_a in df_a.columns else 0,
    )
with col_key_b:
    key_b = st.selectbox(
        "B 表主匹配列",
        options=df_b.columns.tolist(),
        index=df_b.columns.tolist().index(default_key_b) if default_key_b in df_b.columns else 0,
    )
with col_threshold:
    fuzzy_threshold = st.slider("模糊匹配阈值", min_value=60, max_value=100, value=86)

recommended_pairs = [pair for pair in recommend_field_mapping(df_a.columns.tolist(), df_b.columns.tolist()) if pair[0] != key_a and pair[1] != key_b]
if recommended_pairs:
    tips = "；".join(f"{left} ↔ {right}（{score}）" for left, right, score, _ in recommended_pairs[:5])
    st.caption(f"推荐字段映射：{tips}")

max_pairs = max(1, min(6, len(df_a.columns), len(df_b.columns)))
pair_count = st.number_input("需要比对的字段对数量", min_value=1, max_value=max_pairs, value=min(3, max_pairs), step=1)

compare_pairs: list[tuple[str, str]] = []
for index in range(int(pair_count)):
    default_left = recommended_pairs[index][0] if index < len(recommended_pairs) else df_a.columns[index % len(df_a.columns)]
    default_right = recommended_pairs[index][1] if index < len(recommended_pairs) else df_b.columns[index % len(df_b.columns)]
    left_col, right_col = st.columns(2)
    with left_col:
        selected_left = st.selectbox(
            f"字段对 {index + 1} - A 表字段",
            options=df_a.columns.tolist(),
            index=df_a.columns.tolist().index(default_left) if default_left in df_a.columns else 0,
            key=f"left_field_{index}",
        )
    with right_col:
        selected_right = st.selectbox(
            f"字段对 {index + 1} - B 表字段",
            options=df_b.columns.tolist(),
            index=df_b.columns.tolist().index(default_right) if default_right in df_b.columns else 0,
            key=f"right_field_{index}",
        )
    compare_pairs.append((selected_left, selected_right))

if st.button("开始核对", type="primary", use_container_width=True):
    with st.spinner("正在分析数据，请稍候..."):
        results = reconcile_dataframes(df_a, df_b, key_a, key_b, compare_pairs)
        duplicates_a = find_duplicates(df_a, key_a)
        duplicates_b = find_duplicates(df_b, key_b)
        fuzzy_matches = build_fuzzy_matches(
            results["missing_in_b"],
            results["missing_in_a"],
            key_a,
            key_b,
            score_threshold=fuzzy_threshold,
        )
        report_text = generate_report(
            stats=results["stats"],
            compare_pairs=compare_pairs,
            duplicates_a_count=len(duplicates_a),
            duplicates_b_count=len(duplicates_b),
            fuzzy_count=len(fuzzy_matches),
        )
        workbook = build_export_workbook(results, duplicates_a, duplicates_b, fuzzy_matches, report_text)
        st.session_state["excel_reconcile_result"] = {
            "results": results,
            "duplicates_a": duplicates_a,
            "duplicates_b": duplicates_b,
            "fuzzy_matches": fuzzy_matches,
            "report_text": report_text,
            "workbook": workbook,
        }

result_bundle = st.session_state.get("excel_reconcile_result")
if not result_bundle:
    st.stop()

results = result_bundle["results"]
duplicates_a = result_bundle["duplicates_a"]
duplicates_b = result_bundle["duplicates_b"]
fuzzy_matches = result_bundle["fuzzy_matches"]
report_text = result_bundle["report_text"]

st.divider()
st.subheader("核对结果总览")
metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)
stats = results["stats"]
metric_1.metric("A 表记录数", stats["left_rows"])
metric_2.metric("B 表记录数", stats["right_rows"])
metric_3.metric("完全匹配", stats["exact_match_rows"])
metric_4.metric("字段不一致", stats["mismatch_rows"])
metric_5.metric("模糊候选", len(fuzzy_matches))

tabs = st.tabs(
    [
        "匹配结果",
        "完全匹配",
        "A 表缺失于 B",
        "B 表缺失于 A",
        "差异明细",
        "重复记录",
        "模糊匹配",
        "核对报告",
    ]
)

with tabs[0]:
    st.dataframe(results["matched_records"], use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(results["exact_matches"], use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(results["missing_in_b"], use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(results["missing_in_a"], use_container_width=True, hide_index=True)
with tabs[4]:
    st.dataframe(results["mismatch_details"], use_container_width=True, hide_index=True)
with tabs[5]:
    left_dup, right_dup = st.columns(2)
    with left_dup:
        st.caption("A 表重复记录")
        st.dataframe(duplicates_a, use_container_width=True, hide_index=True)
    with right_dup:
        st.caption("B 表重复记录")
        st.dataframe(duplicates_b, use_container_width=True, hide_index=True)
with tabs[6]:
    st.dataframe(fuzzy_matches, use_container_width=True, hide_index=True)
with tabs[7]:
    st.code(report_text, language="text")
    st.download_button(
        label="下载核对结果工作簿",
        data=result_bundle["workbook"],
        file_name="excel_reconcile_result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
