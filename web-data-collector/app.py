from __future__ import annotations

from pathlib import Path

import streamlit as st

from crawlers.detail_crawler import enrich_with_detail
from crawlers.list_crawler import extract_list_items
from services.cleaner import deduplicate_records
from services.exporter import build_export_workbook
from services.extractor import records_to_dataframe
from services.http_client import fetch_html
from utils.ai_tagger import tag_records


st.set_page_config(page_title="网页信息采集平台", page_icon="🕸️", layout="wide")
st.title("🕸️ 网页信息采集与结构化导出平台")
st.caption("支持公开网页和本地 HTML 演示站点的列表抓取、详情页抽取、标签提取与 Excel 导出。")

project_root = Path(__file__).parent
demo_root = project_root / "sample_data" / "demo_pages"
demo_source = demo_root / "jobs_list.html"

mode = st.radio("数据源模式", options=["演示站点", "公开网页"], horizontal=True)

if mode == "演示站点":
    source = str(demo_source)
    base_url = ""
    local_base_dir = demo_root
    st.info("当前使用内置招聘演示站点，无需联网即可完整演示抓取流程。")
    default_item_selector = ".job-card"
    default_title_selector = ".job-title a"
    default_link_selector = ".job-title a"
    default_summary_selector = ".job-summary"
    default_date_selector = ".publish-date"
    default_content_selector = ".job-description"
    default_company_selector = ".job-company"
    default_location_selector = ".job-location"
else:
    source = st.text_input("起始 URL", placeholder="https://example.com/jobs")
    base_url = source
    local_base_dir = None
    default_item_selector = "article"
    default_title_selector = "h2 a"
    default_link_selector = "h2 a"
    default_summary_selector = "p"
    default_date_selector = ".date"
    default_content_selector = ".content"
    default_company_selector = ".company"
    default_location_selector = ".location"

with st.expander("解析配置", expanded=True):
    col_1, col_2, col_3 = st.columns(3)
    with col_1:
        item_selector = st.text_input("列表项选择器", value=default_item_selector)
        title_selector = st.text_input("标题选择器", value=default_title_selector)
        link_selector = st.text_input("链接选择器", value=default_link_selector)
    with col_2:
        summary_selector = st.text_input("摘要选择器", value=default_summary_selector)
        date_selector = st.text_input("日期选择器", value=default_date_selector)
        content_selector = st.text_input("详情正文选择器", value=default_content_selector)
    with col_3:
        company_selector = st.text_input("公司选择器", value=default_company_selector)
        location_selector = st.text_input("地点选择器", value=default_location_selector)
        max_items = st.slider("最大抓取条数", min_value=1, max_value=20, value=10)

if st.button("开始采集", type="primary", use_container_width=True):
    with st.spinner("正在抓取并解析页面..."):
        html = fetch_html(source)
        list_records = extract_list_items(
            html=html,
            item_selector=item_selector,
            title_selector=title_selector,
            link_selector=link_selector,
            summary_selector=summary_selector,
            date_selector=date_selector,
            base_url=base_url,
            local_base_dir=local_base_dir,
        )[:max_items]
        enriched = enrich_with_detail(
            records=list_records,
            content_selector=content_selector,
            company_selector=company_selector,
            location_selector=location_selector,
            base_url=base_url,
            local_base_dir=local_base_dir,
        )
        cleaned = deduplicate_records(enriched)
        tagged = tag_records(cleaned)
        dataframe = records_to_dataframe(tagged)
        workbook = build_export_workbook(dataframe)
        st.session_state["web_collector_result"] = {
            "records": tagged,
            "dataframe": dataframe,
            "workbook": workbook,
        }

result_bundle = st.session_state.get("web_collector_result")
if not result_bundle:
    st.stop()

dataframe = result_bundle["dataframe"]
high_priority = int((dataframe["priority"] == "高").sum()) if not dataframe.empty else 0
unique_companies = dataframe["company"].nunique() if "company" in dataframe.columns else 0
unique_categories = dataframe["category"].nunique() if "category" in dataframe.columns else 0

metric_1, metric_2, metric_3 = st.columns(3)
metric_1.metric("抓取记录数", len(dataframe))
metric_2.metric("高优先级信息", high_priority)
metric_3.metric("公司 / 机构数", unique_companies)
st.caption(f"已识别类别数：{unique_categories}")

tab_1, tab_2 = st.tabs(["采集结果", "导出"])
with tab_1:
    st.dataframe(dataframe, use_container_width=True, hide_index=True)
with tab_2:
    st.download_button(
        label="下载采集结果工作簿",
        data=result_bundle["workbook"],
        file_name="web_data_collector_result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
