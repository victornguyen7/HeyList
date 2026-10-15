import os
from functools import cache

from ollama import Client

MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:31b")


@cache
def client() -> Client:
    key = os.environ.get("OLLAMA_API_KEY")
    if not key:
        raise RuntimeError("OLLAMA_API_KEY must be set")
    return Client(host="https://ollama.com", headers={"Authorization": f"Bearer {key}"})


def chat(messages: list[dict]) -> str:
    return client().chat(model=MODEL, messages=messages).message.content or ""
