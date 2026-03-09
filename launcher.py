"""办公自动化工具箱 — 统一启动器"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import customtkinter as ctk

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

ROOT = Path(__file__).resolve().parent


class LauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🧰 办公自动化工具箱")
        self.geometry("600x500")
        self.resizable(False, False)

        ctk.CTkLabel(
            self, text="办公自动化工具箱",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(pady=(30, 10))

        ctk.CTkLabel(
            self, text="选择要启动的工具",
            font=ctk.CTkFont(size=14), text_color="gray",
        ).pack(pady=(0, 20))

        tools = [
            {
                "icon": "🌐",
                "name": "网页信息智能采集平台",
                "desc": "关键词搜索 / URL 直采 / 多引擎并发 / 图片下载 / 历史记录",
                "path": ROOT / "web-data-collector" / "desktop_app.py",
            },
            {
                "icon": "📊",
                "name": "Excel 智能核对助手",
                "desc": "复合主键匹配 / 模糊匹配 / 数值容差 / 可视化 / 格式化导出",
                "path": ROOT / "excel-reconcile-assistant" / "desktop_app.py",
            },
            {
                "icon": "📬",
                "name": "自动报表生成与通知机器人",
                "desc": "多聚合方式 / 交叉分析 / 飞书钉钉企微通知 / 定时任务",
                "path": ROOT / "report-automation-bot" / "desktop_app.py",
            },
        ]

        for tool in tools:
            self._make_tool_card(tool)

        ctk.CTkLabel(
            self, text="v2.0 — 开源于 GitHub",
            font=ctk.CTkFont(size=11), text_color="gray",
        ).pack(side="bottom", pady=10)

    def _make_tool_card(self, tool: dict):
        card = ctk.CTkFrame(self, corner_radius=12)
        card.pack(fill="x", padx=30, pady=6)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            left, text=f"{tool['icon']}  {tool['name']}",
            font=ctk.CTkFont(size=15, weight="bold"), anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            left, text=tool["desc"],
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w",
        ).pack(anchor="w")

        ctk.CTkButton(
            row, text="启动", width=70, height=32,
            command=lambda p=tool["path"]: self._launch(p),
        ).pack(side="right", padx=(8, 0))

    def _launch(self, script_path: Path):
        subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
        )


if __name__ == "__main__":
    app = LauncherApp()
    app.mainloop()
