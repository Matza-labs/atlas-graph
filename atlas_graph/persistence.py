"""PostgreSQL persistence for CICDGraph.

Stores and retrieves graphs using psycopg (v3).
For MVP, graphs are stored as JSON blobs. Future: normalized tables.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from atlas_sdk.models.graph import CICDGraph

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS cicd_graphs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    platform TEXT,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""


class GraphStore:
    """PostgreSQL-backed graph persistence.

    Usage:
        store = GraphStore("postgresql://user:pass@localhost/atlas")
        store.connect()
        store.save(graph)
        graph = store.load(graph_id)
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._conn: Any = None

    def connect(self) -> None:
        """Connect to PostgreSQL and ensure table exists."""
        try:
            import psycopg
        except ImportError as e:
            raise ImportError("psycopg is required: pip install 'psycopg[binary]'") from e

        self._conn = psycopg.connect(self._dsn)
        with self._conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        self._conn.commit()
        logger.info("Connected to PostgreSQL, table ensured.")

    def save(self, graph: CICDGraph) -> None:
        """Save or update a graph in the database."""
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")

        data = graph.model_dump(mode="json")
        now = datetime.now(timezone.utc)

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cicd_graphs (id, name, platform, data, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    platform = EXCLUDED.platform,
                    data = EXCLUDED.data,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    graph.id,
                    graph.name,
                    str(graph.platform) if graph.platform else None,
                    json.dumps(data),
                    now,
                    now,
                ),
            )
        self._conn.commit()
        logger.info("Saved graph %s (%s)", graph.id, graph.name)

    def load(self, graph_id: str) -> CICDGraph | None:
        """Load a graph by ID."""
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM cicd_graphs WHERE id = %s",
                (graph_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return CICDGraph.model_validate(data)

    def list_graphs(self, limit: int = 50) -> list[dict[str, Any]]:
        """List stored graphs (metadata only)."""
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, platform, created_at FROM cicd_graphs "
                "ORDER BY updated_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()

        return [
            {"id": r[0], "name": r[1], "platform": r[2], "created_at": str(r[3])}
            for r in rows
        ]

    def delete(self, graph_id: str) -> bool:
        """Delete a graph by ID. Returns True if deleted."""
        if not self._conn:
            raise RuntimeError("Not connected. Call connect() first.")

        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM cicd_graphs WHERE id = %s", (graph_id,))
            deleted = cur.rowcount > 0
        self._conn.commit()
        return deleted

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
