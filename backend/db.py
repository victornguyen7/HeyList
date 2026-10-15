import os
from functools import cache
from typing import Any

from supabase import Client, create_client


@cache
def client() -> Client:
    """The secret key bypasses row level security, so it is read only here, on the server."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set")
    return create_client(url, key)


def _where(query, filters: dict):
    for column, value in filters.items():
        query = query.in_(column, value) if isinstance(value, list) else query.eq(column, value)
    return query


# Rows are list[Any]: supabase types .data as List[JSON], which Pylance won't accept as list[dict].
# The calls the routes use. The tests replace these with an in-memory fake.


def select(table: str, order: str = "created_at", **filters) -> list[Any]:
    """Rows where every filter matches; a list value means "is one of"."""
    if any(value == [] for value in filters.values()):
        return []
    return _where(client().table(table).select("*"), filters).order(order).execute().data


def insert(table: str, rows: list[dict]) -> list[Any]:
    return client().table(table).insert(rows).execute().data if rows else []


def update(table: str, values: dict, **filters) -> list[Any]:
    return _where(client().table(table).update(values), filters).execute().data


def delete(table: str, **filters) -> None:
    _where(client().table(table).delete(), filters).execute()


# Receipt photos live in the private "receipts" bucket; only the backend reads or writes them.


def upload(path: str, data: bytes, content_type: str) -> None:
    client().storage.from_("receipts").upload(path, data, {"content-type": content_type})


def download(path: str) -> bytes:
    return client().storage.from_("receipts").download(path)
