"""Excel 智能核对助手 - 桌面版 (customtkinter)"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from tkinter import filedialog, ttk, messagebox
from typing import Any

import customtkinter as ctk
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from services.column_mapper import recommend_field_mapping, recommend_key_columns
from services.duplicate_detector import find_duplicates
from services.exporter import build_export_workbook
from services.file_loader import list_sheets, read_dataframe
from services.fuzzy_matcher import build_fuzzy_matches
from services.match_engine import reconcile_dataframes
from services.report_generator import generate_report

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

FILE_TYPES = [("Excel / CSV 文件", "*.csv *.xlsx *.xls"), ("所有文件", "*.*")]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def populate_treeview(tree: ttk.Treeview, df: pd.DataFrame, max_rows: int | None = None) -> None:
    """Fill a Treeview with DataFrame content."""
    tree.delete(*tree.get_children())
    cols = df.columns.tolist()
    tree["columns"] = cols
    tree["show"] = "headings"
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=120, minwidth=60, anchor="w")
    rows = df.head(max_rows) if max_rows else df
    for _, row in rows.iterrows():
        tree.insert("", "end", values=[str(row[c]) for c in cols])


def _make_treeview(parent) -> ttk.Treeview:
    """Create a Treeview with scrollbars inside a CTkFrame."""
    frame = ctk.CTkFrame(parent)
    frame.pack(fill="both", expand=True, padx=4, pady=4)
    vsb = ttk.Scrollbar(frame, orient="vertical")
    hsb = ttk.Scrollbar(frame, orient="horizontal")
    tree = ttk.Treeview(frame, yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.configure(command=tree.yview)
    hsb.configure(command=tree.xview)
    vsb.pack(side="right", fill="y")
    hsb.pack(side="bottom", fill="x")
    tree.pack(side="left", fill="both", expand=True)
    return tree


def _metric_card(parent, label: str, value: Any, row: int, col: int) -> ctk.CTkLabel:
    """Create a metric card (label + big value) in a grid."""
    card = ctk.CTkFrame(parent, corner_radius=8)
    card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
    ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=12)).pack(pady=(8, 0))
    val_label = ctk.CTkLabel(card, text=str(value), font=ctk.CTkFont(size=20, weight="bold"))
    val_label.pack(pady=(0, 8))
    return val_label


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class ExcelReconcileApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("📊 Excel 智能核对助手")
        self.geometry("1200x800")
        self.minsize(900, 600)

        # state
        self.file_a_path: str = ""
        self.file_b_path: str = ""
        self.df_a: pd.DataFrame | None = None
        self.df_b: pd.DataFrame | None = None
        self.result_bundle: dict | None = None
        self.field_pair_widgets: list[tuple[ctk.CTkOptionMenu, ctk.CTkOptionMenu]] = []

        self._build_ui()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        # scrollable main container
        self.main_scroll = ctk.CTkScrollableFrame(self)
        self.main_scroll.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_file_section()
        self._build_preview_section()
        self._build_mapping_section()
        self._build_action_section()
        self._build_result_section()

    # -- file input ---------------------------------------------------------

    def _build_file_section(self) -> None:
        sec = ctk.CTkFrame(self.main_scroll)
        sec.pack(fill="x", padx=4, pady=(4, 2))

        ctk.CTkLabel(sec, text="数据来源", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=8, pady=(6, 2))

        row = ctk.CTkFrame(sec, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=4)

        ctk.CTkButton(row, text="选择文件 A", width=120, command=self._pick_file_a).pack(side="left", padx=(0, 4))
        self.label_a = ctk.CTkLabel(row, text="未选择", anchor="w")
        self.label_a.pack(side="left", padx=(0, 12))

        ctk.CTkButton(row, text="选择文件 B", width=120, command=self._pick_file_b).pack(side="left", padx=(0, 4))
        self.label_b = ctk.CTkLabel(row, text="未选择", anchor="w")
        self.label_b.pack(side="left", padx=(0, 12))

        ctk.CTkButton(row, text="使用示例数据", width=120, command=self._load_sample).pack(side="left")

        # sheet selectors
        sheet_row = ctk.CTkFrame(sec, fg_color="transparent")
        sheet_row.pack(fill="x", padx=8, pady=(0, 6))

        ctk.CTkLabel(sheet_row, text="Sheet A:").pack(side="left")
        self.sheet_a_var = ctk.StringVar(value="")
        self.sheet_a_menu = ctk.CTkOptionMenu(sheet_row, variable=self.sheet_a_var, values=[""], width=160, command=self._on_sheet_change)
        self.sheet_a_menu.pack(side="left", padx=(4, 16))

        ctk.CTkLabel(sheet_row, text="Sheet B:").pack(side="left")
        self.sheet_b_var = ctk.StringVar(value="")
        self.sheet_b_menu = ctk.CTkOptionMenu(sheet_row, variable=self.sheet_b_var, values=[""], width=160, command=self._on_sheet_change)
        self.sheet_b_menu.pack(side="left", padx=4)

    # -- preview ------------------------------------------------------------

    def _build_preview_section(self) -> None:
        sec = ctk.CTkFrame(self.main_scroll)
        sec.pack(fill="x", padx=4, pady=2)
        ctk.CTkLabel(sec, text="数据预览", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=8, pady=(6, 2))

        cols = ctk.CTkFrame(sec, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=4, pady=4)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        left = ctk.CTkFrame(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=2)
        ctk.CTkLabel(left, text="文件 A").pack(anchor="w", padx=4)
        self.preview_tree_a = _make_treeview(left)

        right = ctk.CTkFrame(cols)
        right.grid(row=0, column=1, sticky="nsew", padx=2)
        ctk.CTkLabel(right, text="文件 B").pack(anchor="w", padx=4)
        self.preview_tree_b = _make_treeview(right)

    # -- field mapping ------------------------------------------------------

    def _build_mapping_section(self) -> None:
        sec = ctk.CTkFrame(self.main_scroll)
        sec.pack(fill="x", padx=4, pady=2)
        ctk.CTkLabel(sec, text="字段映射", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=8, pady=(6, 2))

        top_row = ctk.CTkFrame(sec, fg_color="transparent")
        top_row.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(top_row, text="A 表主匹配列:").pack(side="left")
        self.key_a_var = ctk.StringVar()
        self.key_a_menu = ctk.CTkOptionMenu(top_row, variable=self.key_a_var, values=[""], width=160)
        self.key_a_menu.pack(side="left", padx=(4, 16))

        ctk.CTkLabel(top_row, text="B 表主匹配列:").pack(side="left")
        self.key_b_var = ctk.StringVar()
        self.key_b_menu = ctk.CTkOptionMenu(top_row, variable=self.key_b_var, values=[""], width=160)
        self.key_b_menu.pack(side="left", padx=(4, 16))

        ctk.CTkLabel(top_row, text="模糊阈值:").pack(side="left")
        self.threshold_var = ctk.IntVar(value=86)
        self.threshold_slider = ctk.CTkSlider(top_row, from_=60, to=100, number_of_steps=40, variable=self.threshold_var, width=140)
        self.threshold_slider.pack(side="left", padx=4)
        self.threshold_label = ctk.CTkLabel(top_row, text="86")
        self.threshold_label.pack(side="left")
        self.threshold_var.trace_add("write", lambda *_: self.threshold_label.configure(text=str(self.threshold_var.get())))

        self.recommend_label = ctk.CTkLabel(sec, text="", wraplength=800, anchor="w", text_color="gray")
        self.recommend_label.pack(anchor="w", padx=8)

        # pair count
        pair_row = ctk.CTkFrame(sec, fg_color="transparent")
        pair_row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(pair_row, text="比对字段对数量:").pack(side="left")
        self.pair_count_var = ctk.IntVar(value=3)
        self.pair_count_spin = ctk.CTkOptionMenu(pair_row, variable=self.pair_count_var,
                                                   values=[str(i) for i in range(1, 7)],
                                                   width=80, command=self._rebuild_field_pairs)
        self.pair_count_spin.pack(side="left", padx=4)

        self.pairs_frame = ctk.CTkFrame(sec, fg_color="transparent")
        self.pairs_frame.pack(fill="x", padx=8, pady=4)

    # -- action -------------------------------------------------------------

    def _build_action_section(self) -> None:
        sec = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        sec.pack(fill="x", padx=4, pady=4)
        self.run_btn = ctk.CTkButton(sec, text="开始核对", font=ctk.CTkFont(size=14, weight="bold"),
                                      height=40, command=self._run_reconcile)
        self.run_btn.pack(fill="x", padx=8)
        self.status_label = ctk.CTkLabel(sec, text="", text_color="gray")
        self.status_label.pack(pady=2)

    # -- results ------------------------------------------------------------

    def _build_result_section(self) -> None:
        self.result_frame = ctk.CTkFrame(self.main_scroll)
        self.result_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # metrics row
        self.metrics_frame = ctk.CTkFrame(self.result_frame, fg_color="transparent")
        self.metrics_frame.pack(fill="x", padx=4, pady=4)
        for i in range(5):
            self.metrics_frame.columnconfigure(i, weight=1)
        self.metric_labels: list[ctk.CTkLabel] = []

        # tabs
        self.tabview = ctk.CTkTabview(self.result_frame, height=400)
        self.tabview.pack(fill="both", expand=True, padx=4, pady=4)

        tab_names = ["匹配结果", "完全匹配", "A 表缺失于 B", "B 表缺失于 A",
                      "差异明细", "重复记录", "模糊匹配", "核对报告"]
        self.result_trees: dict[str, ttk.Treeview] = {}
        for name in tab_names:
            tab = self.tabview.add(name)
            if name == "重复记录":
                # two side-by-side trees
                dup_frame = ctk.CTkFrame(tab, fg_color="transparent")
                dup_frame.pack(fill="both", expand=True)
                dup_frame.columnconfigure(0, weight=1)
                dup_frame.columnconfigure(1, weight=1)

                left_f = ctk.CTkFrame(dup_frame)
                left_f.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
                ctk.CTkLabel(left_f, text="A 表重复记录").pack(anchor="w", padx=4)
                self.dup_tree_a = _make_treeview(left_f)

                right_f = ctk.CTkFrame(dup_frame)
                right_f.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
                ctk.CTkLabel(right_f, text="B 表重复记录").pack(anchor="w", padx=4)
                self.dup_tree_b = _make_treeview(right_f)
            elif name == "核对报告":
                self.report_text = ctk.CTkTextbox(tab, wrap="word")
                self.report_text.pack(fill="both", expand=True, padx=4, pady=4)
                self.export_btn = ctk.CTkButton(tab, text="导出核对结果工作簿 (.xlsx)", command=self._export_workbook)
                self.export_btn.pack(pady=6)
            else:
                self.result_trees[name] = _make_treeview(tab)

        # hide until results ready
        self.result_frame.pack_forget()

    # -----------------------------------------------------------------------
    # File loading
    # -----------------------------------------------------------------------

    def _pick_file_a(self) -> None:
        path = filedialog.askopenfilename(title="选择文件 A", filetypes=FILE_TYPES)
        if path:
            self.file_a_path = path
            self.label_a.configure(text=Path(path).name)
            self._update_sheets_a()

    def _pick_file_b(self) -> None:
        path = filedialog.askopenfilename(title="选择文件 B", filetypes=FILE_TYPES)
        if path:
            self.file_b_path = path
            self.label_b.configure(text=Path(path).name)
            self._update_sheets_b()

    def _load_sample(self) -> None:
        self.file_a_path = str(_PROJECT_ROOT / "sample_data" / "customers.csv")
        self.file_b_path = str(_PROJECT_ROOT / "sample_data" / "orders.csv")
        self.label_a.configure(text="customers.csv (示例)")
        self.label_b.configure(text="orders.csv (示例)")
        self._update_sheets_a()
        self._update_sheets_b()

    def _update_sheets_a(self) -> None:
        try:
            sheets = list_sheets(self.file_a_path)
            self.sheet_a_menu.configure(values=sheets)
            self.sheet_a_var.set(sheets[0])
            self._load_dataframes()
        except Exception as e:
            messagebox.showerror("错误", f"读取文件 A 失败：{e}")

    def _update_sheets_b(self) -> None:
        try:
            sheets = list_sheets(self.file_b_path)
            self.sheet_b_menu.configure(values=sheets)
            self.sheet_b_var.set(sheets[0])
            self._load_dataframes()
        except Exception as e:
            messagebox.showerror("错误", f"读取文件 B 失败：{e}")

    def _on_sheet_change(self, *_args) -> None:
        self._load_dataframes()

    def _load_dataframes(self) -> None:
        if not self.file_a_path or not self.file_b_path:
            return
        try:
            self.df_a = read_dataframe(self.file_a_path, self.sheet_a_var.get())
            self.df_b = read_dataframe(self.file_b_path, self.sheet_b_var.get())
        except Exception as e:
            messagebox.showerror("错误", f"读取数据失败：{e}")
            return

        populate_treeview(self.preview_tree_a, self.df_a, max_rows=20)
        populate_treeview(self.preview_tree_b, self.df_b, max_rows=20)
        self._update_mapping_options()

    def _update_mapping_options(self) -> None:
        if self.df_a is None or self.df_b is None:
            return
        cols_a = self.df_a.columns.tolist()
        cols_b = self.df_b.columns.tolist()

        # key column recommendations
        key_recs = recommend_key_columns(cols_a, cols_b)
        default_a = key_recs[0][0] if key_recs else cols_a[0]
        default_b = key_recs[0][1] if key_recs else cols_b[0]

        self.key_a_menu.configure(values=cols_a)
        self.key_a_var.set(default_a if default_a in cols_a else cols_a[0])
        self.key_b_menu.configure(values=cols_b)
        self.key_b_var.set(default_b if default_b in cols_b else cols_b[0])

        # field mapping recommendations
        self._recommended_pairs = [p for p in recommend_field_mapping(cols_a, cols_b)
                                    if p[0] != self.key_a_var.get() and p[1] != self.key_b_var.get()]
        if self._recommended_pairs:
            tips = "；".join(f"{l} ↔ {r}（{s}）" for l, r, s, _ in self._recommended_pairs[:5])
            self.recommend_label.configure(text=f"推荐字段映射：{tips}")
        else:
            self.recommend_label.configure(text="")

        max_pairs = max(1, min(6, len(cols_a), len(cols_b)))
        self.pair_count_spin.configure(values=[str(i) for i in range(1, max_pairs + 1)])
        self.pair_count_var.set(min(3, max_pairs))
        self._rebuild_field_pairs(str(self.pair_count_var.get()))

    def _rebuild_field_pairs(self, count_str: str) -> None:
        for w in self.pairs_frame.winfo_children():
            w.destroy()
        self.field_pair_widgets.clear()

        if self.df_a is None or self.df_b is None:
            return

        cols_a = self.df_a.columns.tolist()
        cols_b = self.df_b.columns.tolist()
        recs = getattr(self, "_recommended_pairs", [])
        count = int(count_str)

        for i in range(count):
            row_frame = ctk.CTkFrame(self.pairs_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=1)

            default_l = recs[i][0] if i < len(recs) else cols_a[i % len(cols_a)]
            default_r = recs[i][1] if i < len(recs) else cols_b[i % len(cols_b)]

            ctk.CTkLabel(row_frame, text=f"字段对 {i+1} - A:").pack(side="left")
            var_l = ctk.StringVar(value=default_l if default_l in cols_a else cols_a[0])
            menu_l = ctk.CTkOptionMenu(row_frame, variable=var_l, values=cols_a, width=150)
            menu_l.pack(side="left", padx=(4, 12))

            ctk.CTkLabel(row_frame, text="B:").pack(side="left")
            var_r = ctk.StringVar(value=default_r if default_r in cols_b else cols_b[0])
            menu_r = ctk.CTkOptionMenu(row_frame, variable=var_r, values=cols_b, width=150)
            menu_r.pack(side="left", padx=4)

            self.field_pair_widgets.append((menu_l, menu_r))

    # -----------------------------------------------------------------------
    # Reconcile
    # -----------------------------------------------------------------------

    def _run_reconcile(self) -> None:
        if self.df_a is None or self.df_b is None:
            messagebox.showwarning("提示", "请先加载两份数据文件。")
            return

        self.run_btn.configure(state="disabled")
        self.status_label.configure(text="正在核对，请稍候...")

        key_a = self.key_a_var.get()
        key_b = self.key_b_var.get()
        threshold = self.threshold_var.get()
        compare_pairs = []
        for menu_l, menu_r in self.field_pair_widgets:
            compare_pairs.append((menu_l.cget("variable").get() if hasattr(menu_l, "cget") else menu_l._variable.get(),
                                  menu_r.cget("variable").get() if hasattr(menu_r, "cget") else menu_r._variable.get()))

        def _worker():
            try:
                results = reconcile_dataframes(self.df_a, self.df_b, key_a, key_b, compare_pairs)
                duplicates_a = find_duplicates(self.df_a, key_a)
                duplicates_b = find_duplicates(self.df_b, key_b)
                fuzzy_matches = build_fuzzy_matches(
                    results["missing_in_b"], results["missing_in_a"],
                    key_a, key_b, score_threshold=threshold,
                )
                report_text = generate_report(
                    stats=results["stats"],
                    compare_pairs=compare_pairs,
                    duplicates_a_count=len(duplicates_a),
                    duplicates_b_count=len(duplicates_b),
                    fuzzy_count=len(fuzzy_matches),
                )
                workbook = build_export_workbook(results, duplicates_a, duplicates_b, fuzzy_matches, report_text)
                bundle = {
                    "results": results,
                    "duplicates_a": duplicates_a,
                    "duplicates_b": duplicates_b,
                    "fuzzy_matches": fuzzy_matches,
                    "report_text": report_text,
                    "workbook": workbook,
                }
                self.after(0, lambda: self._on_reconcile_done(bundle))
            except Exception as e:
                self.after(0, lambda: self._on_reconcile_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_reconcile_done(self, bundle: dict) -> None:
        self.result_bundle = bundle
        self.run_btn.configure(state="normal")
        self.status_label.configure(text="核对完成 ✓")
        self._show_results()

    def _on_reconcile_error(self, msg: str) -> None:
        self.run_btn.configure(state="normal")
        self.status_label.configure(text="")
        messagebox.showerror("核对失败", msg)

    # -----------------------------------------------------------------------
    # Display results
    # -----------------------------------------------------------------------

    def _show_results(self) -> None:
        bundle = self.result_bundle
        if not bundle:
            return

        results = bundle["results"]
        stats = results["stats"]

        # show result frame
        self.result_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # metrics
        for w in self.metrics_frame.winfo_children():
            w.destroy()
        self.metric_labels.clear()
        labels = [
            ("A 表记录数", stats["left_rows"]),
            ("B 表记录数", stats["right_rows"]),
            ("完全匹配", stats["exact_match_rows"]),
            ("字段不一致", stats["mismatch_rows"]),
            ("模糊候选", len(bundle["fuzzy_matches"])),
        ]
        for i, (lbl, val) in enumerate(labels):
            self.metric_labels.append(_metric_card(self.metrics_frame, lbl, val, 0, i))

        # tab data
        tab_data = {
            "匹配结果": results["matched_records"],
            "完全匹配": results["exact_matches"],
            "A 表缺失于 B": results["missing_in_b"],
            "B 表缺失于 A": results["missing_in_a"],
            "差异明细": results["mismatch_details"],
            "模糊匹配": bundle["fuzzy_matches"],
        }
        for name, df in tab_data.items():
            if name in self.result_trees:
                populate_treeview(self.result_trees[name], df)

        # duplicates
        populate_treeview(self.dup_tree_a, bundle["duplicates_a"])
        populate_treeview(self.dup_tree_b, bundle["duplicates_b"])

        # report
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", bundle["report_text"])

        self.tabview.set("匹配结果")

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------

    def _export_workbook(self) -> None:
        if not self.result_bundle:
            return
        path = filedialog.asksaveasfilename(
            title="保存核对结果",
            defaultextension=".xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx")],
            initialfile="excel_reconcile_result.xlsx",
        )
        if path:
            with open(path, "wb") as f:
                f.write(self.result_bundle["workbook"])
            messagebox.showinfo("导出成功", f"已保存到：{path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = ExcelReconcileApp()
    app.mainloop()
