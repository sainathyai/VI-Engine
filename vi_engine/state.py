"""Track processed URLs locally (SQLite) — narrows Phase 1 without cloud."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_urls (
                url TEXT PRIMARY KEY,
                processed_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                domain TEXT,
                source TEXT,
                title TEXT,
                url TEXT,
                source_url TEXT,
                pub_date TEXT,
                description TEXT,
                query TEXT,
                status TEXT DEFAULT 'discovered',
                created_at TEXT DEFAULT (datetime('now')),
                approved_at TEXT,
                summarized_at TEXT,
                output_path TEXT,
                decision_note TEXT,
                summary TEXT,
                score INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                category TEXT,
                content_type TEXT
            )
            """
        )
        conn.commit()

        # Migrations for existing DBs
        cols = {row[1] for row in conn.execute("PRAGMA table_info(candidates)").fetchall()}
        for col, ctype in [("summary", "TEXT"), ("score", "INTEGER DEFAULT 0"), ("comments", "INTEGER DEFAULT 0"), ("category", "TEXT"), ("content_type", "TEXT")]:
            if col not in cols:
                conn.execute(f"ALTER TABLE candidates ADD COLUMN {col} {ctype}")
                conn.commit()

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS newsletters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                body TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT DEFAULT (datetime('now')),
                published_at TEXT,
                output_path TEXT,
                voice TEXT,
                industry TEXT
            )
            """
        )
        conn.commit()

        # Migrations for existing newsletter DBs
        nl_cols = {row[1] for row in conn.execute("PRAGMA table_info(newsletters)").fetchall()}
        for col in ["voice", "industry"]:
            if col not in nl_cols:
                conn.execute(f"ALTER TABLE newsletters ADD COLUMN {col} TEXT")
                conn.commit()

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS newsletter_items (
                newsletter_id INTEGER REFERENCES newsletters(id),
                candidate_id INTEGER REFERENCES candidates(id),
                position INTEGER DEFAULT 0,
                PRIMARY KEY (newsletter_id, candidate_id)
            )
            """
        )
        conn.commit()

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS publish_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                newsletter_id INTEGER REFERENCES newsletters(id),
                platform TEXT,
                status TEXT DEFAULT 'pending',
                scheduled_at TEXT,
                published_at TEXT,
                publish_url TEXT
            )
            """
        )
        conn.commit()


def already_seen(path: Path, url: str) -> bool:
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT 1 FROM seen_urls WHERE url = ?", (url,)).fetchone()
    return row is not None


def mark_seen(path: Path, url: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_urls(url) VALUES (?)",
            (url,),
        )
        conn.commit()


def add_candidate(path: Path, *, key: str, domain: str, source: str, title: str, url: str, source_url: str, pub_date: str, description: str, query: str | None = None, score: int = 0, comments: int = 0) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO candidates (
                key, domain, source, title, url, source_url, pub_date, description, query, status, score, comments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
            """,
            (key, domain, source, title, url, source_url, pub_date, description, query, score, comments),
        )
        conn.commit()


_VALID_SORT = {"score": "score DESC, created_at DESC", "date": "created_at DESC", "title": "title ASC"}


def list_candidates(
    path: Path,
    *,
    status: str = "discovered",
    limit: int = 50,
    category: str | None = None,
    source: str | None = None,
    pipeline: str | None = None,
    sort_by: str = "score",
) -> list[dict[str, Any]]:
    order = _VALID_SORT.get(sort_by, _VALID_SORT["score"])
    where_clauses = ["status = ?"]
    params: list[Any] = [status]
    if category:
        where_clauses.append("category = ?")
        params.append(category)
    if source:
        where_clauses.append("source = ?")
        params.append(source)
    if pipeline:
        where_clauses.append("domain = ?")
        params.append(pipeline)
    params.append(limit)
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                id, key, source, title, url, source_url, pub_date, description, query, status, created_at, output_path, summarized_at, summary, score, comments, category, content_type
            FROM candidates
            WHERE {' AND '.join(where_clauses)}
            ORDER BY {order}
            LIMIT ?
            """,
            params,
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r[0],
                "key": r[1],
                "source": r[2],
                "title": r[3],
                "url": r[4],
                "source_url": r[5],
                "pub_date": r[6],
                "description": r[7],
                "query": r[8],
                "status": r[9],
                "created_at": r[10],
                "output_path": r[11],
                "summarized_at": r[12],
                "summary": r[13],
                "score": r[14] or 0,
                "comments": r[15] or 0,
                "category": r[16] or "",
                "content_type": r[17] or "",
            }
        )
    return out


def get_candidate(path: Path, *, candidate_id: int) -> dict[str, Any] | None:
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            """
            SELECT
                id, key, domain, source, title, url, source_url, pub_date, description, query, status, output_path, summarized_at, summary, category, content_type
            FROM candidates
            WHERE id = ?
            """,
            (candidate_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "key": row[1],
        "domain": row[2],
        "source": row[3],
        "title": row[4],
        "url": row[5],
        "source_url": row[6],
        "pub_date": row[7],
        "description": row[8],
        "query": row[9],
        "status": row[10],
        "output_path": row[11],
        "summarized_at": row[12],
        "summary": row[13],
        "category": row[14] or "",
        "content_type": row[15] or "",
    }


def set_candidate_tags(path: Path, *, candidate_id: int, category: str, content_type: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE candidates SET category = ?, content_type = ? WHERE id = ?", (category, content_type, candidate_id))
        conn.commit()


def set_candidate_description(path: Path, *, candidate_id: int, description: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE candidates SET description = ? WHERE id = ?", (description, candidate_id))
        conn.commit()


def set_candidate_summary(path: Path, *, candidate_id: int, summary: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE candidates SET summary = ? WHERE id = ?", (summary, candidate_id))
        conn.commit()


def set_candidate_status(path: Path, *, candidate_id: int, status: str, note: str | None = None) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            UPDATE candidates
            SET status = ?,
                decision_note = COALESCE(?, decision_note),
                approved_at = CASE WHEN ? = 'approved' THEN datetime('now') ELSE approved_at END,
                summarized_at = CASE WHEN ? = 'summarized' THEN datetime('now') ELSE summarized_at END
            WHERE id = ?
            """,
            (status, note, status, status, candidate_id),
        )
        conn.commit()


def set_candidate_output(path: Path, *, candidate_id: int, output_path: str, status: str = "summarized") -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            UPDATE candidates
            SET output_path = ?,
                status = ?,
                summarized_at = CASE WHEN ? = 'summarized' THEN datetime('now') ELSE summarized_at END
            WHERE id = ?
            """,
            (output_path, status, status, candidate_id),
        )
        conn.commit()


# --------------- Newsletter helpers ---------------

def create_newsletter(path: Path, *, title: str, body: str, candidate_ids: list[int], output_path: str = "", voice: str = "", industry: str = "") -> int:
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO newsletters (title, body, output_path, voice, industry) VALUES (?, ?, ?, ?, ?)",
            (title, body, output_path, voice or None, industry or None),
        )
        nl_id = cur.lastrowid
        for pos, cid in enumerate(candidate_ids):
            conn.execute(
                "INSERT OR IGNORE INTO newsletter_items (newsletter_id, candidate_id, position) VALUES (?, ?, ?)",
                (nl_id, cid, pos),
            )
        conn.commit()
    return nl_id


def list_newsletters(path: Path, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as conn:
        if status:
            rows = conn.execute(
                "SELECT id, title, status, created_at, published_at, output_path FROM newsletters WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, status, created_at, published_at, output_path FROM newsletters ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [
        {"id": r[0], "title": r[1], "status": r[2], "created_at": r[3], "published_at": r[4], "output_path": r[5]}
        for r in rows
    ]


def get_newsletter(path: Path, *, newsletter_id: int) -> dict[str, Any] | None:
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT id, title, body, status, created_at, published_at, output_path, voice, industry FROM newsletters WHERE id = ?",
            (newsletter_id,),
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "title": row[1], "body": row[2], "status": row[3], "created_at": row[4], "published_at": row[5], "output_path": row[6], "voice": row[7] or "", "industry": row[8] or ""}


def set_newsletter_skills(path: Path, *, newsletter_id: int, voice: str, industry: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE newsletters SET voice = ?, industry = ? WHERE id = ?",
            (voice or None, industry or None, newsletter_id),
        )
        conn.commit()


def get_newsletter_candidates(path: Path, *, newsletter_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.url, c.source, c.pub_date, c.output_path, ni.position
            FROM newsletter_items ni
            JOIN candidates c ON c.id = ni.candidate_id
            WHERE ni.newsletter_id = ?
            ORDER BY ni.position
            """,
            (newsletter_id,),
        ).fetchall()
    return [
        {"id": r[0], "title": r[1], "url": r[2], "source": r[3], "pub_date": r[4], "output_path": r[5], "position": r[6]}
        for r in rows
    ]


def set_newsletter_status(path: Path, *, newsletter_id: int, status: str) -> None:
    with sqlite3.connect(path) as conn:
        extra = ", published_at = datetime('now')" if status == "published" else ""
        conn.execute(
            f"UPDATE newsletters SET status = ?{extra} WHERE id = ?",
            (status, newsletter_id),
        )
        conn.commit()


def add_publish_target(path: Path, *, newsletter_id: int, platform: str) -> int:
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO publish_targets (newsletter_id, platform) VALUES (?, ?)",
            (newsletter_id, platform),
        )
        conn.commit()
    return cur.lastrowid


def list_publish_targets(path: Path, *, newsletter_id: int) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT id, newsletter_id, platform, status, scheduled_at, published_at, publish_url FROM publish_targets WHERE newsletter_id = ? ORDER BY id",
            (newsletter_id,),
        ).fetchall()
    return [
        {"id": r[0], "newsletter_id": r[1], "platform": r[2], "status": r[3], "scheduled_at": r[4], "published_at": r[5], "publish_url": r[6]}
        for r in rows
    ]


def set_publish_target_status(path: Path, *, target_id: int, status: str, publish_url: str = "") -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            UPDATE publish_targets
            SET status = ?,
                publish_url = COALESCE(NULLIF(?, ''), publish_url),
                published_at = CASE WHEN ? = 'published' THEN datetime('now') ELSE published_at END
            WHERE id = ?
            """,
            (status, publish_url, status, target_id),
        )
        conn.commit()


def candidate_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT status, COUNT(*) FROM candidates GROUP BY status").fetchall()
    return {r[0]: r[1] for r in rows}


def candidate_filter_options(path: Path) -> dict[str, list[str]]:
    """Return distinct non-empty categories, sources, and pipelines for filter dropdowns."""
    with sqlite3.connect(path) as conn:
        cats = [r[0] for r in conn.execute(
            "SELECT DISTINCT category FROM candidates WHERE category IS NOT NULL AND category != '' ORDER BY category"
        ).fetchall()]
        sources = [r[0] for r in conn.execute(
            "SELECT DISTINCT source FROM candidates WHERE source IS NOT NULL ORDER BY source"
        ).fetchall()]
        pipelines = [r[0] for r in conn.execute(
            "SELECT DISTINCT domain FROM candidates WHERE domain IS NOT NULL AND domain != '' ORDER BY domain"
        ).fetchall()]
    return {"categories": cats, "sources": sources, "pipelines": pipelines}
