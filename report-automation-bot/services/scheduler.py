"""简单定时调度器 — 基于 threading.Timer"""

from __future__ import annotations

import datetime
import threading


class ReportScheduler:
    def __init__(self, callback, interval_seconds: int = 3600):
        self._callback = callback
        self._interval = interval_seconds
        self._timer: threading.Timer | None = None
        self._running = False
        self._next_run: datetime.datetime | None = None

    def start(self) -> None:
        """启动定时器，立即执行一次 callback，然后每隔 interval 再执行"""
        if self._running:
            return
        self._running = True
        self._execute()

    def stop(self) -> None:
        """停止定时器"""
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._next_run = None

    def is_running(self) -> bool:
        return self._running

    def next_run_time(self) -> str:
        """返回下次执行时间字符串"""
        if self._next_run is None:
            return "未调度"
        return self._next_run.strftime("%Y-%m-%d %H:%M:%S")

    def _execute(self) -> None:
        """执行 callback 并调度下一次"""
        if not self._running:
            return
        self._callback()
        self._next_run = datetime.datetime.now() + datetime.timedelta(seconds=self._interval)
        self._timer = threading.Timer(self._interval, self._execute)
        self._timer.daemon = True
        self._timer.start()
