import os
from functools import cache

from supabase import Client, create_client


@cache
def client() -> Client:
    """The secret key bypasses row level security, so it is read only here, on the server."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set")
    return create_client(url, key)
