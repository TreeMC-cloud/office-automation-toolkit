"""采集历史存储 — SQLite 本地持久化"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "history.db"


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            category TEXT DEFAULT '',
            result_count INTEGER DEFAULT 0,
            image_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            results_json TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    return conn


def save_history(keyword: str, category: str, records: list[dict]) -> int:
    """保存一次采集记录，返回 id"""
    conn = _get_conn()
    image_count = sum(1 for r in records if r.get("image_url"))
    # 存储时去掉过大的字段
    slim = []
    for r in records:
        slim.append({k: (v[:500] if isinstance(v, str) else v) for k, v in r.items()})
    conn.execute(
        "INSERT INTO history (keyword, category, result_count, image_count, created_at, results_json) VALUES (?,?,?,?,?,?)",
        (keyword, category, len(records), image_count, datetime.now().isoformat(), json.dumps(slim, ensure_ascii=False)),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return row_id


def list_history(limit: int = 50) -> list[dict]:
    """返回历史列表（不含 results_json）"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, keyword, category, result_count, image_count, created_at FROM history ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "keyword": r[1], "category": r[2], "result_count": r[3],
         "image_count": r[4], "created_at": r[5]}
        for r in rows
    ]


def load_history_results(history_id: int) -> list[dict]:
    """加载某次采集的完整结果"""
    conn = _get_conn()
    row = conn.execute("SELECT results_json FROM history WHERE id=?", (history_id,)).fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return []


def delete_history(history_id: int) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM history WHERE id=?", (history_id,))
    conn.commit()
    conn.close()
