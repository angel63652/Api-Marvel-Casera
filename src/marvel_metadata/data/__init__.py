"""Data access layer — SQLite schema, repositories, and FTS."""

from marvel_metadata.data.schema import get_connection, init_database, SchemaManager
from marvel_metadata.data.repository import IssueRepository, SeriesRepository, CreatorRepository
from marvel_metadata.data.search import setup_fts

__all__ = [
    "get_connection",
    "init_database",
    "SchemaManager",
    "IssueRepository",
    "SeriesRepository",
    "CreatorRepository",
    "setup_fts",
]
