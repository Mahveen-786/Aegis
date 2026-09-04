"""
audit_store.py - Audit Log Store for all 4 risk modules.

Every score, flag, threshold, and evidence snapshot is logged here, keyed
by which module produced it. File-backed by default (not in-memory) so the
trail survives a server restart during a demo -- if you genuinely want a
throwaway in-memory store for local testing, pass db_path=":memory:"
explicitly.
"""
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional


class AuditStore:
    def __init__(self, db_path: str = "audit_log.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    score REAL,
                    threshold_applied REAL,
                    flagged INTEGER NOT NULL,
                    evidence_json TEXT NOT NULL,
                    action_recommended TEXT NOT NULL
                )
            """)
            # Model lineage: what produced the numbers currently shown on
            # /dashboard/metrics -- which artifact, trained on which data
            # (by content hash), with which library version and seed, and
            # when. Without this, a metrics screen is only ever "trust me";
            # with it, a reviewer can trace a metric back to a specific
            # persisted model file on disk.
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS model_lineage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trained_at TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    module_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    training_data_hash TEXT NOT NULL,
                    sklearn_version TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    metrics_json TEXT NOT NULL
                )
            """)

    def log_event(self, persona: str, target_id: str, target_type: str, module_name: str,
                  score: Optional[float], threshold: Optional[float], flagged: bool,
                  evidence: dict, action: str):
        with self.conn:
            self.conn.execute("""
                INSERT INTO audit_logs
                (timestamp, persona, target_id, target_type, module_name, score,
                 threshold_applied, flagged, evidence_json, action_recommended)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                persona, target_id, target_type, module_name,
                score, threshold, 1 if flagged else 0,
                json.dumps(evidence), action,
            ))

    def get_logs(self, persona: Optional[str] = None, module: Optional[str] = None,
                 flagged_only: bool = False, limit: int = 100) -> List[Dict]:
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        if persona:
            query += " AND persona = ?"
            params.append(persona)
        if module:
            query += " AND module_name = ?"
            params.append(module)
        if flagged_only:
            query += " AND flagged = 1"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [{
            "id": r["id"],
            "timestamp": r["timestamp"],
            "persona": r["persona"],
            "target_id": r["target_id"],
            "target_type": r["target_type"],
            "module_name": r["module_name"],
            "score": r["score"],
            "threshold_applied": r["threshold_applied"],
            "flagged": bool(r["flagged"]),
            "evidence": json.loads(r["evidence_json"]),
            "action_recommended": r["action_recommended"],
        } for r in rows]

    def log_model_lineage(self, persona: str, module_name: str, model_version: str,
                           artifact_path: str, training_data_hash: str, sklearn_version: str,
                           seed: int, trained_at: str, metrics: dict):
        with self.conn:
            self.conn.execute("""
                INSERT INTO model_lineage
                (trained_at, persona, module_name, model_version, artifact_path,
                 training_data_hash, sklearn_version, seed, metrics_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trained_at, persona, module_name, model_version, artifact_path,
                training_data_hash, sklearn_version, seed, json.dumps(metrics, default=str),
            ))

    def get_latest_lineage(self, persona: str, module_name: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM model_lineage WHERE persona = ? AND module_name = ?
            ORDER BY id DESC LIMIT 1
        """, (persona, module_name))
        r = cursor.fetchone()
        if not r:
            return None
        return {
            "trained_at": r["trained_at"],
            "persona": r["persona"],
            "module_name": r["module_name"],
            "model_version": r["model_version"],
            "artifact_path": r["artifact_path"],
            "training_data_hash": r["training_data_hash"],
            "sklearn_version": r["sklearn_version"],
            "seed": r["seed"],
            "metrics": json.loads(r["metrics_json"]),
        }

    def module_counts(self, persona: Optional[str] = None) -> Dict[str, int]:
        query = "SELECT module_name, COUNT(*) as n FROM audit_logs"
        params = []
        if persona:
            query += " WHERE persona = ?"
            params.append(persona)
        query += " GROUP BY module_name"
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return {r["module_name"]: r["n"] for r in cursor.fetchall()}
