"""网页信息智能采集平台 - 关键词驱动多引擎采集（CustomTkinter 桌面版）"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
import pandas as pd

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.search_crawler import search_multi_engine
from crawlers.smart_extractor import enrich_search_results, download_images
from services.cleaner import deduplicate_records
from services.exporter import build_export_workbook
from services.extractor import records_to_dataframe
from services.keyword_analyzer import analyze_keyword, INTENT_OPTIONS
from services.history_store import save_history, list_history, load_history_results, delete_history
from utils.ai_tagger import tag_records

ENGINE_OPTIONS = [
    ("Bing", "bing"),
    ("百度", "baidu"),
    ("搜狗", "sogou"),
]


class WebDataCollectorApp(ctk.CTk):
    """关键词驱动多引擎智能采集主窗口"""

    def __init__(self) -> None:
        super().__init__()

        self.title("🔍 网页信息智能采集平台")
        self.geometry("1200x800")
        self.minsize(1000, 650)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._result_df: pd.DataFrame | None = None
        self._result_workbook: bytes | None = None
        self._cancel_event: threading.Event | None = None
        self._last_keyword: str = ""
        self._last_intent: str = ""

        self._build_ui()

    # -------------------------------------------------------------------
    # UI 构建
    # -------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = ctk.CTkScrollableFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        container.columnconfigure(0, weight=1)

        self._build_input_section(container)
        self._build_action_section(container)
        self._build_progress_section(container)
        self._build_metrics_section(container)
        self._build_result_section(container)

    # -- 1. 输入区 ---------------------------------------------------------
    def _build_input_section(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="智能采集配置", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=10, pady=(8, 4), sticky="w", columnspan=6
        )

        # ---- 模式切换 RadioButton ----
        mode_frame = ctk.CTkFrame(frame, fg_color="transparent")
        mode_frame.grid(row=1, column=0, columnspan=6, padx=10, pady=(4, 2), sticky="w")

        self._mode_var = ctk.StringVar(value="keyword")
        ctk.CTkRadioButton(
            mode_frame, text="关键词搜索", variable=self._mode_var,
            value="keyword", command=self._on_mode_switch,
        ).grid(row=0, column=0, padx=(0, 16))
        ctk.CTkRadioButton(
            mode_frame, text="直接URL采集", variable=self._mode_var,
            value="url", command=self._on_mode_switch,
        ).grid(row=0, column=1)

        # ---- 关键词模式面板 ----
        self._keyword_panel = ctk.CTkFrame(frame, fg_color="transparent")
        self._keyword_panel.grid(row=2, column=0, columnspan=6, sticky="ew")
        self._keyword_panel.columnconfigure(1, weight=1)

        ctk.CTkLabel(self._keyword_panel, text="关键词：").grid(
            row=0, column=0, padx=(10, 4), pady=6, sticky="w",
        )
        self._keyword_entry = ctk.CTkEntry(
            self._keyword_panel,
            placeholder_text="输入任意关键词，如：iPhone 17、新能源汽车销量、Python 招聘 北京",
            height=36,
        )
        self._keyword_entry.grid(row=0, column=1, columnspan=3, padx=4, pady=6, sticky="ew")
        self._keyword_entry.bind("<Return>", lambda e: self._on_start_collect())

        ctk.CTkLabel(self._keyword_panel, text="意图：").grid(
            row=0, column=4, padx=(12, 4), pady=6, sticky="w",
        )
        self._intent_var = ctk.StringVar(value="自动")
        self._intent_menu = ctk.CTkOptionMenu(
            self._keyword_panel, values=INTENT_OPTIONS, variable=self._intent_var, width=110,
        )
        self._intent_menu.grid(row=0, column=5, padx=(4, 10), pady=6)

        # 搜索引擎 + 最大条数
        ctk.CTkLabel(self._keyword_panel, text="搜索引擎：").grid(
            row=1, column=0, padx=(10, 4), pady=(0, 8), sticky="w",
        )

        engine_frame = ctk.CTkFrame(self._keyword_panel, fg_color="transparent")
        engine_frame.grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")

        self._engine_vars: dict[str, ctk.BooleanVar] = {}
        for i, (display, key) in enumerate(ENGINE_OPTIONS):
            var = ctk.BooleanVar(value=(key in ("bing", "baidu")))
            cb = ctk.CTkCheckBox(engine_frame, text=display, variable=var, width=80)
            cb.grid(row=0, column=i, padx=(0, 12))
            self._engine_vars[key] = var

        ctk.CTkLabel(self._keyword_panel, text="最大条数：").grid(
            row=1, column=2, padx=(12, 4), pady=(0, 8), sticky="e",
        )

        slider_frame = ctk.CTkFrame(self._keyword_panel, fg_color="transparent")
        slider_frame.grid(row=1, column=3, columnspan=3, padx=4, pady=(0, 8), sticky="ew")
        slider_frame.columnconfigure(0, weight=1)

        self._max_items_var = ctk.IntVar(value=15)
        self._max_items_label = ctk.CTkLabel(slider_frame, text="15", width=30)
        self._max_items_label.grid(row=0, column=1, padx=(6, 10))

        slider = ctk.CTkSlider(
            slider_frame, from_=5, to=50, number_of_steps=45,
            variable=self._max_items_var,
            command=lambda v: self._max_items_label.configure(text=str(int(v))),
        )
        slider.grid(row=0, column=0, sticky="ew")

        # ---- URL 模式面板 ----
        self._url_panel = ctk.CTkFrame(frame, fg_color="transparent")
        self._url_panel.columnconfigure(0, weight=1)
        # 初始隐藏，不 grid

        ctk.CTkLabel(self._url_panel, text="URL 列表（每行一个）：").grid(
            row=0, column=0, padx=10, pady=(6, 2), sticky="w",
        )
        self._url_textbox = ctk.CTkTextbox(self._url_panel, height=120)
        self._url_textbox.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

    def _on_mode_switch(self) -> None:
        if self._mode_var.get() == "keyword":
            self._url_panel.grid_remove()
            self._keyword_panel.grid(row=2, column=0, columnspan=6, sticky="ew")
        else:
            self._keyword_panel.grid_remove()
            self._url_panel.grid(row=2, column=0, columnspan=6, sticky="ew")

    # -- 2. 执行区 ---------------------------------------------------------
    def _build_action_section(self, parent: ctk.CTkFrame) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        self._start_btn = ctk.CTkButton(
            frame, text="🚀 开始智能采集", height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_start_collect,
        )
        self._start_btn.grid(row=0, column=0, sticky="ew")

    # -- 3. 进度区 ---------------------------------------------------------
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

        self._detail_label = ctk.CTkLabel(
            self._progress_frame, text="", text_color="gray", font=ctk.CTkFont(size=11),
        )
        self._detail_label.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="w")

    # -- 4. 指标卡片 -------------------------------------------------------
    def _build_metrics_section(self, parent: ctk.CTkFrame) -> None:
        self._metrics_frame = ctk.CTkFrame(parent)
        self._metrics_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self._metrics_frame.grid_remove()

        for col in range(6):
            self._metrics_frame.columnconfigure(col, weight=1)

        self._metric_labels: dict[str, ctk.CTkLabel] = {}
        metric_defs = [
            ("records", "采集记录", "0"),
            ("intent", "识别意图", "-"),
            ("images", "采集图片", "0"),
            ("quality", "平均质量", "-"),
            ("engines", "搜索引擎", "-"),
            ("high_priority", "高优先级", "0"),
        ]
        for col_idx, (key, title, default) in enumerate(metric_defs):
            card = ctk.CTkFrame(self._metrics_frame)
            card.grid(row=0, column=col_idx, padx=4, pady=8, sticky="ew")
            ctk.CTkLabel(card, text=title, text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=(8, 2))
            val_label = ctk.CTkLabel(card, text=default, font=ctk.CTkFont(size=18, weight="bold"))
            val_label.pack(pady=(0, 8))
            self._metric_labels[key] = val_label

    # -- 5. 结果展示区 -----------------------------------------------------
    def _build_result_section(self, parent: ctk.CTkFrame) -> None:
        self._tabview = ctk.CTkTabview(parent, height=350)
        self._tabview.grid(row=4, column=0, sticky="nsew", pady=(0, 4))
        self._tabview.grid_remove()
        parent.rowconfigure(4, weight=1)

        # ---- 采集结果 Tab ----
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

        # ---- 导出 Tab ----
        tab_export = self._tabview.add("导出")
        tab_export.columnconfigure(0, weight=1)

        self._export_btn = ctk.CTkButton(
            tab_export, text="📥 导出为 Excel 文件", height=38,
            font=ctk.CTkFont(size=14),
            command=self._on_export,
        )
        self._export_btn.grid(row=0, column=0, pady=20, sticky="ew", padx=20)

        self._download_img_btn = ctk.CTkButton(
            tab_export, text="🖼️ 下载采集图片", height=38,
            font=ctk.CTkFont(size=14),
            command=self._on_download_images,
        )
        self._download_img_btn.grid(row=1, column=0, pady=(0, 20), sticky="ew", padx=20)

        # ---- 历史记录 Tab ----
        tab_history = self._tabview.add("历史记录")
        tab_history.columnconfigure(0, weight=1)
        tab_history.rowconfigure(0, weight=1)

        hist_tree_frame = ctk.CTkFrame(tab_history, fg_color="transparent")
        hist_tree_frame.grid(row=0, column=0, sticky="nsew")
        hist_tree_frame.columnconfigure(0, weight=1)
        hist_tree_frame.rowconfigure(0, weight=1)

        hist_columns = ("id", "keyword", "category", "result_count", "image_count", "time")
        hist_headings = ("ID", "关键词", "类别", "结果数", "图片数", "时间")

        self._hist_tree = ttk.Treeview(
            hist_tree_frame, columns=hist_columns, show="headings", selectmode="browse",
        )
        for col_key, heading in zip(hist_columns, hist_headings):
            self._hist_tree.heading(col_key, text=heading)
            width = 60 if col_key in ("id", "result_count", "image_count") else 150
            self._hist_tree.column(col_key, width=width, minwidth=40)

        hist_vsb = ttk.Scrollbar(hist_tree_frame, orient="vertical", command=self._hist_tree.yview)
        self._hist_tree.configure(yscrollcommand=hist_vsb.set)
        self._hist_tree.grid(row=0, column=0, sticky="nsew")
        hist_vsb.grid(row=0, column=1, sticky="ns")

        hist_btn_frame = ctk.CTkFrame(tab_history, fg_color="transparent")
        hist_btn_frame.grid(row=1, column=0, sticky="ew", pady=(6, 4))
        hist_btn_frame.columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            hist_btn_frame, text="📂 加载选中", command=self._on_history_load,
        ).grid(row=0, column=0, padx=6, sticky="ew")
        ctk.CTkButton(
            hist_btn_frame, text="🗑️ 删除选中", command=self._on_history_delete,
            fg_color="#d9534f", hover_color="#c9302c",
        ).grid(row=0, column=1, padx=6, sticky="ew")
        ctk.CTkButton(
            hist_btn_frame, text="🔄 刷新", command=self._refresh_history_list,
        ).grid(row=0, column=2, padx=6, sticky="ew")

    # -------------------------------------------------------------------
    # 事件处理
    # -------------------------------------------------------------------
    def _on_start_collect(self) -> None:
        # 如果正在采集 → 停止
        if self._cancel_event is not None:
            self._cancel_event.set()
            self._start_btn.configure(state="disabled", text="⏳ 正在停止…")
            return

        mode = self._mode_var.get()

        if mode == "keyword":
            keyword = self._keyword_entry.get().strip()
            if not keyword:
                self._show_progress()
                self._update_status("⚠️ 请输入关键词")
                return
            engines = [key for key, var in self._engine_vars.items() if var.get()]
            if not engines:
                self._show_progress()
                self._update_status("⚠️ 请至少选择一个搜索引擎")
                return
        else:
            raw_urls = self._url_textbox.get("1.0", "end").strip()
            if not raw_urls:
                self._show_progress()
                self._update_status("⚠️ 请输入至少一个 URL")
                return

        # 切换按钮为停止状态
        self._cancel_event = threading.Event()
        self._start_btn.configure(text="⏹️ 停止采集", fg_color="#d9534f", hover_color="#c9302c")
        self._show_progress()
        self._progress_bar.set(0)
        self._update_status("⏳ 正在准备…")

        if mode == "keyword":
            keyword = self._keyword_entry.get().strip()
            intent = self._intent_var.get()
            max_items = self._max_items_var.get()
            engines = [key for key, var in self._engine_vars.items() if var.get()]
            thread = threading.Thread(
                target=self._collect_worker_keyword,
                args=(keyword, intent, engines, max_items),
                daemon=True,
            )
        else:
            urls = [u.strip() for u in raw_urls.splitlines() if u.strip()]
            thread = threading.Thread(
                target=self._collect_worker_url,
                args=(urls,),
                daemon=True,
            )
        thread.start()

    def _reset_start_button(self) -> None:
        self._cancel_event = None
        self._start_btn.configure(
            text="🚀 开始智能采集", state="normal",
            fg_color=("#3a7ebf", "#1f538d"), hover_color=("#325882", "#14375e"),
        )

    # -------------------------------------------------------------------
    # 关键词模式 worker
    # -------------------------------------------------------------------
    def _collect_worker_keyword(
        self, keyword: str, intent: str, engines: list[str], max_items: int,
    ) -> None:
        cancel = self._cancel_event
        try:
            # 1. 分析关键词
            analysis = analyze_keyword(keyword, intent_override=intent, engines=engines)
            detected_intent = analysis["intent_display"]
            is_product = analysis["is_product"]
            queries = analysis["search_queries"]
            expected_fields = analysis["expected_fields"]

            self._last_keyword = keyword
            self._last_intent = detected_intent

            if cancel and cancel.is_set():
                self.after(0, self._on_collect_cancelled)
                return

            product_hint = "（产品查询）" if is_product else ""
            self.after(
                0, self._update_status,
                f"📋 意图：{detected_intent}{product_hint}，生成 {len(queries)} 个查询 × {len(engines)} 个引擎",
            )
            self.after(0, self._progress_bar.set, 0.05)

            # 2. 多引擎并发搜索
            def on_search_progress(msg, ratio):
                self.after(0, self._update_detail, msg)
                self.after(0, self._progress_bar.set, 0.05 + 0.25 * ratio)

            search_results = search_multi_engine(
                queries, engines=engines, max_results=max_items,
                progress_callback=on_search_progress,
            )

            if cancel and cancel.is_set():
                self.after(0, self._on_collect_cancelled)
                return

            if not search_results:
                self.after(0, self._on_collect_error, "未找到搜索结果，请尝试其他关键词或更换搜索引擎")
                return

            engine_names = set(r.get("search_engine", "") for r in search_results if r.get("search_engine"))
            self.after(
                0, self._update_status,
                f"🔗 从 {', '.join(engine_names)} 找到 {len(search_results)} 个结果，正在深入提取…",
            )
            self.after(0, self._progress_bar.set, 0.3)

            # 3. 深入详情页提取
            self._run_enrich_and_finish(search_results, expected_fields, cancel, engine_names)

        except Exception as exc:
            self.after(0, self._on_collect_error, str(exc))

    # -------------------------------------------------------------------
    # URL 模式 worker
    # -------------------------------------------------------------------
    def _collect_worker_url(self, urls: list[str]) -> None:
        cancel = self._cancel_event
        try:
            self._last_keyword = "URL直接采集"
            self._last_intent = "URL模式"

            self.after(0, self._update_status, f"🔗 准备采集 {len(urls)} 个 URL…")
            self.after(0, self._progress_bar.set, 0.1)

            search_results = [{"url": u, "title": u, "snippet": ""} for u in urls]
            expected_fields = ["title", "content", "url"]

            self._run_enrich_and_finish(search_results, expected_fields, cancel, engine_names=set())

        except Exception as exc:
            self.after(0, self._on_collect_error, str(exc))

    # -------------------------------------------------------------------
    # 共享：enrich → clean → tag → done
    # -------------------------------------------------------------------
    def _run_enrich_and_finish(
        self,
        search_results: list[dict],
        expected_fields: list[str],
        cancel: threading.Event | None,
        engine_names: set,
    ) -> None:
        def on_extract_progress(idx, total, url):
            short_url = url[:55] + "…" if len(url) > 55 else url
            self.after(0, self._update_detail, f"提取 ({idx+1}/{total})：{short_url}")
            self.after(0, self._progress_bar.set, 0.3 + 0.5 * (idx + 1) / total)

        enriched = enrich_search_results(
            search_results, expected_fields,
            progress_callback=on_extract_progress,
            cancel_event=cancel,
        )

        if cancel and cancel.is_set():
            self.after(0, self._on_collect_cancelled)
            return

        # 4. 清洗去重
        self.after(0, self._update_status, "🧹 清洗去重中…")
        self.after(0, self._progress_bar.set, 0.85)
        cleaned = deduplicate_records(enriched)

        # 5. 智能标签
        self.after(0, self._update_status, "🏷️ 智能标签分类中…")
        self.after(0, self._progress_bar.set, 0.92)
        tagged = tag_records(cleaned)

        # 6. 转换 + 导出
        df = records_to_dataframe(tagged)
        wb = build_export_workbook(df)

        self.after(0, self._progress_bar.set, 1.0)
        self.after(0, self._on_collect_done, df, wb, self._last_intent, engine_names)

    # -------------------------------------------------------------------
    # 采集完成 / 取消 / 错误
    # -------------------------------------------------------------------
    def _on_collect_done(self, df: pd.DataFrame, workbook: bytes, intent: str, engine_names: set) -> None:
        self._result_df = df
        self._result_workbook = workbook

        self._reset_start_button()
        self._update_status(f"✅ 采集完成，共 {len(df)} 条记录")
        self._update_detail("")

        # 指标
        high_priority = int((df["priority"] == "高").sum()) if "priority" in df.columns and not df.empty else 0

        avg_quality = "-"
        if "quality_score" in df.columns and not df.empty:
            scores = pd.to_numeric(df["quality_score"], errors="coerce")
            mean_val = scores.mean()
            if pd.notna(mean_val):
                avg_quality = f"{mean_val:.0f}/100"

        image_count = 0
        if "image_url" in df.columns and not df.empty:
            image_count = int(df["image_url"].astype(str).str.strip().ne("").sum())

        self._metric_labels["records"].configure(text=str(len(df)))
        self._metric_labels["intent"].configure(text=intent)
        self._metric_labels["quality"].configure(text=avg_quality)
        self._metric_labels["engines"].configure(text=", ".join(engine_names) if engine_names else "-")
        self._metric_labels["high_priority"].configure(text=str(high_priority))
        self._metric_labels["images"].configure(text=str(image_count))

        self._metrics_frame.grid()

        self._populate_treeview(df)
        self._tabview.grid()
        self._tabview.set("采集结果")

        # 自动保存历史
        try:
            save_history(
                keyword=self._last_keyword,
                category=self._last_intent,
                result_df=df,
            )
        except Exception:
            pass

    def _on_collect_cancelled(self) -> None:
        self._reset_start_button()
        self._update_status("🛑 采集已停止")
        self._update_detail("")

    def _on_collect_error(self, message: str) -> None:
        self._reset_start_button()
        self._update_status(f"❌ 采集失败：{message}")
        self._update_detail("")

    # -------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------
    def _show_progress(self) -> None:
        self._progress_frame.grid()

    def _update_status(self, text: str) -> None:
        self._status_label.configure(text=text)

    def _update_detail(self, text: str) -> None:
        self._detail_label.configure(text=text)

    def _populate_treeview(self, df: pd.DataFrame) -> None:
        self._tree.delete(*self._tree.get_children())

        columns = list(df.columns)
        self._tree["columns"] = columns

        wide_cols = {"title", "content", "abstract", "ai_summary", "url", "snippet", "specs", "image_url", "image_urls"}
        medium_cols = {"price", "price_range", "source", "domain", "company", "keywords"}

        for col in columns:
            self._tree.heading(col, text=col)
            if col in wide_cols:
                width = 200
            elif col in medium_cols:
                width = 120
            else:
                width = 80
            self._tree.column(col, width=width, minwidth=50)

        for _, row in df.iterrows():
            values = [str(v)[:200] if pd.notna(v) else "" for v in row]
            self._tree.insert("", "end", values=values)

    # -------------------------------------------------------------------
    # 导出
    # -------------------------------------------------------------------
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

    # -------------------------------------------------------------------
    # 图片下载
    # -------------------------------------------------------------------
    def _on_download_images(self) -> None:
        if self._result_df is None or self._result_df.empty:
            messagebox.showwarning("提示", "暂无采集结果，请先执行采集。")
            return

        folder = filedialog.askdirectory(title="选择图片保存文件夹")
        if not folder:
            return

        self._update_status("🖼️ 正在下载图片…")
        self._download_img_btn.configure(state="disabled")

        def _worker():
            try:
                download_images(self._result_df, folder)
                self.after(0, self._update_status, f"🖼️ 图片已保存到：{folder}")
            except Exception as exc:
                self.after(0, self._update_status, f"❌ 图片下载失败：{exc}")
            finally:
                self.after(0, lambda: self._download_img_btn.configure(state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    # -------------------------------------------------------------------
    # 历史记录
    # -------------------------------------------------------------------
    def _refresh_history_list(self) -> None:
        self._hist_tree.delete(*self._hist_tree.get_children())
        try:
            records = list_history()
        except Exception:
            return
        for rec in records:
            self._hist_tree.insert("", "end", values=(
                rec.get("id", ""),
                rec.get("keyword", ""),
                rec.get("category", ""),
                rec.get("result_count", 0),
                rec.get("image_count", 0),
                rec.get("time", ""),
            ))

    def _on_history_load(self) -> None:
        sel = self._hist_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一条历史记录。")
            return
        values = self._hist_tree.item(sel[0], "values")
        history_id = values[0]
        try:
            df = load_history_results(history_id)
        except Exception as exc:
            messagebox.showerror("错误", f"加载失败：{exc}")
            return

        if df is None or df.empty:
            messagebox.showinfo("提示", "该历史记录无数据。")
            return

        self._result_df = df
        self._result_workbook = build_export_workbook(df)
        self._populate_treeview(df)
        self._tabview.grid()
        self._tabview.set("采集结果")
        self._update_status(f"📂 已加载历史记录 #{history_id}，共 {len(df)} 条")

    def _on_history_delete(self) -> None:
        sel = self._hist_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一条历史记录。")
            return
        values = self._hist_tree.item(sel[0], "values")
        history_id = values[0]
        if not messagebox.askyesno("确认", f"确定删除历史记录 #{history_id}？"):
            return
        try:
            delete_history(history_id)
        except Exception as exc:
            messagebox.showerror("错误", f"删除失败：{exc}")
            return
        self._refresh_history_list()
        self._update_status(f"🗑️ 已删除历史记录 #{history_id}")


if __name__ == "__main__":
    app = WebDataCollectorApp()
    app.mainloop()
