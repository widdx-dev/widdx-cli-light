"""Database query tool — SQLite and external databases."""

import json
import logging
import sqlite3
import subprocess
from pathlib import Path

logger = logging.getLogger("widdx.tools.db_query")


def _query_sqlite(db_path: str, query: str, max_rows: int = 50, format: str = "text") -> str:
    """Execute a query against a SQLite database."""
    p = Path(db_path).resolve()
    if not p.exists():
        return f"Database not found: {db_path}"

    try:
        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query)

        if query.strip().upper().startswith(("SELECT", "PRAGMA", "EXPLAIN")):
            rows = cur.fetchmany(max_rows + 1)
            columns = [d[0] for d in cur.description] if cur.description else []
            has_more = len(rows) > max_rows
            rows = rows[:max_rows]

            if format == "json":
                result = {
                    "columns": columns,
                    "rows": [dict(r) for r in rows],
                    "total": len(rows),
                    "has_more": has_more,
                }
                return json.dumps(result, indent=2, ensure_ascii=False, default=str)

            buf = [f"📊 SQLite: {db_path} ({len(rows)} rows)", ""]
            if columns:
                col_header = " | ".join(f"{c:<20}" for c in columns)
                buf.append(col_header)
                buf.append("-" * len(col_header))
            for row in rows:
                vals = [str(row[c])[:20] for c in columns]
                buf.append(" | ".join(f"{v:<20}" for v in vals))
            if has_more:
                buf.append("... and more (use limit to control)")
            conn.close()
            return "\n".join(buf)
        else:
            conn.commit()
            affected = cur.rowcount
            conn.close()
            return f"✅ Query executed. {affected} row(s) affected."

    except sqlite3.Error as e:
        return f"SQLite error: {e}"
    except Exception as e:
        return f"Error: {e}"


def _query_postgres(conn_str: str, query: str, max_rows: int = 50) -> str:
    """Execute a query against PostgreSQL using psql."""
    try:
        cmd = ["psql", conn_str, "-c", query, "--csv", "-t", "-A"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return f"PostgreSQL error: {r.stderr[:500]}"
        return r.stdout[-3000:] or "Query executed successfully."
    except FileNotFoundError:
        return "psql not installed. Install PostgreSQL client."
    except subprocess.TimeoutExpired:
        return "Query timed out"
    except Exception as e:
        return f"Error: {e}"


def _show_tables(db_path: str) -> str:
    """List all tables in a SQLite database."""
    return _query_sqlite(db_path, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")


def _describe_table(db_path: str, table: str) -> str:
    """Describe a table's schema."""
    return _query_sqlite(db_path, f"PRAGMA table_info({table})")


def _db_query(db_path: str | None = None, query: str = "",
              type: str = "sqlite", conn_str: str | None = None,
              action: str = "query", table: str | None = None,
              max_rows: int = 50, format: str = "text") -> str:
    """Query a database (SQLite or PostgreSQL)."""
    if type == "sqlite":
        if not db_path:
            return "db_path required for SQLite"
        if action == "tables":
            return _show_tables(db_path)
        if action == "describe":
            if not table:
                return "table name required"
            return _describe_table(db_path, table)
        return _query_sqlite(db_path, query, max_rows, format)

    elif type == "postgres":
        if not conn_str:
            return "conn_str required for PostgreSQL"
        if action == "tables":
            return _query_postgres(conn_str, "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        return _query_postgres(conn_str, query, max_rows)

    return f"Unsupported database type: {type}. Use: sqlite, postgres"
