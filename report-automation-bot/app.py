from __future__ import annotations

from pathlib import Path

import streamlit as st

from services.chart_builder import build_bar_chart_base64, build_line_chart_base64
from services.cleaner import coerce_dataframe, detect_numeric_columns
from services.exporter import build_report_workbook
from services.file_ingestion import load_uploaded_files
from services.metrics import aggregate_by_dimension, aggregate_by_period, compute_overview
from services.notifier import build_notification_text, send_email, send_feishu
from services.report_renderer import render_html_report
from utils.ai_summary import generate_summary


st.set_page_config(page_title="自动报表机器人", page_icon="📬", layout="wide")
st.title("📬 自动报表生成与通知机器人")
st.caption("上传多份 Excel / CSV，自动生成趋势分析、HTML 报告和消息通知。")

project_root = Path(__file__).parent
sample_dir = project_root / "sample_data"
source_mode = st.radio("数据来源", options=["上传文件", "示例数据"], horizontal=True)

if source_mode == "示例数据":
    uploaded_files = sorted(sample_dir.glob("*.csv"))
    st.success("已载入内置样例数据，可直接点击“生成报表”。")
else:
    uploaded_files = st.file_uploader(
        "上传多个数据文件",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
    )

if not uploaded_files:
    st.info("请先上传文件，或切换到“示例数据”快速体验。")
    st.stop()

dataframe = load_uploaded_files(list(uploaded_files))
st.subheader("数据预览")
st.dataframe(dataframe.head(20), use_container_width=True, hide_index=True)

date_candidates = dataframe.columns.tolist()
numeric_candidates = detect_numeric_columns(dataframe)
dimension_candidates = [column for column in dataframe.columns if column not in numeric_candidates and column != "__source_file"]

config_left, config_mid, config_right = st.columns(3)
with config_left:
    date_column = st.selectbox("日期列", options=date_candidates, index=date_candidates.index("日期") if "日期" in date_candidates else 0)
    value_column = st.selectbox(
        "指标列",
        options=numeric_candidates or date_candidates,
        index=(numeric_candidates.index("销售额") if "销售额" in numeric_candidates else 0) if numeric_candidates else 0,
    )
with config_mid:
    dimension_column = st.selectbox(
        "维度列",
        options=["(不选择)"] + dimension_candidates,
        index=1 if len(dimension_candidates) >= 1 else 0,
    )
    frequency = st.selectbox("趋势粒度", options=[("D", "按天"), ("W", "按周"), ("M", "按月")], format_func=lambda item: item[1])
with config_right:
    top_n = st.slider("维度 Top N", min_value=3, max_value=10, value=5)

if st.button("生成报表", type="primary", use_container_width=True):
    with st.spinner("正在生成报表..."):
        cleaned = coerce_dataframe(dataframe, date_column=date_column, numeric_columns=[value_column])
        dimension_name = None if dimension_column == "(不选择)" else dimension_column
        overview = compute_overview(cleaned, date_column=date_column, value_column=value_column)
        trend_df = aggregate_by_period(cleaned, date_column=date_column, value_column=value_column, freq=frequency[0])
        dimension_df = aggregate_by_dimension(cleaned, dimension_column=dimension_name, value_column=value_column, top_n=top_n)
        summary_text = generate_summary(
            overview=overview,
            trend_df=trend_df,
            dimension_df=dimension_df,
            value_label=value_column,
            dimension_label=dimension_name or "维度",
        )
        trend_chart = build_line_chart_base64(trend_df, x_column="period", y_column=value_column, title=f"{value_column} 趋势")
        dimension_chart = build_bar_chart_base64(dimension_df, x_column=dimension_name or "dimension", y_column=value_column, title=f"{value_column} Top 分布") if not dimension_df.empty else ""
        template_path = Path(__file__).parent / "templates" / "report.html"
        html_report = render_html_report(
            template_path=template_path,
            context={
                "title": f"{value_column} 自动分析报告",
                "overview": overview,
                "summary_text": summary_text,
                "trend_records": trend_df.to_dict(orient="records"),
                "dimension_records": dimension_df.to_dict(orient="records"),
                "preview_records": cleaned.head(10).to_dict(orient="records"),
                "trend_chart": trend_chart,
                "dimension_chart": dimension_chart,
                "value_label": value_column,
                "dimension_label": dimension_name or "维度",
            },
        )
        workbook = build_report_workbook(cleaned, overview, trend_df, dimension_df, summary_text)
        st.session_state["report_bot_result"] = {
            "overview": overview,
            "trend_df": trend_df,
            "dimension_df": dimension_df,
            "summary_text": summary_text,
            "html_report": html_report,
            "workbook": workbook,
        }

result_bundle = st.session_state.get("report_bot_result")
if not result_bundle:
    st.stop()

overview = result_bundle["overview"]
trend_df = result_bundle["trend_df"]
dimension_df = result_bundle["dimension_df"]
summary_text = result_bundle["summary_text"]

metric_1, metric_2, metric_3, metric_4 = st.columns(4)
metric_1.metric("总记录数", overview["total_records"])
metric_2.metric("总指标值", overview["total_value"])
metric_3.metric("均值", overview["average_value"])
metric_4.metric("最新周期值", overview["latest_period_value"])

tab_1, tab_2, tab_3 = st.tabs(["趋势与维度", "摘要与导出", "通知发送"])
with tab_1:
    st.subheader("趋势数据")
    st.line_chart(trend_df.set_index("period"))
    if not dimension_df.empty:
        st.subheader("维度 Top N")
        st.bar_chart(dimension_df.set_index(dimension_df.columns[0]))
    st.dataframe(trend_df, use_container_width=True, hide_index=True)
    if not dimension_df.empty:
        st.dataframe(dimension_df, use_container_width=True, hide_index=True)
with tab_2:
    st.code(summary_text, language="text")
    st.download_button(
        label="下载 HTML 报告",
        data=result_bundle["html_report"].encode("utf-8"),
        file_name="report.html",
        mime="text/html",
        use_container_width=True,
    )
    st.download_button(
        label="下载 Excel 报表工作簿",
        data=result_bundle["workbook"],
        file_name="report_workbook.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
with tab_3:
    notification_text = build_notification_text(summary_text, overview)
    webhook_url = st.text_input("飞书 Webhook（可选）")
    with st.expander("邮件发送（可选）"):
        smtp_server = st.text_input("SMTP 服务器", value="smtp.qq.com")
        smtp_port = st.number_input("SMTP 端口", min_value=1, max_value=65535, value=465)
        sender = st.text_input("发件邮箱")
        password = st.text_input("邮箱授权码 / 密码", type="password")
        recipients = st.text_input("收件人，多个用逗号分隔")
    if st.button("发送通知", use_container_width=True):
        messages = []
        if webhook_url:
            response_text = send_feishu(webhook_url, notification_text)
            messages.append(f"飞书发送完成：{response_text}")
        if sender and password and recipients:
            send_email(
                smtp_server=smtp_server,
                smtp_port=int(smtp_port),
                sender=sender,
                password=password,
                recipients=[item.strip() for item in recipients.split(",") if item.strip()],
                subject="自动报表通知",
                html_body=result_bundle["html_report"],
            )
            messages.append("邮件发送完成")
        if messages:
            st.success("；".join(messages))
        else:
            st.warning("未填写通知配置，本次仅展示通知预览。")
    st.code(notification_text, language="text")
