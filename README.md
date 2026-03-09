# 🛠️ Office Automation Toolkit

三个开箱即用的办公自动化桌面工具，基于 Python + CustomTkinter 构建，支持打包为独立 exe 无需安装环境。

## 项目列表

| 项目 | 说明 | 核心技术 |
|------|------|---------|
| [web-data-collector](./web-data-collector) | 🔍 网页信息智能采集平台 | 多引擎搜索、智能正文提取、JSON-LD 解析、图片采集 |
| [report-automation-bot](./report-automation-bot) | 📊 自动报表生成机器人 | 数据清洗、指标计算、图表生成、HTML/Excel 报告、飞书/邮件通知 |
| [excel-reconcile-assistant](./excel-reconcile-assistant) | 📋 Excel 智能核对助手 | 双表对比、模糊匹配、差异识别、核对报告导出 |

## 快速开始

每个项目都是独立的，进入对应目录即可运行：

```bash
cd web-data-collector
pip install -r requirements.txt
python desktop_app.py
```

## 打包为 exe

使用 PyInstaller 打包为独立可执行文件，无需 Python 环境：

```bash
pip install pyinstaller
cd web-data-collector
pyinstaller desktop_app.py --noconfirm --windowed --name "网页信息智能采集平台"
```

## 技术栈

- Python 3.10+
- CustomTkinter（桌面 GUI）
- Pandas + openpyxl（数据处理）
- BeautifulSoup4 + requests（网页采集）
- Matplotlib（图表生成）
- rapidfuzz（模糊匹配）

## License

[MIT](./LICENSE)
