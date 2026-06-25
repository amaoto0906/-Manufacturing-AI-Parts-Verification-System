"""SQLite リポジトリ。

品番マスタ・登録画像・照合ログ・フィードバックを永続化する。本番では
PostgreSQL（database/schema_postgres.sql）へ移行する想定だが、API は本
リポジトリ・インタフェースに依存させ、差し替えを容易にしている。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

_SCHEMA = Path(__file__).with_name("schema_sqlite.sql")


class Repository:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.init_db()

    # 接続はスレッドローカル（FastAPI のスレッドプール対応）
    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.db_path, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys = ON")
            self._local.conn = c
        return c

    def init_db(self) -> None:
        with open(_SCHEMA, encoding="utf-8") as f:
            self._conn().executescript(f.read())
        self._conn().commit()

    # --- 品番マスタ ---
    def upsert_part(self, part_no: str, part_name: Optional[str] = None,
                    category: Optional[str] = None, material: Optional[str] = None,
                    group_id: Optional[int] = None, status: str = "active",
                    accept_threshold: Optional[float] = None,
                    margin_threshold: Optional[float] = None) -> int:
        c = self._conn()
        c.execute(
            """INSERT INTO parts(part_no, part_name, category, material, group_id,
                                 status, accept_threshold, margin_threshold)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(part_no) DO UPDATE SET
                 part_name=COALESCE(excluded.part_name, parts.part_name),
                 category=COALESCE(excluded.category, parts.category),
                 material=COALESCE(excluded.material, parts.material),
                 group_id=COALESCE(excluded.group_id, parts.group_id),
                 status=excluded.status,
                 accept_threshold=excluded.accept_threshold,
                 margin_threshold=excluded.margin_threshold,
                 updated_at=datetime('now')""",
            (part_no, part_name, category, material, group_id, status,
             accept_threshold, margin_threshold),
        )
        c.commit()
        row = c.execute("SELECT id FROM parts WHERE part_no=?", (part_no,)).fetchone()
        return int(row["id"])

    def get_part(self, part_no: str) -> Optional[dict]:
        row = self._conn().execute(
            "SELECT * FROM parts WHERE part_no=?", (part_no,)).fetchone()
        return dict(row) if row else None

    def list_parts(self, limit: int = 1000) -> List[dict]:
        rows = self._conn().execute(
            "SELECT * FROM parts ORDER BY part_no LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def part_thresholds(self) -> dict:
        """品番別しきい値の辞書（NULL を除く）。"""
        rows = self._conn().execute(
            "SELECT part_no, accept_threshold, margin_threshold FROM parts"
        ).fetchall()
        out = {}
        for r in rows:
            d = {}
            if r["accept_threshold"] is not None:
                d["accept_threshold"] = r["accept_threshold"]
            if r["margin_threshold"] is not None:
                d["margin_threshold"] = r["margin_threshold"]
            if d:
                out[r["part_no"]] = d
        return out

    # --- 登録画像 ---
    def add_part_image(self, part_id: int, image_path: str,
                       capture_condition_id: Optional[int] = None) -> int:
        c = self._conn()
        cur = c.execute(
            "INSERT INTO part_images(part_id, image_path, capture_condition_id) VALUES(?,?,?)",
            (part_id, image_path, capture_condition_id))
        c.commit()
        return int(cur.lastrowid)

    # --- 照合ログ ---
    def log_inspection(self, result: dict, image_path: Optional[str] = None,
                       operator_id: Optional[str] = None,
                       line_id: Optional[str] = None) -> int:
        c = self._conn()
        cur = c.execute(
            """INSERT INTO inspection_logs(
                 expected_part_no, predicted_part_no, result, action, confidence,
                 margin, top_candidates_json, quality_json, reason, image_path,
                 operator_id, line_id, processing_time_ms)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (result.get("expected_part_no"), result.get("predicted_part_no"),
             result["result"], result["action"], result.get("confidence"),
             result.get("margin"),
             json.dumps(result.get("top_candidates", []), ensure_ascii=False),
             json.dumps(result.get("quality", {}), ensure_ascii=False),
             result.get("reason"), image_path, operator_id, line_id,
             result.get("processing_time_ms")))
        c.commit()
        return int(cur.lastrowid)

    def list_inspections(self, limit: int = 100, result: Optional[str] = None) -> List[dict]:
        if result:
            rows = self._conn().execute(
                "SELECT * FROM inspection_logs WHERE result=? ORDER BY id DESC LIMIT ?",
                (result, limit)).fetchall()
        else:
            rows = self._conn().execute(
                "SELECT * FROM inspection_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # --- フィードバック ---
    def add_feedback(self, inspection_log_id: Optional[int], correct_part_no: Optional[str],
                     feedback_type: str, comment: Optional[str] = None,
                     created_by: Optional[str] = None) -> int:
        c = self._conn()
        cur = c.execute(
            """INSERT INTO feedback_logs(inspection_log_id, correct_part_no,
                 feedback_type, comment, created_by) VALUES(?,?,?,?,?)""",
            (inspection_log_id, correct_part_no, feedback_type, comment, created_by))
        c.commit()
        return int(cur.lastrowid)

    def list_feedback(self, limit: int = 100) -> List[dict]:
        rows = self._conn().execute(
            "SELECT * FROM feedback_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # --- 統計（ダッシュボード用） ---
    def stats(self) -> dict:
        c = self._conn()
        n_parts = c.execute("SELECT COUNT(*) n FROM parts").fetchone()["n"]
        n_logs = c.execute("SELECT COUNT(*) n FROM inspection_logs").fetchone()["n"]
        by_result = {r["result"]: r["n"] for r in c.execute(
            "SELECT result, COUNT(*) n FROM inspection_logs GROUP BY result").fetchall()}
        avg_ms = c.execute(
            "SELECT AVG(processing_time_ms) a FROM inspection_logs").fetchone()["a"]
        return {
            "n_parts": n_parts,
            "n_inspections": n_logs,
            "by_result": by_result,
            "avg_processing_ms": round(avg_ms, 2) if avg_ms else None,
        }
