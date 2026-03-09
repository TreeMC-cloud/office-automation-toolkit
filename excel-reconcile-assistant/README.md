# 📋 Excel 智能核对助手

加载两份 Excel/CSV 文件，自动匹配对比，识别差异和缺失记录，生成核对报告。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 功能特性

- **双表加载** — 支持 Excel、CSV 格式的 A 表和 B 表
- **智能映射** — 自动推荐主键列和字段映射关系
- **精确匹配** — 基于主键的精确记录匹配
- **模糊匹配** — 基于 rapidfuzz 的模糊字符串匹配，容忍拼写差异
- **差异识别** — 缺失记录检测、字段值差异对比、重复数据识别
- **核对报告** — 导出为 Excel 工作簿，包含匹配结果和差异明细

## 快速开始

```bash
pip install -r requirements.txt
python desktop_app.py
```

## 项目结构

```
├── desktop_app.py              # 桌面 GUI 主入口
├── services/
│   ├── file_loader.py          # 文件加载
│   ├── column_mapper.py        # 列映射
│   ├── match_engine.py         # 匹配引擎
│   ├── fuzzy_matcher.py        # 模糊匹配
│   ├── duplicate_detector.py   # 重复检测
│   ├── report_generator.py     # 报告生成
│   └── exporter.py             # 导出
├── utils/
│   ├── text_normalizer.py      # 文本标准化
│   └── validators.py           # 数据验证
└── requirements.txt
```
