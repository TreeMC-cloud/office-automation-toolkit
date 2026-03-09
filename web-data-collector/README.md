# 🔍 网页信息智能采集平台

输入关键词，自动从多个搜索引擎采集信息，智能提取结构化数据并导出 Excel。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 功能特性

- **关键词驱动** — 输入任意关键词，自动识别意图（商品比价/产品评测/新闻资讯/招聘求职/学术论文）
- **多引擎搜索** — 同时从 Bing、百度、搜狗并发搜索，结果交替排列保证来源多样性
- **智能提取** — JSON-LD 结构化数据优先，正文密度算法兜底，自动提取标题/价格/规格/日期/作者/图片
- **图片采集** — 自动提取产品主图（og:image → JSON-LD → 正文大图），过滤 logo/icon 噪声
- **AI 标签** — 品牌识别、情感倾向分析、自动分类、优先级判定、关键词提取
- **质量评分** — 每条结果 0-100 分，衡量信息完整度
- **反爬增强** — 7 个真实浏览器 UA 轮换、自动重试、智能编码检测
- **Excel 导出** — 带 summary 统计页 + records 数据页

## 快速开始

```bash
pip install -r requirements.txt
python desktop_app.py
```

## 使用示例

| 输入关键词 | 自动识别意图 | 采集内容 |
|-----------|------------|---------|
| `iPhone 17` | 产品评测 | 评测文章、参数配置、产品图片 |
| `iPhone 17 价格` | 商品比价 | 各平台报价、优惠信息、产品图片 |
| `Python 招聘 北京` | 招聘求职 | 岗位信息、公司、薪资、地点 |
| `新能源汽车` | 综合搜索 | 新闻资讯、行业动态 |

## 项目结构

```
├── desktop_app.py              # 桌面 GUI 主入口
├── services/
│   ├── keyword_analyzer.py     # 关键词意图分析引擎
│   ├── http_client.py          # HTTP 客户端（UA 轮换/重试）
│   ├── cleaner.py              # 数据清洗去重
│   ├── extractor.py            # DataFrame 转换
│   └── exporter.py             # Excel 导出
├── crawlers/
│   ├── search_crawler.py       # 多引擎并发搜索
│   └── smart_extractor.py      # 智能正文/图片提取
├── utils/
│   └── ai_tagger.py            # 智能标签分类
└── requirements.txt
```

## 依赖

```
customtkinter>=5.2.0
pandas>=2.2.3
requests>=2.32.3
beautifulsoup4>=4.12.3
openpyxl>=3.1.5
lxml>=5.3.0
```
