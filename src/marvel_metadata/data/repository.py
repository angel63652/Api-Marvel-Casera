"""Data access repositories for Marvel metadata."""

import sqlite3
from typing import Any, Optional

from marvel_metadata.core.types import IssueData, get_role_name


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


class IssueRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_by_id(self, issue_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT id, digital_id AS digitalId, title, issue_number AS issueNumber,
                   description, modified, page_count AS pageCount, detail_url AS detailUrl,
                   series_id AS seriesId, series_name AS seriesName,
                   on_sale_date AS onSaleDate, unlimited_date AS unlimitedDate,
                   year_page AS yearPage, cover_path, cover_extension
            FROM issues WHERE id = ?
            """,
            (issue_id,),
        ).fetchone()
        if not row:
            return None

        data = _row_to_dict(row)
        assert data is not None

        # Attach creators
        creator_rows = self._conn.execute(
            """
            SELECT c.id, c.name, ic.role
            FROM creators c
            JOIN issue_creators ic ON c.id = ic.creator_id
            WHERE ic.issue_id = ?
            ORDER BY c.name
            """,
            (issue_id,),
        ).fetchall()
        data["creators"] = [
            {"id": r["id"], "name": r["name"], "role": r["role"]}
            for r in creator_rows
        ]

        # Build cover sub-object
        if data.get("cover_path"):
            data["cover"] = {
                "path": data.pop("cover_path"),
                "extension": data.pop("cover_extension"),
            }
        else:
            data.pop("cover_path", None)
            data.pop("cover_extension", None)
            data["cover"] = None

        return data

    def list_issues(
        self,
        year: Optional[int] = None,
        series_id: Optional[int] = None,
        available: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        where_parts: list[str] = []
        params: list[Any] = []

        if year is not None:
            where_parts.append("year_page = ?")
            params.append(year)
        if series_id is not None:
            where_parts.append("series_id = ?")
            params.append(series_id)
        if available is True:
            where_parts.append("unlimited_date IS NOT NULL")
        elif available is False:
            where_parts.append("unlimited_date IS NULL")

        where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        total_row = self._conn.execute(
            f"SELECT COUNT(*) FROM issues {where}", params
        ).fetchone()
        total = total_row[0] if total_row else 0

        rows = self._conn.execute(
            f"""
            SELECT id, title, issue_number AS issueNumber, detail_url AS detailUrl,
                   series_id AS seriesId, series_name AS seriesName,
                   on_sale_date AS onSaleDate, unlimited_date AS unlimitedDate,
                   year_page AS yearPage
            FROM issues {where}
            ORDER BY on_sale_date ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

        return _rows_to_dicts(rows), total

    def search(self, q: str, limit: int = 50) -> list[dict[str, Any]]:
        # Try FTS5 first
        try:
            rows = self._conn.execute(
                """
                SELECT i.id, i.title, i.issue_number AS issueNumber,
                       i.detail_url AS detailUrl, i.series_id AS seriesId,
                       i.series_name AS seriesName, i.on_sale_date AS onSaleDate,
                       i.unlimited_date AS unlimitedDate, i.year_page AS yearPage
                FROM issues_fts f
                JOIN issues i ON i.id = f.rowid
                WHERE issues_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (q, limit),
            ).fetchall()
            return _rows_to_dicts(rows)
        except sqlite3.OperationalError:
            pass

        # Fallback: LIKE search
        pattern = f"%{q}%"
        rows = self._conn.execute(
            """
            SELECT id, title, issue_number AS issueNumber, detail_url AS detailUrl,
                   series_id AS seriesId, series_name AS seriesName,
                   on_sale_date AS onSaleDate, unlimited_date AS unlimitedDate,
                   year_page AS yearPage
            FROM issues WHERE title LIKE ?
            ORDER BY on_sale_date ASC
            LIMIT ?
            """,
            (pattern, limit),
        ).fetchall()
        return _rows_to_dicts(rows)

    def get_series_summary(self, series_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT s.id AS seriesId, s.name AS seriesName,
                   COUNT(i.id) AS issueCount,
                   MIN(i.on_sale_date) AS firstIssueDate,
                   MAX(i.on_sale_date) AS lastIssueDate
            FROM series s
            LEFT JOIN issues i ON i.series_id = s.id
            WHERE s.id = ?
            GROUP BY s.id
            """,
            (series_id,),
        ).fetchone()
        return _row_to_dict(row)

    def get_issues_by_series(
        self, series_id: int, limit: int = 200, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        total_row = self._conn.execute(
            "SELECT COUNT(*) FROM issues WHERE series_id = ?", (series_id,)
        ).fetchone()
        total = total_row[0] if total_row else 0

        rows = self._conn.execute(
            """
            SELECT id, title, issue_number AS issueNumber, detail_url AS detailUrl,
                   series_id AS seriesId, series_name AS seriesName,
                   on_sale_date AS onSaleDate, unlimited_date AS unlimitedDate,
                   year_page AS yearPage, cover_path, cover_extension
            FROM issues
            WHERE series_id = ?
            ORDER BY on_sale_date ASC, CAST(issue_number AS REAL) ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (series_id, limit, offset),
        ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            if d.get("cover_path"):
                d["cover"] = {"path": d.pop("cover_path"), "extension": d.pop("cover_extension")}
            else:
                d.pop("cover_path", None)
                d.pop("cover_extension", None)
                d["cover"] = None
            results.append(d)

        return results, total

    def upsert(self, issue: IssueData) -> None:
        series = issue.get("series")
        if series:
            self._conn.execute(
                "INSERT OR IGNORE INTO series(id, name) VALUES(?, ?)",
                (series["id"], series["name"]),
            )

        cover = issue.get("cover", {}) or {}
        dates = issue.get("dates", {}) or {}
        creators_data = issue.get("creators") or []

        self._conn.execute(
            """
            INSERT INTO issues(
                id, digital_id, title, issue_number, description, modified,
                page_count, detail_url, series_id, series_name,
                on_sale_date, unlimited_date, year_page, cover_path, cover_extension
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                digital_id=excluded.digital_id,
                title=excluded.title,
                issue_number=excluded.issue_number,
                description=excluded.description,
                modified=excluded.modified,
                page_count=excluded.page_count,
                detail_url=excluded.detail_url,
                series_id=excluded.series_id,
                series_name=excluded.series_name,
                on_sale_date=excluded.on_sale_date,
                unlimited_date=excluded.unlimited_date,
                year_page=excluded.year_page,
                cover_path=excluded.cover_path,
                cover_extension=excluded.cover_extension
            """,
            (
                issue["id"],
                issue.get("digitalId"),
                issue["title"],
                issue.get("issue"),
                issue.get("description"),
                issue.get("modified"),
                issue.get("pageCount"),
                issue["detailUrl"],
                series["id"] if series else None,
                series["name"] if series else None,
                dates.get("onSale"),
                dates.get("unlimited"),
                issue.get("_year_page"),
                cover.get("path"),
                cover.get("ext"),
            ),
        )

        for creator in creators_data:
            self._conn.execute(
                "INSERT OR IGNORE INTO creators(id, name) VALUES(?, ?)",
                (creator["id"], creator["name"]),
            )
            role = get_role_name(creator["role"])
            self._conn.execute(
                """
                INSERT OR IGNORE INTO issue_creators(issue_id, creator_id, role)
                VALUES(?, ?, ?)
                """,
                (issue["id"], creator["id"], role),
            )


class SeriesRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_series(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        total_row = self._conn.execute("SELECT COUNT(*) FROM series").fetchone()
        total = total_row[0] if total_row else 0

        rows = self._conn.execute(
            """
            SELECT s.id, s.name, COUNT(i.id) AS issueCount
            FROM series s
            LEFT JOIN issues i ON i.series_id = s.id
            GROUP BY s.id
            ORDER BY s.name ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        return _rows_to_dicts(rows), total


class CreatorRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_creators(
        self,
        role: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if role:
            total_row = self._conn.execute(
                """
                SELECT COUNT(DISTINCT c.id) FROM creators c
                JOIN issue_creators ic ON c.id = ic.creator_id
                WHERE ic.role = ?
                """,
                (role,),
            ).fetchone()
            total = total_row[0] if total_row else 0

            rows = self._conn.execute(
                """
                SELECT c.id, c.name, COUNT(DISTINCT ic.issue_id) AS issueCount
                FROM creators c
                JOIN issue_creators ic ON c.id = ic.creator_id
                WHERE ic.role = ?
                GROUP BY c.id
                ORDER BY issueCount DESC, c.name ASC
                LIMIT ? OFFSET ?
                """,
                (role, limit, offset),
            ).fetchall()
        else:
            total_row = self._conn.execute(
                "SELECT COUNT(*) FROM creators"
            ).fetchone()
            total = total_row[0] if total_row else 0

            rows = self._conn.execute(
                """
                SELECT c.id, c.name, COUNT(DISTINCT ic.issue_id) AS issueCount
                FROM creators c
                LEFT JOIN issue_creators ic ON c.id = ic.creator_id
                GROUP BY c.id
                ORDER BY issueCount DESC, c.name ASC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        return _rows_to_dicts(rows), total

    def get_by_id(self, creator_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT id, name FROM creators WHERE id = ?", (creator_id,)
        ).fetchone()
        return _row_to_dict(row)

    def get_details(self, creator_id: int) -> dict[str, Any] | None:
        creator = self.get_by_id(creator_id)
        if not creator:
            return None

        role_rows = self._conn.execute(
            """
            SELECT role, COUNT(DISTINCT issue_id) AS issueCount
            FROM issue_creators
            WHERE creator_id = ?
            GROUP BY role
            ORDER BY issueCount DESC
            """,
            (creator_id,),
        ).fetchall()

        roles = [{"role": r["role"], "issueCount": r["issueCount"]} for r in role_rows]
        total = sum(r["issueCount"] for r in roles)

        return {
            "id": creator["id"],
            "name": creator["name"],
            "roles": roles,
            "totalIssues": total,
        }

    def get_issues(
        self,
        creator_id: int,
        role: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        extra = "AND ic.role = ?" if role else ""
        params_count: list[Any] = [creator_id]
        if role:
            params_count.append(role)

        total_row = self._conn.execute(
            f"SELECT COUNT(*) FROM issue_creators ic WHERE ic.creator_id = ? {extra}",
            params_count,
        ).fetchone()
        total = total_row[0] if total_row else 0

        params_rows: list[Any] = [creator_id]
        if role:
            params_rows.append(role)
        params_rows += [limit, offset]

        rows = self._conn.execute(
            f"""
            SELECT i.id, i.title, COALESCE(i.issue_number, '') AS issueNumber,
                   COALESCE(i.series_id, 0) AS seriesId,
                   COALESCE(i.series_name, '') AS seriesName,
                   ic.role, i.on_sale_date AS onSaleDate,
                   COALESCE(i.year_page, 0) AS yearPage
            FROM issues i
            JOIN issue_creators ic ON i.id = ic.issue_id
            WHERE ic.creator_id = ? {extra}
            ORDER BY i.on_sale_date ASC, i.id ASC
            LIMIT ? OFFSET ?
            """,
            params_rows,
        ).fetchall()

        return _rows_to_dicts(rows), total


class ReadingOrderRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_all(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT ro.id, ro.slug, ro.name, ro.description, ro.is_curated,
                   ro.created_at, COUNT(roi.id) AS item_count
            FROM reading_orders ro
            LEFT JOIN reading_order_items roi ON roi.reading_order_id = ro.id
            GROUP BY ro.id
            ORDER BY ro.is_curated DESC, ro.name ASC
            """
        ).fetchall()
        return _rows_to_dicts(rows)

    def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT id, slug, name, description, is_curated, created_at FROM reading_orders WHERE slug = ?",
            (slug,),
        ).fetchone()
        if not row:
            return None

        data = dict(row)
        items = self._conn.execute(
            """
            SELECT roi.id, roi.position, roi.issue_id, roi.issue_title, roi.note,
                   i.detail_url, i.cover_path, i.cover_extension,
                   i.series_name, i.on_sale_date
            FROM reading_order_items roi
            LEFT JOIN issues i ON i.id = roi.issue_id
            WHERE roi.reading_order_id = ?
            ORDER BY roi.position ASC
            """,
            (data["id"],),
        ).fetchall()
        data["items"] = _rows_to_dicts(items)
        return data

    def create(
        self,
        slug: str,
        name: str,
        description: str,
        is_curated: bool,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        cursor = self._conn.execute(
            "INSERT INTO reading_orders(slug, name, description, is_curated) VALUES(?, ?, ?, ?)",
            (slug, name, description, 1 if is_curated else 0),
        )
        order_id = cursor.lastrowid
        for idx, item in enumerate(items):
            self._conn.execute(
                """
                INSERT INTO reading_order_items(reading_order_id, position, issue_id, issue_title, note)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    idx,
                    item.get("issue_id"),
                    item["issue_title"],
                    item.get("note", ""),
                ),
            )
        self._conn.commit()
        result = self.get_by_slug(slug)
        assert result is not None
        return result

    def delete(self, slug: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM reading_orders WHERE slug = ?", (slug,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def upsert_curated(
        self,
        slug: str,
        name: str,
        description: str,
        items: list[dict[str, Any]],
    ) -> None:
        """Insert curated reading order only if it doesn't exist yet."""
        exists = self._conn.execute(
            "SELECT 1 FROM reading_orders WHERE slug = ?", (slug,)
        ).fetchone()
        if exists:
            return
        self.create(slug=slug, name=name, description=description, is_curated=True, items=items)

    def link_issues_by_title(self) -> int:
        """Try to match unlinked items to issues by title. Returns count of newly linked items."""
        unlinked = self._conn.execute(
            "SELECT id, issue_title FROM reading_order_items WHERE issue_id IS NULL"
        ).fetchall()

        count = 0
        for item in unlinked:
            row = self._conn.execute(
                "SELECT id FROM issues WHERE title = ? LIMIT 1",
                (item["issue_title"],),
            ).fetchone()
            if row:
                self._conn.execute(
                    "UPDATE reading_order_items SET issue_id = ? WHERE id = ?",
                    (row["id"], item["id"]),
                )
                count += 1

        if count:
            self._conn.commit()
        return count
