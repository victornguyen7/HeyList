import os
from functools import cache
from typing import Any

import httpx
from supabase import Client, ClientOptions, create_client


@cache
def client() -> Client:
    """The secret key bypasses row level security, so it is read only here, on the server."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set")
    # HTTP/1.1, not supabase's default HTTP/2: route handlers run on many threads, and one shared HTTP/2
    # connection read from several at once failed with ReadError (EAGAIN), so lists loaded together came back 500.
    return create_client(url, key, ClientOptions(httpx_client=httpx.Client(timeout=30)))


def _where(query, filters: dict):
    for column, value in filters.items():
        if isinstance(value, list):
            query = query.in_(column, value)
        elif value is None:
            query = query.is_(column, "null")
        else:
            query = query.eq(column, value)
    return query


def user(token: str) -> dict | None:
    """The logged-in user for a Supabase access token ({"id", "name"}), or None if the token is bad or expired."""
    try:
        response = client().auth.get_user(token)
    except AuthError:
        return None
    if not response or not response.user:
        return None
    return {"id": response.user.id, "name": (response.user.user_metadata or {}).get("name")}


# Rows are list[Any]: supabase types .data as List[JSON], which Pylance won't accept as list[dict].
# The calls the routes use. The tests replace these with an in-memory fake.


def select(table: str, order: str = "created_at", **filters) -> list[Any]:
    """Rows where every filter matches; a list value means "is one of", None means "is null"."""
    if any(value == [] for value in filters.values()):
        return []
    return _where(client().table(table).select("*"), filters).order(order).execute().data


def insert(table: str, rows: list[dict]) -> list[Any]:
    return client().table(table).insert(rows).execute().data if rows else []


def update(table: str, values: dict, **filters) -> list[Any]:
    """The rows it changed. One UPDATE, so a filter like checked_at=None claims a row atomically."""
    return _where(client().table(table).update(values), filters).execute().data


def delete(table: str, **filters) -> None:
    _where(client().table(table).delete(), filters).execute()


# Receipt photos live in the private "receipts" bucket; only the backend reads or writes them.


def upload(path: str, data: bytes, content_type: str) -> None:
    client().storage.from_("receipts").upload(path, data, {"content-type": content_type})


def download(path: str) -> bytes:
    return client().storage.from_("receipts").download(path)
