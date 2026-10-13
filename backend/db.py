import os
from functools import cache
from typing import cast

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


def _rows(query) -> list[dict]:
    # supabase types a row as any JSON value; a table row is always an object.
    return cast(list[dict], query.execute().data)


# The four calls the routes use. The tests replace these with an in-memory fake.


def select(table: str, order: str = "created_at", **filters) -> list[dict]:
    """Rows where every filter matches; a list value means "is one of"."""
    if any(value == [] for value in filters.values()):
        return []
    return _rows(_where(client().table(table).select("*"), filters).order(order))


def insert(table: str, rows: list[dict]) -> list[dict]:
    return _rows(client().table(table).insert(rows)) if rows else []


def update(table: str, values: dict, **filters) -> list[dict]:
    return _rows(_where(client().table(table).update(values), filters))


def delete(table: str, **filters) -> None:
    _where(client().table(table).delete(), filters).execute()


# Receipt photos, in the private "receipts" bucket.


def upload(path: str, data: bytes, content_type: str) -> None:
    client().storage.from_("receipts").upload(path, data, {"content-type": content_type})


def download(path: str) -> bytes:
    return client().storage.from_("receipts").download(path)
