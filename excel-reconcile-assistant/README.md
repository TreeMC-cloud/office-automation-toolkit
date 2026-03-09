# Excel Reconcile Assistant

一个面向办公自动化场景的 Excel / CSV 智能核对工具，支持多表匹配、缺失检测、字段差异分析、查重、模糊匹配和结果导出。

## 功能特性
- 上传两份 Excel / CSV 文件并预览数据
- 自动推荐主键列和字段映射
- 精确匹配、A 表缺失 / B 表缺失检测
- 字段差异比对与重复数据识别
- 基于相似度的模糊匹配候选推荐
- 一键导出多 Sheet 核对结果工作簿
- 自动生成核对摘要，便于写日报或同步给同事

## 典型场景
- 客户主数据核对
- 订单与 CRM 数据比对
- 财务回款对账
- 多部门 Excel 数据清洗

## 技术栈
- Python
- Streamlit
- pandas / openpyxl
- rapidfuzz

## 项目结构
```text
excel-reconcile-assistant/
├─ app.py
├─ services/
├─ utils/
├─ sample_data/
└─ docs/
```

## 快速开始
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 示例数据
项目自带 `sample_data/customers.csv` 和 `sample_data/orders.csv`，可直接用于演示：
- 客户名称不完全一致
- 存在缺失记录
- 存在联系人、手机号、金额等字段差异
- 存在重复客户记录

## 导出结果
导出的工作簿包含：
- `summary`
- `matched_records`
- `exact_matches`
- `missing_in_b`
- `missing_in_a`
- `mismatch_details`
- `duplicates_a`
- `duplicates_b`
- `fuzzy_candidates`
- `report`

## 后续可扩展
- 多文件批量核对
- 自然语言查询条件
- 接入 LLM 自动生成更详细的核对说明
- 历史任务存档与报表对比
