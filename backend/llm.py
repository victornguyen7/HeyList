import os
from functools import cache

from ollama import Client


@cache
def client() -> Client:
    key = os.environ.get("OLLAMA_API_KEY")
    if not key:
        raise RuntimeError("OLLAMA_API_KEY must be set")
    return Client(host="https://ollama.com", headers={"Authorization": f"Bearer {key}"})


def chat(messages: list[dict]) -> str:
    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        raise RuntimeError("OLLAMA_MODEL must be set")
    return client().chat(model=model, messages=messages).message.content or ""
