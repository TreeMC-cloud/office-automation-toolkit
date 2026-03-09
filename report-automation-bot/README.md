# Report Automation Bot

一个面向办公自动化的自动报表生成与通知机器人，支持多源 Excel / CSV 合并、指标计算、趋势分析、图表输出、HTML 报告生成以及邮件 / 飞书通知。

## 功能特性
- 上传多份 Excel / CSV 并自动合并数据
- 选择日期列、指标列、维度列生成日报 / 周报
- 自动计算总量、均值、最新趋势、分组 Top N
- 生成 HTML 报告与 Excel 工作簿
- 支持邮件发送和飞书 Webhook 推送
- 内置样例数据，可直接体验完整流程

## 技术栈
- Python
- Streamlit
- pandas
- Jinja2
- matplotlib

## 快速开始
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 样例数据
`sample_data/` 目录内提供三份业务数据，可直接用于生成日报或周报：
- `sales_north.csv`
- `sales_east.csv`
- `sales_online.csv`
