"""自动报表机器人 - CustomTkinter 桌面版 — 全面优化"""
from __future__ import annotations

import base64
import io
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk, messagebox

import customtkinter as ctk
import pandas as pd
from PIL import Image

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent / "_internal"
else:
    PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.file_ingestion import load_uploaded_files
from services.cleaner import coerce_dataframe, detect_numeric_columns, compute_data_quality
from services.metrics import (
    compute_overview, aggregate_by_period, aggregate_by_dimension,
    detect_trend, AGG_FUNCS,
)
from services.chart_builder import build_bar_chart_base64, build_line_chart_base64, build_pie_chart_base64
from services.exporter import build_report_workbook
from services.report_renderer import render_html_report
from services.notifier import build_notification_text, send_email, send_feishu
from utils.ai_summary import generate_summary
from services.metrics import cross_analyze
from services.chart_builder import build_multi_line_base64, build_heatmap_base64
from services.notifier import send_dingtalk, send_wechat_work
from services.scheduler import ReportScheduler
from utils.config_store import load_config, save_config

FREQ_OPTIONS = {"按天": "D", "按周": "W", "按月": "M"}


class ReportApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("📬 自动报表生成与通知机器人")
        self.geometry("1200x850")
        self.minsize(1000, 700)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.raw_df: pd.DataFrame | None = None
        self.result: dict | None = None
        self._chart_images: list = []

        self._cancel_event = threading.Event()
        self._config = load_config()
        self._scheduler = None

        # 通知配置持久化
        self._notify_config = {
            "feishu_url": "", "smtp_server": "smtp.qq.com", "smtp_port": "465",
            "sender": "", "password": "", "recipients": "",
            "dingtalk_url": "", "wechat_url": "",
        }

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkScrollableFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        self._container = container

        self._build_source_section(container)
        self._build_preview_section(container)
        self._build_config_section(container)
        self._build_action_section(container)
        self._build_result_section(container)

    # ── 1. 数据来源 ─────────────────────────────────────────

    def _build_source_section(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(frame, text="数据来源", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))

        self._source_var = ctk.StringVar(value="upload")
        ctk.CTkRadioButton(row, text="上传文件", variable=self._source_var, value="upload", command=self._on_source_change).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(row, text="示例数据", variable=self._source_var, value="sample", command=self._on_source_change).pack(side="left", padx=(0, 16))

        self._upload_btn = ctk.CTkButton(row, text="选择文件…", width=120, command=self._pick_files)
        self._upload_btn.pack(side="left", padx=(16, 0))
        self._file_label = ctk.CTkLabel(row, text="未选择文件", text_color="gray")
        self._file_label.pack(side="left", padx=8)

    def _on_source_change(self):
        if self._source_var.get() == "sample":
            self._upload_btn.configure(state="disabled")
            sample_dir = PROJECT_ROOT / "sample_data"
            files = sorted(sample_dir.glob("*.csv"))
            if not files:
                messagebox.showwarning("提示", "sample_data 目录下没有 CSV 文件")
                return
            self._file_label.configure(text=f"已载入 {len(files)} 个示例文件")
            self._load_dataframe(files)
        else:
            self._upload_btn.configure(state="normal")
            self._file_label.configure(text="未选择文件")

    def _pick_files(self):
        paths = filedialog.askopenfilenames(
            title="选择数据文件",
            filetypes=[("数据文件", "*.csv *.xlsx *.xls"), ("所有文件", "*.*")],
        )
        if not paths:
            return
        files = [Path(p) for p in paths]
        self._file_label.configure(text=f"已选择 {len(files)} 个文件")
        self._load_dataframe(files)

    def _load_dataframe(self, files):
        try:
            self.raw_df = load_uploaded_files(list(files))
            self._refresh_preview()
            self._refresh_config_options()
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    # ── 2. 数据预览 ─────────────────────────────────────────

    def _build_preview_section(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(frame, text="数据预览（前 20 行）", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        tree_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tree_frame.pack(fill="x", padx=10, pady=(0, 8))

        self._preview_tree = ttk.Treeview(tree_frame, show="headings", height=10)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._preview_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._preview_tree.xview)
        self._preview_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._preview_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

    def _refresh_preview(self):
        tree = self._preview_tree
        tree.delete(*tree.get_children())
        if self.raw_df is None or self.raw_df.empty:
            tree["columns"] = ()
            return
        cols = [c for c in self.raw_df.columns if c != "__source_file"]
        tree["columns"] = cols
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=110, minwidth=60)
        for _, row in self.raw_df.head(20).iterrows():
            tree.insert("", "end", values=[str(row.get(c, "")) for c in cols])

    # ── 3. 配置区 ───────────────────────────────────────────

    def _build_config_section(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(frame, text="报表配置", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(8, 4))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))
        row.columnconfigure((0, 1, 2), weight=1)

        # 左列
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(left, text="日期列").pack(anchor="w")
        self._date_col_var = ctk.StringVar()
        self._date_col_cb = ctk.CTkComboBox(left, variable=self._date_col_var, state="readonly", width=200)
        self._date_col_cb.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(left, text="指标列").pack(anchor="w")
        self._value_col_var = ctk.StringVar()
        self._value_col_cb = ctk.CTkComboBox(left, variable=self._value_col_var, state="readonly", width=200)
        self._value_col_cb.pack(fill="x")

        # 中列
        mid = ctk.CTkFrame(row, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="nsew", padx=6)
        ctk.CTkLabel(mid, text="维度列").pack(anchor="w")
        self._dim_col_var = ctk.StringVar()
        self._dim_col_cb = ctk.CTkComboBox(mid, variable=self._dim_col_var, state="readonly", width=200)
        self._dim_col_cb.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(mid, text="第二维度列（交叉分析）").pack(anchor="w")
        self._dim2_col_var = ctk.StringVar()
        self._dim2_col_cb = ctk.CTkComboBox(mid, variable=self._dim2_col_var, state="readonly", width=200)
        self._dim2_col_cb.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(mid, text="趋势粒度").pack(anchor="w")
        self._freq_var = ctk.StringVar(value="按天")
        self._freq_cb = ctk.CTkComboBox(mid, variable=self._freq_var, values=list(FREQ_OPTIONS.keys()), state="readonly", width=200)
        self._freq_cb.pack(fill="x")

        # 右列
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(right, text="聚合方式").pack(anchor="w")
        self._agg_var = ctk.StringVar(value="求和")
        self._agg_cb = ctk.CTkComboBox(right, variable=self._agg_var, values=list(AGG_FUNCS.keys()), state="readonly", width=200)
        self._agg_cb.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(right, text="Top N").pack(anchor="w")
        self._topn_var = ctk.IntVar(value=5)
        self._topn_slider = ctk.CTkSlider(right, from_=3, to=10, number_of_steps=7, variable=self._topn_var)
        self._topn_slider.pack(fill="x", pady=(0, 2))
        self._topn_label = ctk.CTkLabel(right, text="5")
        self._topn_label.pack(anchor="w")
        self._topn_var.trace_add("write", lambda *_: self._topn_label.configure(text=str(self._topn_var.get())))

    def _refresh_config_options(self):
        if self.raw_df is None:
            return
        all_cols = self.raw_df.columns.tolist()
        numeric_cols = detect_numeric_columns(self.raw_df)
        dim_cols = [c for c in all_cols if c not in numeric_cols and c != "__source_file"]

        self._date_col_cb.configure(values=all_cols)
        self._date_col_var.set("日期" if "日期" in all_cols else (all_cols[0] if all_cols else ""))

        val_options = numeric_cols or all_cols
        self._value_col_cb.configure(values=val_options)
        self._value_col_var.set("销售额" if "销售额" in val_options else (val_options[0] if val_options else ""))

        dim_options = ["(不选择)"] + dim_cols
        self._dim_col_cb.configure(values=dim_options)
        self._dim_col_var.set(dim_cols[0] if dim_cols else "(不选择)")

        self._dim2_col_cb.configure(values=["(不选择)"] + dim_cols)
        self._dim2_col_var.set("(不选择)")

    # ── 4. 执行区 ───────────────────────────────────────────

    def _build_action_section(self, parent):
        self._gen_btn = ctk.CTkButton(parent, text="生成报表", height=40,
                                       font=ctk.CTkFont(size=14, weight="bold"), command=self._on_generate)
        self._gen_btn.pack(fill="x", pady=(0, 4))

        self._cancel_btn = ctk.CTkButton(parent, text="停止生成", height=36, fg_color="red",
                                          command=self._cancel_generate, state="disabled")
        self._cancel_btn.pack(fill="x", pady=(0, 4))

        self._status_label = ctk.CTkLabel(parent, text="", text_color="gray")
        self._status_label.pack(pady=(0, 2))

        self._progress = ctk.CTkProgressBar(parent)
        self._progress.set(0)

    def _on_generate(self):
        if self.raw_df is None or self.raw_df.empty:
            messagebox.showwarning("提示", "请先加载数据")
            return

        # 输入校验
        date_col = self._date_col_var.get()
        value_col = self._value_col_var.get()
        if not date_col or not value_col:
            messagebox.showwarning("提示", "请选择日期列和指标列")
            return

        # 线程安全：主线程提前取值
        params = {
            "date_col": date_col,
            "value_col": value_col,
            "dim_col": self._dim_col_var.get(),
            "freq": FREQ_OPTIONS.get(self._freq_var.get(), "D"),
            "agg": AGG_FUNCS.get(self._agg_var.get(), "sum"),
            "top_n": self._topn_var.get(),
            "dim2": None if self._dim2_col_var.get() == "(不选择)" else self._dim2_col_var.get(),
        }

        self._gen_btn.configure(state="disabled", text="正在生成…")
        self._cancel_event.clear()
        self._cancel_btn.configure(state="normal")
        self._progress.pack(fill="x", pady=(0, 8))
        self._progress.set(0)
        self._update_status("⏳ 正在清洗数据…")

        threading.Thread(target=self._generate_worker, args=(params,), daemon=True).start()

    def _generate_worker(self, params: dict):
        try:
            df = self.raw_df
            date_col = params["date_col"]
            value_col = params["value_col"]
            dim_col = params["dim_col"]
            dim_name = None if dim_col == "(不选择)" else dim_col
            freq = params["freq"]
            agg = params["agg"]
            top_n = params["top_n"]

            # 1. 清洗
            if self._cancel_event.is_set():
                self.after(0, self._on_generate_cancelled)
                return
            self.after(0, self._update_status, "🧹 清洗数据…")
            self.after(0, self._progress.set, 0.1)
            cleaned = coerce_dataframe(df, date_column=date_col, numeric_columns=[value_col])
            quality = compute_data_quality(cleaned, date_col)

            # 2. 指标计算
            if self._cancel_event.is_set():
                self.after(0, self._on_generate_cancelled)
                return
            self.after(0, self._update_status, "📊 计算指标…")
            self.after(0, self._progress.set, 0.25)
            overview = compute_overview(cleaned, date_column=date_col, value_column=value_col)
            trend_df = aggregate_by_period(cleaned, date_column=date_col, value_column=value_col, freq=freq, agg=agg)
            dimension_df = aggregate_by_dimension(cleaned, dimension_column=dim_name, value_column=value_col, top_n=top_n, agg=agg)
            trend_info = detect_trend(trend_df, value_col)

            # 交叉分析
            dim2 = params.get("dim2")
            cross_df = pd.DataFrame()
            heatmap_chart = ""
            if dim_name and dim2:
                cross_df = cross_analyze(cleaned, dim_name, dim2, value_col, agg=agg)
                heatmap_chart = build_heatmap_base64(cross_df, f"{value_col} 交叉分析")

            # 3. 摘要
            if self._cancel_event.is_set():
                self.after(0, self._on_generate_cancelled)
                return
            self.after(0, self._update_status, "💡 生成摘要…")
            self.after(0, self._progress.set, 0.4)
            summary_text = generate_summary(
                overview=overview, trend_df=trend_df, dimension_df=dimension_df,
                value_label=value_col, dimension_label=dim_name or "维度",
                trend_info=trend_info, data_quality=quality,
            )

            # 4. 图表
            if self._cancel_event.is_set():
                self.after(0, self._on_generate_cancelled)
                return
            self.after(0, self._update_status, "📈 生成图表…")
            self.after(0, self._progress.set, 0.55)
            trend_chart = build_line_chart_base64(
                trend_df, x_column="period", y_column=value_col,
                title=f"{value_col} 趋势", change_column="环比变化率",
            )
            dimension_chart = build_bar_chart_base64(
                dimension_df, x_column=dim_name or "dimension", y_column=value_col,
                title=f"{value_col} Top 分布",
            ) if not dimension_df.empty else ""
            pie_chart = build_pie_chart_base64(
                dimension_df, label_column=dim_name or "dimension", value_column=value_col,
                title=f"{value_col} 占比分布",
            ) if not dimension_df.empty else ""

            # 5. HTML 报告
            if self._cancel_event.is_set():
                self.after(0, self._on_generate_cancelled)
                return
            self.after(0, self._update_status, "📝 渲染报告…")
            self.after(0, self._progress.set, 0.7)
            template_path = PROJECT_ROOT / "templates" / "report.html"
            html_report = render_html_report(
                template_path=template_path,
                context={
                    "title": f"{value_col} 自动分析报告",
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "overview": overview,
                    "data_quality": quality,
                    "summary_text": summary_text,
                    "trend_records": trend_df.to_dict(orient="records"),
                    "dimension_records": dimension_df.to_dict(orient="records"),
                    "preview_records": cleaned.head(10).to_dict(orient="records"),
                    "trend_chart": trend_chart,
                    "dimension_chart": dimension_chart,
                    "pie_chart": pie_chart,
                    "value_label": value_col,
                    "dimension_label": dim_name or "维度",
                },
            )

            # 6. Excel
            if self._cancel_event.is_set():
                self.after(0, self._on_generate_cancelled)
                return
            self.after(0, self._update_status, "📦 构建 Excel…")
            self.after(0, self._progress.set, 0.85)
            workbook = build_report_workbook(
                cleaned, overview, trend_df, dimension_df, summary_text,
                trend_chart_b64=trend_chart, dimension_chart_b64=dimension_chart,
            )

            self.result = {
                "overview": overview, "trend_df": trend_df, "dimension_df": dimension_df,
                "dimension_name": dim_name, "value_col": value_col,
                "summary_text": summary_text, "html_report": html_report,
                "workbook": workbook, "trend_chart": trend_chart,
                "dimension_chart": dimension_chart, "pie_chart": pie_chart,
                "trend_info": trend_info, "data_quality": quality,
                "cross_df": cross_df, "heatmap_chart": heatmap_chart,
            }
            self.after(0, self._progress.set, 1.0)
            self.after(0, self._on_generate_done)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda: self._on_generate_error(str(e)))

    def _on_generate_done(self):
        self._progress.pack_forget()
        self._gen_btn.configure(state="normal", text="生成报表")
        self._cancel_btn.configure(state="disabled")
        self._update_status("✅ 报表生成完成")
        self._show_results()

    def _on_generate_error(self, msg):
        self._progress.pack_forget()
        self._gen_btn.configure(state="normal", text="生成报表")
        self._update_status("")
        messagebox.showerror("生成失败", msg)

    def _update_status(self, text: str):
        self._status_label.configure(text=text)

    def _cancel_generate(self):
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled")
        self._update_status("⏹ 正在停止…")

    def _on_generate_cancelled(self):
        self._progress.pack_forget()
        self._gen_btn.configure(state="normal", text="生成报表")
        self._cancel_btn.configure(state="disabled")
        self._update_status("⏹ 已停止")

    # ── 5. 结果展示区 ───────────────────────────────────────

    def _build_result_section(self, parent):
        self._result_frame = ctk.CTkFrame(parent)

    def _show_results(self):
        res = self.result
        if not res:
            return
        overview = res["overview"]

        for w in self._result_frame.winfo_children():
            w.destroy()
        self._chart_images.clear()
        self._result_frame.pack(fill="both", expand=True, pady=(0, 8))

        # 导出按钮（顶部）
        export_row = ctk.CTkFrame(self._result_frame, fg_color="transparent")
        export_row.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkButton(export_row, text="📥 下载 HTML 报告", command=lambda: self._save_html(res)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(export_row, text="📥 下载 Excel 报表", command=lambda: self._save_excel(res)).pack(side="left")

        # 指标卡片
        cards = ctk.CTkFrame(self._result_frame, fg_color="transparent")
        cards.pack(fill="x", padx=10, pady=(4, 4))
        metrics = [
            ("总记录数", f"{overview['total_records']:,}"),
            ("总指标值", f"{overview['total_value']:,.2f}"),
            ("均值", f"{overview['average_value']:,.2f}"),
            ("中位数", f"{overview.get('median_value', 0):,.2f}"),
            ("最大值", f"{overview.get('max_value', 0):,.2f}"),
            ("最小值", f"{overview.get('min_value', 0):,.2f}"),
            ("标准差", f"{overview.get('std_value', 0):,.2f}"),
            ("最新周期值", f"{overview['latest_period_value']:,.2f}"),
        ]
        for i in range(len(metrics)):
            cards.columnconfigure(i, weight=1)
        for i, (label, value) in enumerate(metrics):
            card = ctk.CTkFrame(cards)
            card.grid(row=0, column=i, sticky="nsew", padx=3, pady=4)
            ctk.CTkLabel(card, text=label, text_color="gray", font=ctk.CTkFont(size=11)).pack(padx=6, pady=(6, 0))
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=16, weight="bold")).pack(padx=6, pady=(0, 6))

        # 环比变化率
        trend_info = res.get("trend_info", {})
        direction = trend_info.get("direction", "")
        if direction and direction != "数据不足":
            ctk.CTkLabel(self._result_frame, text=f"📈 趋势：{direction}",
                         font=ctk.CTkFont(size=13), text_color="#2563eb").pack(anchor="w", padx=14, pady=(4, 0))

        # 标签页
        tabview = ctk.CTkTabview(self._result_frame)
        tabview.pack(fill="both", expand=True, padx=10, pady=(4, 8))

        tab1 = tabview.add("趋势与维度")
        tab2 = tabview.add("摘要")
        tab3 = tabview.add("通知发送")
        tab4 = tabview.add("交叉分析")

        self._fill_tab_trend(tab1, res)
        self._fill_tab_summary(tab2, res)
        self._fill_tab_notify(tab3, res)
        self._fill_tab_cross(tab4, res)

    def _fill_tab_trend(self, parent, res):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)

        if res["trend_chart"]:
            ctk.CTkLabel(scroll, text="趋势图（含环比变化率）", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(4, 2))
            self._place_chart_image(scroll, res["trend_chart"])

        if res.get("dimension_chart"):
            ctk.CTkLabel(scroll, text="维度 Top N 分布", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(8, 2))
            self._place_chart_image(scroll, res["dimension_chart"])

        if res.get("pie_chart"):
            ctk.CTkLabel(scroll, text="维度占比饼图", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(8, 2))
            self._place_chart_image(scroll, res["pie_chart"])

        ctk.CTkLabel(scroll, text="趋势数据", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(8, 2))
        self._build_df_treeview(scroll, res["trend_df"])

        if not res["dimension_df"].empty:
            ctk.CTkLabel(scroll, text="维度数据", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(8, 2))
            self._build_df_treeview(scroll, res["dimension_df"])

    def _place_chart_image(self, parent, b64_str: str):
        raw = base64.b64decode(b64_str)
        pil_img = Image.open(io.BytesIO(raw))
        max_w = 900
        if pil_img.width > max_w:
            ratio = max_w / pil_img.width
            pil_img = pil_img.resize((max_w, int(pil_img.height * ratio)), Image.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(pil_img.width, pil_img.height))
        self._chart_images.append(ctk_img)
        ctk.CTkLabel(parent, image=ctk_img, text="").pack(pady=4)

    def _build_df_treeview(self, parent, df: pd.DataFrame):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=(0, 4))
        cols = df.columns.tolist()
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=min(len(df), 10))
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=120, minwidth=60)
        for _, row in df.iterrows():
            tree.insert("", "end", values=[str(row[c]) for c in cols])
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=hsb.set)
        tree.pack(fill="x")
        hsb.pack(fill="x")

    def _fill_tab_summary(self, parent, res):
        ctk.CTkLabel(parent, text="智能摘要", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
        txt = ctk.CTkTextbox(parent, height=300)
        txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        txt.insert("0.0", res["summary_text"])
        txt.configure(state="disabled")

    def _fill_tab_cross(self, parent, res):
        if res.get("heatmap_chart"):
            ctk.CTkLabel(parent, text="交叉分析热力图", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
            self._place_chart_image(parent, res["heatmap_chart"])
        cross_df = res.get("cross_df", pd.DataFrame())
        if not cross_df.empty:
            ctk.CTkLabel(parent, text="交叉透视表", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
            # 把 index 变成列
            display_df = cross_df.reset_index()
            self._build_df_treeview(parent, display_df)
        if not res.get("heatmap_chart") and cross_df.empty:
            ctk.CTkLabel(parent, text="请选择两个维度列以启用交叉分析", text_color="gray").pack(pady=20)

    def _fill_tab_notify(self, parent, res):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)

        notification_text = build_notification_text(res["summary_text"], res["overview"])

        ctk.CTkLabel(scroll, text="飞书 Webhook（可选）", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
        self._feishu_entry = ctk.CTkEntry(scroll, placeholder_text="https://open.feishu.cn/open-apis/bot/v2/hook/...")
        self._feishu_entry.pack(fill="x", padx=8, pady=(0, 8))
        if self._notify_config["feishu_url"]:
            self._feishu_entry.insert(0, self._notify_config["feishu_url"])

        ctk.CTkLabel(scroll, text="钉钉 Webhook（可选）", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        self._dingtalk_entry = ctk.CTkEntry(scroll, placeholder_text="https://oapi.dingtalk.com/robot/send?access_token=...")
        self._dingtalk_entry.pack(fill="x", padx=8, pady=(0, 8))
        if self._notify_config.get("dingtalk_url"):
            self._dingtalk_entry.insert(0, self._notify_config["dingtalk_url"])

        ctk.CTkLabel(scroll, text="企业微信 Webhook（可选）", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        self._wechat_entry = ctk.CTkEntry(scroll, placeholder_text="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...")
        self._wechat_entry.pack(fill="x", padx=8, pady=(0, 8))
        if self._notify_config.get("wechat_url"):
            self._wechat_entry.insert(0, self._notify_config["wechat_url"])

        ctk.CTkLabel(scroll, text="邮件配置（可选）", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        mail_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        mail_frame.pack(fill="x", padx=8, pady=(0, 4))
        mail_frame.columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(mail_frame, text="SMTP 服务器").grid(row=0, column=0, sticky="w")
        self._smtp_server = ctk.CTkEntry(mail_frame)
        self._smtp_server.insert(0, self._notify_config["smtp_server"])
        self._smtp_server.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(0, 4))

        ctk.CTkLabel(mail_frame, text="SMTP 端口").grid(row=0, column=1, sticky="w")
        self._smtp_port = ctk.CTkEntry(mail_frame)
        self._smtp_port.insert(0, self._notify_config["smtp_port"])
        self._smtp_port.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(0, 4))

        ctk.CTkLabel(mail_frame, text="发件邮箱").grid(row=2, column=0, sticky="w")
        self._sender = ctk.CTkEntry(mail_frame)
        if self._notify_config["sender"]:
            self._sender.insert(0, self._notify_config["sender"])
        self._sender.grid(row=3, column=0, sticky="ew", padx=(0, 4), pady=(0, 4))

        ctk.CTkLabel(mail_frame, text="邮箱授权码 / 密码").grid(row=2, column=1, sticky="w")
        self._mail_pwd = ctk.CTkEntry(mail_frame, show="*")
        self._mail_pwd.grid(row=3, column=1, sticky="ew", padx=(4, 0), pady=(0, 4))

        ctk.CTkLabel(mail_frame, text="收件人（多个用逗号分隔）").grid(row=4, column=0, columnspan=2, sticky="w")
        self._recipients = ctk.CTkEntry(mail_frame)
        if self._notify_config["recipients"]:
            self._recipients.insert(0, self._notify_config["recipients"])
        self._recipients.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        ctk.CTkButton(scroll, text="发送通知", command=lambda: self._send_notify(res)).pack(fill="x", padx=8, pady=(4, 8))

        ctk.CTkLabel(scroll, text="通知预览", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        preview = ctk.CTkTextbox(scroll, height=180)
        preview.pack(fill="x", padx=8, pady=(0, 8))
        preview.insert("0.0", notification_text)
        preview.configure(state="disabled")

    def _send_notify(self, res):
        # 保存配置
        self._notify_config["feishu_url"] = self._feishu_entry.get().strip()
        self._notify_config["smtp_server"] = self._smtp_server.get().strip()
        self._notify_config["smtp_port"] = self._smtp_port.get().strip()
        self._notify_config["sender"] = self._sender.get().strip()
        self._notify_config["recipients"] = self._recipients.get().strip()
        self._notify_config["dingtalk_url"] = self._dingtalk_entry.get().strip()
        self._notify_config["wechat_url"] = self._wechat_entry.get().strip()

        notification_text = build_notification_text(res["summary_text"], res["overview"])
        messages: list[str] = []
        webhook = self._notify_config["feishu_url"]
        sender = self._notify_config["sender"]
        pwd = self._mail_pwd.get().strip()
        recip = self._notify_config["recipients"]

        def _worker():
            try:
                if webhook:
                    resp = send_feishu(webhook, notification_text, overview=res["overview"])
                    messages.append(f"飞书发送完成：{resp}")
                dingtalk_url = self._dingtalk_entry.get().strip()
                if dingtalk_url:
                    resp = send_dingtalk(dingtalk_url, notification_text, overview=res["overview"])
                    messages.append(f"钉钉发送完成：{resp}")
                wechat_url = self._wechat_entry.get().strip()
                if wechat_url:
                    resp = send_wechat_work(wechat_url, notification_text)
                    messages.append(f"企业微信发送完成：{resp}")
                if sender and pwd and recip:
                    send_email(
                        smtp_server=self._notify_config["smtp_server"],
                        smtp_port=int(self._notify_config["smtp_port"]),
                        sender=sender, password=pwd,
                        recipients=[r.strip() for r in recip.split(",")],
                        subject=f"自动报表 - {res['value_col']}",
                        html_body=res["html_report"],
                        attachment=res["workbook"],
                        attachment_name=f"报表_{res['value_col']}.xlsx",
                    )
                    messages.append("邮件发送完成（含 Excel 附件）")
                if not messages:
                    messages.append("未配置任何通知渠道")
                self.after(0, lambda: messagebox.showinfo("通知结果", "\n".join(messages)))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("发送失败", str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _save_html(self, res):
        path = filedialog.asksaveasfilename(
            defaultextension=".html", filetypes=[("HTML", "*.html")],
            initialfile=f"报告_{res['value_col']}.html",
        )
        if path:
            Path(path).write_text(res["html_report"], encoding="utf-8")
            messagebox.showinfo("完成", f"HTML 报告已保存至\n{path}")

    def _save_excel(self, res):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"报表_{res['value_col']}.xlsx",
        )
        if path:
            Path(path).write_bytes(res["workbook"])
            messagebox.showinfo("完成", f"Excel 工作簿已保存至\n{path}")


if __name__ == "__main__":
    app = ReportApp()
    app.mainloop()
