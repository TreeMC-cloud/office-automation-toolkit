# 📊 自动报表生成机器人

导入 CSV/Excel 数据，自动清洗、计算指标、生成带图表的报告，支持飞书/邮件通知推送。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 功能特性

- **数据导入** — 支持 CSV、Excel 文件导入
- **自动清洗** — 缺失值处理、数据类型转换
- **指标计算** — 总量、均值、趋势等多维度聚合分析
- **图表生成** — 基于 Matplotlib 自动生成可视化图表
- **报告输出** — HTML 报告（Jinja2 模板渲染）+ Excel 报告
- **AI 摘要** — 自动生成数据分析摘要
- **通知推送** — 飞书 Webhook + 邮件 SMTP 通知

## 快速开始

```bash
pip install -r requirements.txt
python desktop_app.py
```

## 项目结构

```
├── desktop_app.py              # 桌面 GUI 主入口
├── services/
│   ├── file_ingestion.py       # 文件导入
│   ├── cleaner.py              # 数据清洗
│   ├── metrics.py              # 指标计算
│   ├── chart_builder.py        # 图表生成
│   ├── report_renderer.py      # 报告渲染
│   ├── exporter.py             # 导出
│   └── notifier.py             # 通知推送
├── utils/
│   └── ai_summary.py           # AI 摘要
└── requirements.txt
```
