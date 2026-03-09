"""网页信息采集平台 - CustomTkinter 桌面版"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from tkinter import filedialog, ttk

import customtkinter as ctk
import pandas as pd

# 确保项目根目录在 sys.path 中，以便正确导入子模块
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.detail_crawler import enrich_with_detail
from crawlers.list_crawler import extract_list_items
from services.cleaner import deduplicate_records
from services.exporter import build_export_workbook
from services.extractor import records_to_dataframe
from services.http_client import fetch_html
from utils.ai_tagger import tag_records

# ---------------------------------------------------------------------------
# 默认选择器配置
# ---------------------------------------------------------------------------
DEMO_SELECTORS = {
    "item": ".job-card",
    "title": ".job-title a",
    "link": ".job-title a",
    "summary": ".job-summary",
    "date": ".publish-date",
    "content": ".job-description",
    "company": ".job-company",
    "location": ".job-location",
}

WEB_SELECTORS = {
    "item": "article",
    "title": "h2 a",
    "link": "h2 a",
    "summary": "p",
    "date": ".date",
    "content": ".content",
    "company": ".company",
    "location": ".location",
}


class WebDataCollectorApp(ctk.CTk):
    """主窗口"""

    def __init__(self) -> None:
        super().__init__()

        self.title("🕸️ 网页信息采集与结构化导出平台")
        self.geometry("1100x750")
        self.minsize(900, 600)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # 结果缓存
        self._result_df: pd.DataFrame | None = None
        self._result_workbook: bytes | None = None

        # 选择器输入框引用
        self._selector_entries: dict[str, ctk.CTkEntry] = {}

        self._build_ui()

    # -----------------------------------------------------------------------
    # UI 构建
    # -----------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 使主内容区域可滚动
        container = ctk.CTkScrollableFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        container.columnconfigure(0, weight=1)

        self._build_source_section(container)
        self._build_selector_section(container)
        self._build_action_section(container)
        self._build_metrics_section(container)
        self._build_result_section(container)

    # -- 1. 数据源选择 -------------------------------------------------------
    def _build_source_section(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="数据源模式", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=10, pady=8, sticky="w"
        )

        self._mode_var = ctk.StringVar(value="演示站点")
        seg = ctk.CTkSegmentedButton(
            frame,
            values=["演示站点", "公开网页"],
            variable=self._mode_var,
            command=self._on_mode_changed,
        )
        seg.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        # URL 输入（公开网页模式可见）
        self._url_entry = ctk.CTkEntry(frame, placeholder_text="https://example.com/jobs", width=480)
        self._url_entry.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="ew")
        self._url_entry.grid_remove()  # 默认隐藏

        self._demo_hint = ctk.CTkLabel(
            frame, text="ℹ️ 当前使用内置招聘演示站点，无需联网即可完整演示抓取流程。",
            text_color="gray",
        )
        self._demo_hint.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="w")

    # -- 2. 解析配置区 -------------------------------------------------------
    def _build_selector_section(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent)
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(frame, text="解析配置", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=10, pady=(8, 4), sticky="w", columnspan=3
        )

        # 三列布局
        for col in range(3):
            frame.columnconfigure(col, weight=1)

        labels_keys = [
            # 左列
            [("列表项选择器", "item"), ("标题选择器", "title"), ("链接选择器", "link")],
            # 中列
            [("摘要选择器", "summary"), ("日期选择器", "date"), ("详情正文选择器", "content")],
            # 右列
            [("公司选择器", "company"), ("地点选择器", "location")],
        ]

        defaults = DEMO_SELECTORS

        for col_idx, col_items in enumerate(labels_keys):
            col_frame = ctk.CTkFrame(frame, fg_color="transparent")
            col_frame.grid(row=1, column=col_idx, padx=6, pady=4, sticky="new")
            col_frame.columnconfigure(0, weight=1)

            for row_idx, (label, key) in enumerate(col_items):
                ctk.CTkLabel(col_frame, text=label).grid(row=row_idx * 2, column=0, sticky="w", padx=4)
                entry = ctk.CTkEntry(col_frame)
                entry.insert(0, defaults[key])
                entry.grid(row=row_idx * 2 + 1, column=0, sticky="ew", padx=4, pady=(0, 6))
                self._selector_entries[key] = entry

        # 最大抓取条数滑块（放在右列最后）
        right_frame = frame.winfo_children()[-1]  # 右列 col_frame
        slider_row = len(labels_keys[2]) * 2
        ctk.CTkLabel(right_frame, text="最大抓取条数").grid(row=slider_row, column=0, sticky="w", padx=4)

        slider_container = ctk.CTkFrame(right_frame, fg_color="transparent")
        slider_container.grid(row=slider_row + 1, column=0, sticky="ew", padx=4, pady=(0, 6))
        slider_container.columnconfigure(0, weight=1)

        self._max_items_var = ctk.IntVar(value=10)
        self._max_items_label = ctk.CTkLabel(slider_container, text="10", width=30)
        self._max_items_label.grid(row=0, column=1, padx=(6, 0))

        slider = ctk.CTkSlider(
            slider_container, from_=1, to=20, number_of_steps=19,
            variable=self._max_items_var,
            command=lambda v: self._max_items_label.configure(text=str(int(v))),
        )
        slider.grid(row=0, column=0, sticky="ew")

    # -- 3. 执行区 -----------------------------------------------------------
    def _build_action_section(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        self._start_btn = ctk.CTkButton(
            frame, text="🚀 开始采集", height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_start_collect,
        )
        self._start_btn.grid(row=0, column=0, sticky="ew")

        self._status_label = ctk.CTkLabel(frame, text="", text_color="gray")
        self._status_label.grid(row=1, column=0, pady=(4, 0))

    # -- 4. 指标卡片 ---------------------------------------------------------
    def _build_metrics_section(self, parent: ctk.CTkFrame) -> None:
        self._metrics_frame = ctk.CTkFrame(parent)
        self._metrics_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self._metrics_frame.grid_remove()  # 初始隐藏

        for col in range(3):
            self._metrics_frame.columnconfigure(col, weight=1)

        self._metric_labels: dict[str, ctk.CTkLabel] = {}
        metric_defs = [
            ("records", "抓取记录数", "0"),
            ("high_priority", "高优先级信息", "0"),
            ("companies", "公司 / 机构数", "0"),
        ]
        for col_idx, (key, title, default) in enumerate(metric_defs):
            card = ctk.CTkFrame(self._metrics_frame)
            card.grid(row=0, column=col_idx, padx=6, pady=8, sticky="ew")
            ctk.CTkLabel(card, text=title, text_color="gray").pack(pady=(8, 2))
            val_label = ctk.CTkLabel(card, text=default, font=ctk.CTkFont(size=22, weight="bold"))
            val_label.pack(pady=(0, 8))
            self._metric_labels[key] = val_label

        self._category_label = ctk.CTkLabel(self._metrics_frame, text="已识别类别数：0", text_color="gray")
        self._category_label.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 6), sticky="w")

    # -- 5. 结果展示区 -------------------------------------------------------
    def _build_result_section(self, parent: ctk.CTkFrame) -> None:
        self._tabview = ctk.CTkTabview(parent, height=320)
        self._tabview.grid(row=4, column=0, sticky="nsew", pady=(0, 4))
        self._tabview.grid_remove()  # 初始隐藏
        parent.rowconfigure(4, weight=1)

        # 标签页 1：采集结果
        tab_result = self._tabview.add("采集结果")
        tab_result.columnconfigure(0, weight=1)
        tab_result.rowconfigure(0, weight=1)

        # Treeview + 滚动条
        tree_frame = ctk.CTkFrame(tab_result, fg_color="transparent")
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=26, font=("Microsoft YaHei UI", 10))
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))

        self._tree = ttk.Treeview(tree_frame, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # 标签页 2：导出
        tab_export = self._tabview.add("导出")
        tab_export.columnconfigure(0, weight=1)

        self._export_btn = ctk.CTkButton(
            tab_export, text="📥 导出为 Excel 文件", height=38,
            font=ctk.CTkFont(size=14),
            command=self._on_export,
        )
        self._export_btn.grid(row=0, column=0, pady=20, sticky="ew", padx=20)

    # -----------------------------------------------------------------------
    # 事件处理
    # -----------------------------------------------------------------------
    def _on_mode_changed(self, mode: str) -> None:
        """切换数据源模式时更新 UI"""
        selectors = DEMO_SELECTORS if mode == "演示站点" else WEB_SELECTORS
        for key, entry in self._selector_entries.items():
            entry.delete(0, "end")
            entry.insert(0, selectors[key])

        if mode == "演示站点":
            self._url_entry.grid_remove()
            self._demo_hint.grid()
        else:
            self._demo_hint.grid_remove()
            self._url_entry.grid()

    def _on_start_collect(self) -> None:
        """点击开始采集"""
        self._start_btn.configure(state="disabled")
        self._status_label.configure(text="⏳ 正在抓取并解析页面…")

        # 收集参数
        params = {k: e.get().strip() for k, e in self._selector_entries.items()}
        params["max_items"] = self._max_items_var.get()

        mode = self._mode_var.get()
        demo_root = PROJECT_ROOT / "sample_data" / "demo_pages"

        if mode == "演示站点":
            params["source"] = str(demo_root / "jobs_list.html")
            params["base_url"] = ""
            params["local_base_dir"] = demo_root
        else:
            params["source"] = self._url_entry.get().strip()
            params["base_url"] = params["source"]
            params["local_base_dir"] = None

        thread = threading.Thread(target=self._collect_worker, args=(params,), daemon=True)
        thread.start()

    def _collect_worker(self, params: dict) -> None:
        """子线程：执行采集流水线"""
        try:
            html = fetch_html(params["source"])

            list_records = extract_list_items(
                html=html,
                item_selector=params["item"],
                title_selector=params["title"],
                link_selector=params["link"],
                summary_selector=params["summary"],
                date_selector=params["date"],
                base_url=params["base_url"],
                local_base_dir=params["local_base_dir"],
            )[: params["max_items"]]

            enriched = enrich_with_detail(
                records=list_records,
                content_selector=params["content"],
                company_selector=params["company"],
                location_selector=params["location"],
                base_url=params["base_url"],
                local_base_dir=params["local_base_dir"],
            )

            cleaned = deduplicate_records(enriched)
            tagged = tag_records(cleaned)
            df = records_to_dataframe(tagged)
            wb = build_export_workbook(df)

            self.after(0, self._on_collect_done, df, wb)
        except Exception as exc:
            self.after(0, self._on_collect_error, str(exc))

    def _on_collect_done(self, df: pd.DataFrame, workbook: bytes) -> None:
        """采集完成回调（主线程）"""
        self._result_df = df
        self._result_workbook = workbook

        self._start_btn.configure(state="normal")
        self._status_label.configure(text=f"✅ 采集完成，共 {len(df)} 条记录")

        # 更新指标卡片
        high_priority = int((df["priority"] == "高").sum()) if "priority" in df.columns and not df.empty else 0
        unique_companies = int(df["company"].nunique()) if "company" in df.columns else 0
        unique_categories = int(df["category"].nunique()) if "category" in df.columns else 0

        self._metric_labels["records"].configure(text=str(len(df)))
        self._metric_labels["high_priority"].configure(text=str(high_priority))
        self._metric_labels["companies"].configure(text=str(unique_companies))
        self._category_label.configure(text=f"已识别类别数：{unique_categories}")
        self._metrics_frame.grid()

        # 填充 Treeview
        self._populate_treeview(df)
        self._tabview.grid()
        self._tabview.set("采集结果")

    def _on_collect_error(self, message: str) -> None:
        """采集出错回调（主线程）"""
        self._start_btn.configure(state="normal")
        self._status_label.configure(text=f"❌ 采集失败：{message}")

    def _populate_treeview(self, df: pd.DataFrame) -> None:
        """将 DataFrame 填充到 Treeview"""
        # 清空旧数据
        self._tree.delete(*self._tree.get_children())

        columns = list(df.columns)
        self._tree["columns"] = columns

        for col in columns:
            self._tree.heading(col, text=col)
            # 根据列名设置合理宽度
            width = 160 if col in ("title", "content", "ai_summary", "url") else 90
            self._tree.column(col, width=width, minwidth=60)

        for _, row in df.iterrows():
            values = [str(v) if pd.notna(v) else "" for v in row]
            self._tree.insert("", "end", values=values)

    def _on_export(self) -> None:
        """导出 Excel"""
        if self._result_workbook is None:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx")],
            initialfile="web_data_collector_result.xlsx",
        )
        if not path:
            return

        Path(path).write_bytes(self._result_workbook)
        self._status_label.configure(text=f"📁 已导出到：{path}")


if __name__ == "__main__":
    app = WebDataCollectorApp()
    app.mainloop()
