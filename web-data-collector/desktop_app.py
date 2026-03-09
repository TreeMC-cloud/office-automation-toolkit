"""网页信息采集平台 - 关键词驱动智能采集（CustomTkinter 桌面版）"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from tkinter import filedialog, ttk

import customtkinter as ctk
import pandas as pd

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.search_crawler import search_multiple_queries
from crawlers.smart_extractor import enrich_search_results
from services.cleaner import deduplicate_records
from services.exporter import build_export_workbook
from services.extractor import records_to_dataframe
from services.keyword_analyzer import analyze_keyword
from utils.ai_tagger import tag_records

# 类别选项
CATEGORY_OPTIONS = ["自动", "招聘", "商品", "新闻", "论文", "通用"]


class WebDataCollectorApp(ctk.CTk):
    """关键词驱动智能采集主窗口"""

    def __init__(self) -> None:
        super().__init__()

        self.title("🔍 网页信息智能采集平台")
        self.geometry("1100x750")
        self.minsize(900, 600)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._result_df: pd.DataFrame | None = None
        self._result_workbook: bytes | None = None

        self._build_ui()

    # -----------------------------------------------------------------------
    # UI 构建
    # -----------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = ctk.CTkScrollableFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        container.columnconfigure(0, weight=1)

        self._build_input_section(container)
        self._build_action_section(container)
        self._build_progress_section(container)
        self._build_metrics_section(container)
        self._build_result_section(container)

    # -- 1. 关键词输入区 -----------------------------------------------------
    def _build_input_section(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="智能采集配置", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=10, pady=(8, 4), sticky="w", columnspan=4
        )

        # 关键词输入
        ctk.CTkLabel(frame, text="关键词：").grid(row=1, column=0, padx=(10, 4), pady=6, sticky="w")
        self._keyword_entry = ctk.CTkEntry(
            frame, placeholder_text="输入关键词，如：Python 招聘 北京、新能源汽车销量、GPU 价格对比",
            height=36,
        )
        self._keyword_entry.grid(row=1, column=1, padx=4, pady=6, sticky="ew")
        self._keyword_entry.bind("<Return>", lambda e: self._on_start_collect())

        # 数据类别
        ctk.CTkLabel(frame, text="类别：").grid(row=1, column=2, padx=(12, 4), pady=6, sticky="w")
        self._category_var = ctk.StringVar(value="自动")
        self._category_menu = ctk.CTkOptionMenu(
            frame, values=CATEGORY_OPTIONS, variable=self._category_var, width=100,
        )
        self._category_menu.grid(row=1, column=3, padx=(4, 10), pady=6)

        # 第二行：最大条数
        ctk.CTkLabel(frame, text="最大采集条数：").grid(row=2, column=0, padx=(10, 4), pady=(0, 8), sticky="w")

        slider_frame = ctk.CTkFrame(frame, fg_color="transparent")
        slider_frame.grid(row=2, column=1, columnspan=3, padx=4, pady=(0, 8), sticky="ew")
        slider_frame.columnconfigure(0, weight=1)

        self._max_items_var = ctk.IntVar(value=10)
        self._max_items_label = ctk.CTkLabel(slider_frame, text="10", width=30)
        self._max_items_label.grid(row=0, column=1, padx=(6, 10))

        slider = ctk.CTkSlider(
            slider_frame, from_=1, to=30, number_of_steps=29,
            variable=self._max_items_var,
            command=lambda v: self._max_items_label.configure(text=str(int(v))),
        )
        slider.grid(row=0, column=0, sticky="ew")

    # -- 2. 执行区 -----------------------------------------------------------
    def _build_action_section(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        self._start_btn = ctk.CTkButton(
            frame, text="🚀 开始智能采集", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_start_collect,
        )
        self._start_btn.grid(row=0, column=0, sticky="ew")

    # -- 3. 进度区 -----------------------------------------------------------
    def _build_progress_section(self, parent: ctk.CTkFrame) -> None:
        self._progress_frame = ctk.CTkFrame(parent)
        self._progress_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self._progress_frame.grid_remove()
        self._progress_frame.columnconfigure(0, weight=1)

        self._status_label = ctk.CTkLabel(self._progress_frame, text="", text_color="gray")
        self._status_label.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

        self._progress_bar = ctk.CTkProgressBar(self._progress_frame)
        self._progress_bar.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")
        self._progress_bar.set(0)

        self._detail_label = ctk.CTkLabel(self._progress_frame, text="", text_color="gray", font=ctk.CTkFont(size=11))
        self._detail_label.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")

    # -- 4. 指标卡片 ---------------------------------------------------------
    def _build_metrics_section(self, parent: ctk.CTkFrame) -> None:
        self._metrics_frame = ctk.CTkFrame(parent)
        self._metrics_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self._metrics_frame.grid_remove()

        for col in range(4):
            self._metrics_frame.columnconfigure(col, weight=1)

        self._metric_labels: dict[str, ctk.CTkLabel] = {}
        metric_defs = [
            ("records", "采集记录数", "0"),
            ("category", "识别类别", "-"),
            ("high_priority", "高优先级", "0"),
            ("sources", "信息来源数", "0"),
        ]
        for col_idx, (key, title, default) in enumerate(metric_defs):
            card = ctk.CTkFrame(self._metrics_frame)
            card.grid(row=0, column=col_idx, padx=6, pady=8, sticky="ew")
            ctk.CTkLabel(card, text=title, text_color="gray").pack(pady=(8, 2))
            val_label = ctk.CTkLabel(card, text=default, font=ctk.CTkFont(size=20, weight="bold"))
            val_label.pack(pady=(0, 8))
            self._metric_labels[key] = val_label

    # -- 5. 结果展示区 -------------------------------------------------------
    def _build_result_section(self, parent: ctk.CTkFrame) -> None:
        self._tabview = ctk.CTkTabview(parent, height=320)
        self._tabview.grid(row=4, column=0, sticky="nsew", pady=(0, 4))
        self._tabview.grid_remove()
        parent.rowconfigure(4, weight=1)

        # 采集结果
        tab_result = self._tabview.add("采集结果")
        tab_result.columnconfigure(0, weight=1)
        tab_result.rowconfigure(0, weight=1)

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

        # 导出
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
    def _on_start_collect(self) -> None:
        keyword = self._keyword_entry.get().strip()
        if not keyword:
            self._update_status("⚠️ 请输入关键词")
            return

        self._start_btn.configure(state="disabled")
        self._progress_frame.grid()
        self._progress_bar.set(0)
        self._update_status("⏳ 正在分析关键词…")

        category = self._category_var.get()
        max_items = self._max_items_var.get()

        thread = threading.Thread(
            target=self._collect_worker,
            args=(keyword, category, max_items),
            daemon=True,
        )
        thread.start()

    def _collect_worker(self, keyword: str, category: str, max_items: int) -> None:
        """子线程：执行关键词驱动采集流水线"""
        try:
            # 1. 分析关键词
            analysis = analyze_keyword(keyword, category_override=category)
            detected_category = analysis["category"]
            queries = analysis["search_queries"]
            expected_fields = analysis["expected_fields"]

            self.after(0, self._update_status, f"📋 识别类别：{detected_category}，生成 {len(queries)} 个搜索查询")
            self.after(0, self._progress_bar.set, 0.1)

            # 2. 搜索引擎抓取
            self.after(0, self._update_detail, "正在搜索 Bing…")

            def on_search_progress(query, idx, total):
                self.after(0, self._update_detail, f"搜索中 ({idx+1}/{total})：{query}")
                self.after(0, self._progress_bar.set, 0.1 + 0.2 * (idx + 1) / total)

            search_results = search_multiple_queries(
                queries, max_results=max_items, progress_callback=on_search_progress,
            )

            if not search_results:
                self.after(0, self._on_collect_error, "未找到搜索结果，请尝试其他关键词")
                return

            self.after(0, self._update_status, f"🔗 找到 {len(search_results)} 个结果，正在提取详情…")
            self.after(0, self._progress_bar.set, 0.35)

            # 3. 深入详情页提取
            def on_extract_progress(idx, total, url):
                self.after(0, self._update_detail, f"提取中 ({idx+1}/{total})：{url[:60]}…")
                self.after(0, self._progress_bar.set, 0.35 + 0.45 * (idx + 1) / total)

            enriched = enrich_search_results(
                search_results, expected_fields, progress_callback=on_extract_progress,
            )

            # 4. 清洗去重
            self.after(0, self._update_status, "🧹 清洗去重中…")
            self.after(0, self._progress_bar.set, 0.85)
            cleaned = deduplicate_records(enriched)

            # 5. 标签分类
            self.after(0, self._update_status, "🏷️ 智能标签分类中…")
            self.after(0, self._progress_bar.set, 0.9)
            tagged = tag_records(cleaned)

            # 6. 转换 + 导出
            df = records_to_dataframe(tagged)
            wb = build_export_workbook(df)

            self.after(0, self._progress_bar.set, 1.0)
            self.after(0, self._on_collect_done, df, wb, detected_category)

        except Exception as exc:
            self.after(0, self._on_collect_error, str(exc))

    def _on_collect_done(self, df: pd.DataFrame, workbook: bytes, category: str) -> None:
        self._result_df = df
        self._result_workbook = workbook

        self._start_btn.configure(state="normal")
        self._update_status(f"✅ 采集完成，共 {len(df)} 条记录")
        self._update_detail("")

        # 更新指标
        high_priority = int((df["priority"] == "高").sum()) if "priority" in df.columns and not df.empty else 0
        unique_categories = int(df["category"].nunique()) if "category" in df.columns else 0

        # 来源数：优先用 source 列，否则从 url 提取域名
        if "source" in df.columns and not df.empty:
            sources = df["source"][df["source"].astype(str).str.strip() != ""].nunique()
        elif "company" in df.columns and not df.empty:
            sources = df["company"].nunique()
        else:
            sources = 0

        self._metric_labels["records"].configure(text=str(len(df)))
        self._metric_labels["category"].configure(text=category)
        self._metric_labels["high_priority"].configure(text=str(high_priority))
        self._metric_labels["sources"].configure(text=str(sources))
        self._metrics_frame.grid()

        self._populate_treeview(df)
        self._tabview.grid()
        self._tabview.set("采集结果")

    def _on_collect_error(self, message: str) -> None:
        self._start_btn.configure(state="normal")
        self._update_status(f"❌ 采集失败：{message}")
        self._update_detail("")

    def _update_status(self, text: str) -> None:
        self._status_label.configure(text=text)

    def _update_detail(self, text: str) -> None:
        self._detail_label.configure(text=text)

    def _populate_treeview(self, df: pd.DataFrame) -> None:
        self._tree.delete(*self._tree.get_children())

        columns = list(df.columns)
        self._tree["columns"] = columns

        for col in columns:
            self._tree.heading(col, text=col)
            width = 180 if col in ("title", "content", "abstract", "ai_summary", "url", "snippet") else 90
            self._tree.column(col, width=width, minwidth=60)

        for _, row in df.iterrows():
            values = [str(v)[:200] if pd.notna(v) else "" for v in row]
            self._tree.insert("", "end", values=values)

    def _on_export(self) -> None:
        if self._result_workbook is None:
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx")],
            initialfile="智能采集结果.xlsx",
        )
        if not path:
            return

        Path(path).write_bytes(self._result_workbook)
        self._update_status(f"📁 已导出到：{path}")


if __name__ == "__main__":
    app = WebDataCollectorApp()
    app.mainloop()
