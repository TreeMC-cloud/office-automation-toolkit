# Web Data Collector

一个面向办公自动化的数据采集工具，支持从公开网页或本地 HTML 演示站点中抓取列表信息、追踪详情页内容、做结构化清洗与标签提取，并导出 Excel / CSV。

## 功能特性
- 支持公开网页 URL 或本地演示 HTML 抓取
- 支持自定义 CSS Selector 解析列表页
- 可追踪详情页正文、公司、地点等字段
- 自动去重、清洗、提取关键标签
- 生成优先级、类别、城市等结构化结果
- 一键导出 Excel / CSV

## 演示模式
项目内置 `sample_data/demo_pages/`，无需联网即可体验招聘信息抓取流程。

## 适用场景
- 招聘信息采集
- 招标公告整理
- 商品信息抽取
- 行业名单收集

## 技术栈
- Python
- Streamlit
- requests
- BeautifulSoup
- pandas

## 快速开始
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 合规提醒
- 仅建议抓取公开可访问页面
- 需遵守网站 robots、使用条款和访问频率限制
- 不应用于未授权或侵犯隐私的数据采集
