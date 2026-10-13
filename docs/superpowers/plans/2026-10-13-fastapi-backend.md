# FastAPI Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the PayPal order endpoints and the sample list from Next.js route handlers into a Python FastAPI service, with identical behaviour, and leave Next.js as the frontend only.

**Architecture:** A flat `backend/` folder holds three Python modules that mirror the three TypeScript ones. The browser keeps calling same-origin `/api/*`; a Next.js rewrite forwards those requests to FastAPI. The TypeScript backend is deleted first, in Task 1, before any Python is written; the rewrite is turned on last, in Task 4. Between the two, `/api/*` answers `404`, which breaks nothing because no page calls it yet.

**Tech Stack:** Python 3.13, FastAPI 0.143.0, uvicorn 0.54.0, httpx 0.28.1, stdlib `unittest`; Next.js 16.4.0 (rewrites); PayPal Orders API v2 (sandbox).

**Spec:** `docs/superpowers/specs/2026-10-13-fastapi-backend-design.md`

## Global Constraints

- Backend dependencies are exactly `fastapi`, `uvicorn[standard]`, `httpx`, pinned. No PayPal SDK, no pytest, no other package.
- Every error body is `{"error": "<CODE>"}`. Use `JSONResponse`, never `HTTPException`. No Pydantic model on the `POST /api/orders` body.
- Status codes and error codes are unchanged: `400 INVALID_ITEMS`, `400 INVALID_ORDER_ID`, `422 INSTRUMENT_DECLINED`, `502 PAYPAL_ERROR`.
- Sandbox only: API base `https://api-m.sandbox.paypal.com`.
- The browser never sends an amount. Totals are computed in the backend from item IDs, in integer cents.
- Every POST to PayPal carries a `PayPal-Request-Id`. Capture uses the order ID as its key.
- `PAYPAL_CLIENT_SECRET` is read only in `backend/paypal.py`.
- The proxy default is `http://127.0.0.1:8000`, not `localhost`.
- This Next.js version differs from older ones. Read `node_modules/next/dist/docs/01-app/03-api-reference/05-config/01-next-config-js/rewrites.md` before changing the rewrite in Task 4.
- Backend commands run from `backend/`; everything else from the repo root. Work stays on the current `check_out` branch, one commit per task.
- End every commit message with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the commands below pass it as a second `-m`).
- `next dev` rewrites `AGENTS.md`. If it shows as modified at commit time, add it to that commit.

## Review Focus

Inputs and failures the spec implies but does not spell out, most likely first. Each is pinned by a check in the task named.

1. An item ID that is not a string (a nested list or a number in the JSON) — must return `400 INVALID_ITEMS`, not crash with `500` (Task 1 unit test, Task 3 route test).
2. The backend is not running while Next.js is — the browser must get an error status from the proxy, not a hang or a `200` (Task 4, Step 4).
3. PayPal answers `429` twice in a row — one retry with the same request ID, then an error; never a loop, never a second order (Task 2 tests).
4. PayPal answers an error with a body that is not JSON (an HTML `503`) — must become `502 PAYPAL_ERROR`, not an unhandled exception (Task 2 test).
5. An order ID in the URL that is lowercase, too long, or contains an encoded slash — must never reach PayPal (Task 3 route test, Task 4 Step 3).

## File Structure

| File | Responsibility |
|---|---|
| `backend/requirements.txt` | The three pinned dependencies. |
| `backend/sample_list.py` | The hardcoded list and `total_cents`. No imports. |
| `backend/test_sample_list.py` | Unit test for `total_cents`. |
| `backend/paypal.py` | PayPal REST client: token cache, `create_order`, `capture_order`, `PayPalError`. |
| `backend/test_paypal.py` | PayPal client tests against a fake PayPal. |
| `backend/main.py` | The FastAPI app: three routes, and the mapping from failures to the error contract. |
| `backend/test_main.py` | Route tests with the PayPal client mocked. |
| `next.config.ts` | The `/api/:path*` rewrite. |

Deleted in Task 1: `app/api/`, `lib/`, and the `test` script in `package.json`.

---

### Task 1: Backend scaffold and sample list

**Files:**
- Create: `backend/requirements.txt`, `backend/sample_list.py`
- Test: `backend/test_sample_list.py`
- Modify: `.gitignore`, `package.json`
- Delete: `app/api/orders/route.ts`, `app/api/orders/[id]/capture/route.ts`, `lib/paypal.ts`, `lib/sample-list.ts`, `lib/sample-list.test.mjs`

**Interfaces:**
- Produces:
  - `ITEMS: list[dict]` — each item is `{"id": str, "name": str, "priceCents": int}`. The keys are the JSON contract, so they stay camelCase.
  - `total_cents(item_ids) -> int` — raises `ValueError` unless `item_ids` is a non-empty list of distinct known string IDs.

- [ ] **Step 1: Commit what exists as a checkpoint**

The TypeScript backend has never been committed. The next step deletes it, so commit it first; otherwise the deletion cannot be undone.

```bash
git add .gitignore AGENTS.md package.json .env.example app/api lib
git commit -m "feat: add PayPal order create and capture routes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git add docs/superpowers/specs/2026-10-13-fastapi-backend-design.md docs/superpowers/plans/2026-10-13-fastapi-backend.md
git commit -m "docs: add FastAPI backend spec and plan" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Run: `git status --short`
Expected: no output.

- [ ] **Step 1b: Delete the TypeScript backend**

The TypeScript backend goes before the Python one is written.

```bash
git rm -r app/api lib
```

In `package.json`, replace:

```json
    "lint": "eslint",
    "test": "node --test \"lib/**/*.test.mjs\""
```

with:

```json
    "lint": "eslint"
```

Run: `ls app lib 2>&1`
Expected: `app` lists `favicon.ico globals.css layout.tsx page.tsx`; `lib` reports `No such file or directory`.

```bash
git add package.json
git commit -m "refactor: remove the TypeScript backend" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Ignore the Python build files**

Append to `.gitignore`:

```
# python
backend/.venv/
__pycache__/
```

- [ ] **Step 3: Add the requirements and create the virtual environment**

Create `backend/requirements.txt`:

```
fastapi==0.143.0
uvicorn[standard]==0.54.0
httpx==0.28.1
```

`uvicorn[standard]` is deliberate: the extra includes the loader behind the `--env-file` flag used in Task 4.

Run from the repo root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

Expected: ends with `Successfully installed ...` listing `fastapi-0.143.0`, `httpx-0.28.1`, and `uvicorn-0.54.0`.

Run: `git status --short`
Expected: `.gitignore` modified and `backend/` untracked; nothing under `backend/.venv/` is listed.

- [ ] **Step 4: Write the failing test**

Create `backend/test_sample_list.py`:

```python
import unittest

from sample_list import ITEMS, total_cents


class TotalCentsTest(unittest.TestCase):
    def test_sums_the_selected_items_in_cents(self):
        self.assertEqual(total_cents(["sunscreen", "adapter"]), 899 + 1499)
        self.assertEqual(
            total_cents([item["id"] for item in ITEMS]),
            sum(item["priceCents"] for item in ITEMS),
        )

    def test_rejects_selections_that_must_never_be_charged(self):
        for item_ids, message in [
            ([], "at least one"),
            (["sunscreen", "nope"], "unknown"),
            (["sunscreen", "sunscreen"], "twice"),
            ("sunscreen", "at least one"),
            (None, "at least one"),
            ([["sunscreen"]], "unknown"),
            ([1], "unknown"),
        ]:
            with self.subTest(item_ids=item_ids):
                with self.assertRaisesRegex(ValueError, message):
                    total_cents(item_ids)
```

- [ ] **Step 5: Run the test to verify it fails**

Run from `backend/`: `.venv/bin/python -m unittest test_sample_list`
Expected: FAIL with `ModuleNotFoundError: No module named 'sample_list'`.

- [ ] **Step 6: Write the implementation**

Create `backend/sample_list.py`:

```python
ITEMS = [
    {"id": "sunscreen", "name": "Sunscreen", "priceCents": 899},
    {"id": "adapter", "name": "Travel adapter", "priceCents": 1499},
    {"id": "toothbrush", "name": "Toothbrush", "priceCents": 349},
]

_PRICES = {item["id"]: item["priceCents"] for item in ITEMS}


def total_cents(item_ids) -> int:
    if not isinstance(item_ids, list) or not item_ids:
        raise ValueError("Select at least one item")
    seen = set()
    for item_id in item_ids:
        # The str check comes first: JSON can hold a nested list, which cannot be looked up in a dict.
        if not isinstance(item_id, str) or item_id not in _PRICES:
            raise ValueError(f"unknown item: {item_id}")
        if item_id in seen:
            raise ValueError("An item was selected twice")
        seen.add(item_id)
    return sum(_PRICES[item_id] for item_id in item_ids)
```

- [ ] **Step 7: Run the test to verify it passes**

Run from `backend/`: `.venv/bin/python -m unittest test_sample_list`
Expected: `Ran 2 tests` and `OK`.

- [ ] **Step 8: Commit**

```bash
git add .gitignore backend/requirements.txt backend/sample_list.py backend/test_sample_list.py
git commit -m "feat: port the sample list to Python" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: PayPal client

**Files:**
- Create: `backend/paypal.py`
- Test: `backend/test_paypal.py`

**Interfaces:**
- Consumes: `ITEMS`, `total_cents(item_ids) -> int` from `backend/sample_list.py`.
- Produces:
  - `class PayPalError(Exception)` with `status: int` and `issue: str | None`.
  - `async create_order(item_ids: list[str]) -> str` — returns the PayPal order ID.
  - `async capture_order(order_id: str) -> dict` — returns `{"orderId": str, "status": str}`.
  - Module attributes the tests replace: `client` (the shared `httpx.AsyncClient`), `_token` (the token cache), `log`, `BASE_URL`.
  - Both functions raise `RuntimeError` when a credential is missing, and let `httpx` errors (timeouts, connection failures) propagate. Callers treat anything that is not a `PayPalError` as unexpected.

- [ ] **Step 1: Write the failing tests**

The tests never touch the network. `httpx.MockTransport` stands in for PayPal, and `asyncio.sleep` is replaced so the retry test does not wait.

Create `backend/test_paypal.py`:

```python
import json
import os
import unittest
from unittest import mock

import httpx

import paypal


class PayPalTest(unittest.IsolatedAsyncioTestCase):
    def fake_paypal(self, *order_responses):
        """Points the client at a fake PayPal that answers order POSTs with the given responses, in turn."""
        self.requests = []
        replies = iter(order_responses)

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            if request.url.path == "/v1/oauth2/token":
                return httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
            return next(replies)

        fake = httpx.AsyncClient(base_url=paypal.BASE_URL, transport=httpx.MockTransport(handler))
        for patch in (
            mock.patch.object(paypal, "client", fake),
            mock.patch.object(paypal, "_token", None),
            mock.patch.dict(os.environ, {"PAYPAL_CLIENT_ID": "id", "PAYPAL_CLIENT_SECRET": "secret"}),
            mock.patch("asyncio.sleep", mock.AsyncMock()),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def paths(self):
        return [request.url.path for request in self.requests]

    async def test_create_order_sends_the_server_side_total_and_reuses_the_token(self):
        self.fake_paypal(
            httpx.Response(201, json={"id": "ORDER1"}),
            httpx.Response(201, json={"id": "ORDER2"}),
        )

        self.assertEqual(await paypal.create_order(["sunscreen", "adapter"]), "ORDER1")
        self.assertEqual(await paypal.create_order(["toothbrush"]), "ORDER2")

        self.assertEqual(
            self.paths(), ["/v1/oauth2/token", "/v2/checkout/orders", "/v2/checkout/orders"]
        )
        order = self.requests[1]
        self.assertEqual(order.headers["authorization"], "Bearer token-1")
        self.assertTrue(order.headers["paypal-request-id"])
        unit = json.loads(order.content)["purchase_units"][0]
        self.assertEqual(unit["amount"]["value"], "23.98")
        self.assertEqual(unit["amount"]["breakdown"]["item_total"]["value"], "23.98")
        self.assertEqual([item["unit_amount"]["value"] for item in unit["items"]], ["8.99", "14.99"])

    async def test_capture_retries_once_on_429_with_the_same_request_id(self):
        self.fake_paypal(
            httpx.Response(429, headers={"retry-after": "60"}),
            httpx.Response(201, json={"id": "ORDER1", "status": "COMPLETED"}),
        )

        self.assertEqual(
            await paypal.capture_order("ORDER1"), {"orderId": "ORDER1", "status": "COMPLETED"}
        )

        paypal.asyncio.sleep.assert_awaited_once_with(5)
        self.assertEqual(self.paths()[1:], ["/v2/checkout/orders/ORDER1/capture"] * 2)
        self.assertEqual(
            [request.headers["paypal-request-id"] for request in self.requests[1:]],
            ["ORDER1", "ORDER1"],
        )

    async def test_a_second_429_is_an_error_not_another_retry(self):
        self.fake_paypal(httpx.Response(429), httpx.Response(429))

        with self.assertLogs(paypal.log, "ERROR"), self.assertRaises(paypal.PayPalError) as raised:
            await paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.status, 429)
        self.assertEqual(len(self.requests), 3)

    async def test_a_paypal_failure_carries_the_issue_and_logs_the_debug_id(self):
        self.fake_paypal(
            httpx.Response(
                422,
                json={
                    "name": "UNPROCESSABLE_ENTITY",
                    "details": [{"issue": "INSTRUMENT_DECLINED"}],
                    "debug_id": "abc123",
                },
            )
        )

        with self.assertLogs(paypal.log, "ERROR") as logs, self.assertRaises(paypal.PayPalError) as raised:
            await paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.issue, "INSTRUMENT_DECLINED")
        self.assertIn("abc123", logs.output[0])

    async def test_a_non_json_error_body_is_still_a_paypal_error(self):
        self.fake_paypal(httpx.Response(503, text="<html>down</html>"))

        with self.assertLogs(paypal.log, "ERROR"), self.assertRaises(paypal.PayPalError) as raised:
            await paypal.capture_order("ORDER1")

        self.assertEqual(raised.exception.status, 503)
        self.assertIsNone(raised.exception.issue)

    async def test_missing_credentials_fail_before_any_request(self):
        self.fake_paypal()
        with mock.patch.dict(os.environ, {"PAYPAL_CLIENT_SECRET": ""}):
            with self.assertRaisesRegex(RuntimeError, "must be set"):
                await paypal.create_order(["sunscreen"])
        self.assertEqual(self.requests, [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `.venv/bin/python -m unittest test_paypal`
Expected: FAIL with `ModuleNotFoundError: No module named 'paypal'`.

- [ ] **Step 3: Write the implementation**

Create `backend/paypal.py`:

```python
import asyncio
import logging
import os
import time
import uuid
from urllib.parse import quote

import httpx

from sample_list import ITEMS, total_cents

BASE_URL = "https://api-m.sandbox.paypal.com"

log = logging.getLogger(__name__)
# httpx defaults to a 5 second timeout, which a slow capture can exceed.
client = httpx.AsyncClient(base_url=BASE_URL, timeout=30)


class PayPalError(Exception):
    def __init__(self, status: int, issue: str | None):
        super().__init__(f"PayPal request failed: {status} {issue or ''}")
        self.status = status
        self.issue = issue


def _to_error(response: httpx.Response) -> PayPalError:
    """Logs the debug_id PayPal support asks for, then returns an error the routes can map."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    details = body.get("details") or [{}]
    issue = details[0].get("issue") or body.get("name") or body.get("error")
    log.error(
        "PayPal error status=%s issue=%s debug_id=%s",
        response.status_code,
        issue,
        body.get("debug_id") or response.headers.get("paypal-debug-id"),
    )
    return PayPalError(response.status_code, issue)


_token: tuple[str, float] | None = None  # (value, expires at, on the monotonic clock)


async def _access_token() -> str:
    global _token
    if _token and time.monotonic() < _token[1]:
        return _token[0]

    client_id = os.environ.get("PAYPAL_CLIENT_ID")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")

    response = await client.post(
        "/v1/oauth2/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
    )
    if not response.is_success:
        raise _to_error(response)

    data = response.json()
    # Refresh two minutes early so a token never expires mid-request.
    _token = (data["access_token"], time.monotonic() + data["expires_in"] - 120)
    return _token[0]


async def _post(path: str, request_id: str, body: dict, retried: bool = False) -> dict:
    response = await client.post(
        path,
        json=body,
        headers={
            "Authorization": f"Bearer {await _access_token()}",
            "PayPal-Request-Id": request_id,
        },
    )

    if response.status_code == 429 and not retried:
        try:
            seconds = int(response.headers.get("retry-after", ""))
        except ValueError:
            seconds = 1
        await asyncio.sleep(min(seconds or 1, 5))
        return await _post(path, request_id, body, True)
    if not response.is_success:
        raise _to_error(response)
    return response.json()


def _usd(cents: int) -> dict:
    return {"currency_code": "USD", "value": f"{cents // 100}.{cents % 100:02d}"}


async def create_order(item_ids: list[str]) -> str:
    total = total_cents(item_ids)
    items = [item for item in ITEMS if item["id"] in item_ids]

    order = await _post(
        "/v2/checkout/orders",
        str(uuid.uuid4()),
        {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {**_usd(total), "breakdown": {"item_total": _usd(total)}},
                    "items": [
                        {
                            "name": item["name"],
                            "quantity": "1",
                            "unit_amount": _usd(item["priceCents"]),
                        }
                        for item in items
                    ],
                }
            ],
        },
    )
    return order["id"]


async def capture_order(order_id: str) -> dict:
    # The order ID is the idempotency key, so a repeated capture returns the first result.
    order = await _post(f"/v2/checkout/orders/{quote(order_id, safe='')}/capture", order_id, {})
    return {"orderId": order["id"], "status": order["status"]}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run from `backend/`: `.venv/bin/python -m unittest test_paypal`
Expected: `Ran 6 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
git add backend/paypal.py backend/test_paypal.py
git commit -m "feat: port the PayPal client to Python" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: FastAPI app and routes

**Files:**
- Create: `backend/main.py`
- Test: `backend/test_main.py`

**Interfaces:**
- Consumes:
  - `ITEMS`, `total_cents(item_ids) -> int` from `backend/sample_list.py`.
  - `paypal.create_order(item_ids: list[str]) -> str`, `paypal.capture_order(order_id: str) -> dict`, `paypal.PayPalError` (with `.issue`) from `backend/paypal.py`. Call them as `paypal.create_order(...)`, through the module, so the tests can replace them.
- Produces:
  - `app` — the FastAPI instance, importable as `main:app`.
  - `GET /api/items` → `200 [{"id", "name", "priceCents"}, ...]`.
  - `POST /api/orders` body `{"itemIds": [...]}` → `200 {"orderId"}` | `400 {"error": "INVALID_ITEMS"}` | `502 {"error": "PAYPAL_ERROR"}`.
  - `POST /api/orders/{order_id}/capture` → `200 {"orderId", "status"}` | `400 {"error": "INVALID_ORDER_ID"}` | `422 {"error": "INSTRUMENT_DECLINED"}` | `502 {"error": "PAYPAL_ERROR"}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/test_main.py`:

```python
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import paypal
from main import app
from sample_list import ITEMS

client = TestClient(app)


class ItemsTest(unittest.TestCase):
    def test_lists_the_items(self):
        response = client.get("/api/items")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ITEMS)


class CreateOrderTest(unittest.TestCase):
    def test_bad_input_is_400_and_never_reaches_paypal(self):
        bodies = [
            '{"itemIds": []}',
            '{"itemIds": ["sunscreen", "nope"]}',
            '{"itemIds": ["sunscreen", "sunscreen"]}',
            '{"itemIds": "sunscreen"}',
            '{"itemIds": [["sunscreen"]]}',
            "{}",
            "[]",
            "null",
            "not json",
            "",
        ]
        with mock.patch.object(paypal, "create_order") as create_order:
            for body in bodies:
                with self.subTest(body=body):
                    response = client.post(
                        "/api/orders", content=body, headers={"Content-Type": "application/json"}
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json(), {"error": "INVALID_ITEMS"})
        create_order.assert_not_called()

    def test_returns_the_order_id(self):
        with mock.patch.object(paypal, "create_order", mock.AsyncMock(return_value="ORDER1")) as create_order:
            response = client.post("/api/orders", json={"itemIds": ["sunscreen"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"orderId": "ORDER1"})
        create_order.assert_awaited_once_with(["sunscreen"])

    def test_a_paypal_failure_is_a_generic_502(self):
        failure = paypal.PayPalError(500, "INTERNAL_SERVER_ERROR")
        with mock.patch.object(paypal, "create_order", mock.AsyncMock(side_effect=failure)):
            response = client.post("/api/orders", json={"itemIds": ["sunscreen"]})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "PAYPAL_ERROR"})

    def test_an_unexpected_failure_is_logged_and_a_generic_502(self):
        failure = RuntimeError("no credentials")
        with mock.patch.object(paypal, "create_order", mock.AsyncMock(side_effect=failure)):
            with self.assertLogs("main", "ERROR"):
                response = client.post("/api/orders", json={"itemIds": ["sunscreen"]})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "PAYPAL_ERROR"})


class CaptureOrderTest(unittest.TestCase):
    def test_malformed_order_id_is_400_and_never_reaches_paypal(self):
        with mock.patch.object(paypal, "capture_order") as capture_order:
            for order_id in ("abc", "ORDER-1", "A" * 37):
                with self.subTest(order_id=order_id):
                    response = client.post(f"/api/orders/{order_id}/capture")
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json(), {"error": "INVALID_ORDER_ID"})
        capture_order.assert_not_called()

    def test_returns_the_capture_result(self):
        result = {"orderId": "ORDER1", "status": "COMPLETED"}
        with mock.patch.object(paypal, "capture_order", mock.AsyncMock(return_value=result)):
            response = client.post("/api/orders/ORDER1/capture")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)

    def test_maps_paypal_failures_to_the_error_contract(self):
        for issue, status, code in [
            ("INSTRUMENT_DECLINED", 422, "INSTRUMENT_DECLINED"),
            ("ORDER_NOT_APPROVED", 502, "PAYPAL_ERROR"),
        ]:
            with self.subTest(issue=issue):
                failure = paypal.PayPalError(422, issue)
                with mock.patch.object(paypal, "capture_order", mock.AsyncMock(side_effect=failure)):
                    response = client.post("/api/orders/ORDER1/capture")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"error": code})

    def test_an_unexpected_failure_is_logged_and_a_generic_502(self):
        failure = RuntimeError("no credentials")
        with mock.patch.object(paypal, "capture_order", mock.AsyncMock(side_effect=failure)):
            with self.assertLogs("main", "ERROR"):
                response = client.post("/api/orders/ORDER1/capture")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "PAYPAL_ERROR"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `.venv/bin/python -m unittest test_main`
Expected: FAIL with `ModuleNotFoundError: No module named 'main'`.

- [ ] **Step 3: Write the implementation**

Create `backend/main.py`:

```python
import logging
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import paypal
from sample_list import ITEMS, total_cents

log = logging.getLogger(__name__)
app = FastAPI()


def error(code: str, status: int) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


@app.get("/api/items")
def list_items():
    return ITEMS


@app.post("/api/orders")
async def create_order(request: Request):
    # The body is read by hand: a Pydantic model would answer bad input with 422, not 400 INVALID_ITEMS.
    try:
        item_ids = (await request.json())["itemIds"]
        total_cents(item_ids)
    except (ValueError, KeyError, TypeError):
        return error("INVALID_ITEMS", 400)

    try:
        return {"orderId": await paypal.create_order(item_ids)}
    except Exception as exc:
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Create order failed")
        return error("PAYPAL_ERROR", 502)


@app.post("/api/orders/{order_id}/capture")
async def capture_order(order_id: str):
    if not re.fullmatch(r"[A-Z0-9]{1,36}", order_id):
        return error("INVALID_ORDER_ID", 400)

    try:
        return await paypal.capture_order(order_id)
    except Exception as exc:
        if isinstance(exc, paypal.PayPalError) and exc.issue == "INSTRUMENT_DECLINED":
            return error("INSTRUMENT_DECLINED", 422)
        if not isinstance(exc, paypal.PayPalError):
            log.exception("Capture order failed")
        return error("PAYPAL_ERROR", 502)
```

- [ ] **Step 4: Run the whole suite**

Run from `backend/`: `.venv/bin/python -m unittest`
Expected: `Ran 17 tests` and `OK`. A `StarletteDeprecationWarning` about `httpx` and `starlette.testclient` is printed first; it is expected and needs no action.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/test_main.py
git commit -m "feat: add FastAPI routes for items and orders" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Switch Next.js over to the backend

**Files:**
- Modify: `next.config.ts`, `.env.example`

**Interfaces:**
- Consumes: the three routes served by `main:app` (Task 3), on `http://127.0.0.1:8000`.
- Produces: the same three routes on the Next.js origin, `http://localhost:3000/api/*`. `BACKEND_URL` overrides the destination.

**Prerequisite:** `.env.local` at the repo root holds real sandbox credentials. Steps 1–4 work without them; Step 5 does not.

- [ ] **Step 1: Add the rewrite**

In `next.config.ts`, replace:

```ts
  cacheComponents: true,
  partialPrefetching: true,
```

with:

```ts
  cacheComponents: true,
  partialPrefetching: true,
  // All server-side logic lives in the FastAPI service in backend/.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
```

- [ ] **Step 2: Document `BACKEND_URL`**

Append to `.env.example`:

```

# Where Next.js sends /api/* requests. Leave unset locally; the default is http://127.0.0.1:8000.
# BACKEND_URL=
```

- [ ] **Step 3: Check the proxy**

Start both servers in the background.

From `backend/`: `.venv/bin/uvicorn main:app --reload --env-file ../.env.local`
Expected: `Uvicorn running on http://127.0.0.1:8000`.

From the repo root: `npm run dev`
Expected: `Ready` on `http://localhost:3000`.

Then:

```bash
curl -s localhost:3000/api/items
curl -s -w " %{http_code}\n" -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d '{"itemIds":[]}'
curl -s -w " %{http_code}\n" -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d 'not json'
curl -s -w " %{http_code}\n" -X POST localhost:3000/api/orders/abc/capture
curl -s -o /dev/null -w "%{http_code}\n" -X POST "localhost:3000/api/orders/bad%2Fid/capture"
```

Expected, in order:

1. The three items as JSON, starting `[{"id":"sunscreen","name":"Sunscreen","priceCents":899}`.
2. `{"error":"INVALID_ITEMS"} 400`
3. `{"error":"INVALID_ITEMS"} 400`
4. `{"error":"INVALID_ORDER_ID"} 400`
5. `404` (FastAPI treats the encoded slash as a path separator, so no route matches). `400` is also fine. `200` or `502` is a failure: it means the ID reached PayPal.

Each request also appears in the uvicorn log, which proves it went through the proxy.

- [ ] **Step 4: Check what happens when the backend is down**

Stop uvicorn, then:

```bash
curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 localhost:3000/api/items
```

Expected: a `5xx` status within the ten seconds. A `200`, or `000` (curl timed out), is a failure.

Start uvicorn again with the command from Step 3.

- [ ] **Step 5: Sandbox run through the proxy (needs `.env.local`)**

```bash
curl -s -X POST localhost:3000/api/orders -H "Content-Type: application/json" -d '{"itemIds":["sunscreen","adapter"]}'
```

Expected: `{"orderId":"<17 characters>"}`.

Confirm the order with the PayPal MCP tool `get_order` using that ID. Expected: status `CREATED`, amount `23.98` USD, two items.

Capture it before any buyer has approved:

```bash
curl -s -w " %{http_code}\n" -X POST localhost:3000/api/orders/<orderId>/capture
```

Expected: `{"error":"PAYPAL_ERROR"} 502`. The uvicorn log shows `PayPal error status=422 issue=ORDER_NOT_APPROVED debug_id=<id>`.

The next part needs a person, because the buyer approval cannot be scripted. Open `https://www.sandbox.paypal.com/checkoutnow?token=<orderId>`, log in as a sandbox **personal** account (from https://developer.paypal.com/dashboard/accounts), and approve. Then run the capture command again.

Expected: `{"orderId":"<orderId>","status":"COMPLETED"} 200`, and `get_order` reports `COMPLETED`.

- [ ] **Step 6: Lint and build**

Run: `npm run lint && npm run build`
Expected: lint reports no errors; the build succeeds and its route list has no `/api` entries.

- [ ] **Step 7: Commit**

```bash
git add next.config.ts .env.example
git commit -m "feat: proxy /api to the FastAPI backend" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Run: `git status --short`
Expected: no output (or only `AGENTS.md`, which `next dev` rewrites; if so, amend it into this commit).

---

### Task 5: Docs

**Files:**
- Modify: `README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/CHANGELOG.md`, `docs/superpowers/specs/2026-10-12-paypal-checkout-design.md`, `docs/superpowers/plans/2026-10-12-paypal-checkout.md`

**Interfaces:**
- Consumes: the file names and routes from Tasks 1–4.
- Produces: docs that match the code. The checkout plan's Task 3 (the checkout page, not yet built) is rewritten to fetch items from `GET /api/items` instead of importing `lib/sample-list`.

Each step below is a set of exact replacements. If a "replace" block is not found verbatim, stop and report it rather than guessing.

- [ ] **Step 1: `README.md`**

Replace:

```markdown
- **App:** Next.js website, mobile-first (native app later)
```

with:

```markdown
- **Frontend:** Next.js website, mobile-first (native app later)
- **Backend:** FastAPI (Python) in `backend/`; Next.js proxies `/api/*` to it
```

Replace:

````markdown
```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Other scripts: `npm run build`, `npm run start`, `npm run lint`.
````

with:

````markdown
Copy `.env.example` to `.env.local` and fill in the PayPal sandbox credentials. Both servers read that file.

Set up once:

```bash
npm install
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

Then run the two servers, each in its own terminal:

```bash
cd backend && .venv/bin/uvicorn main:app --reload --env-file ../.env.local
```

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Backend tests: `cd backend && .venv/bin/python -m unittest`. Other scripts: `npm run build`, `npm run start`, `npm run lint`.
````

- [ ] **Step 2: `docs/ARCHITECTURE.md`**

Replace:

```markdown
Planned architecture. The repository is currently an unmodified Next.js scaffold; nothing below is implemented yet (see [CHANGELOG.md](CHANGELOG.md)).
```

with:

```markdown
Planned architecture. Only the PayPal order endpoints are implemented, in `backend/` (see [CHANGELOG.md](CHANGELOG.md)); everything else below is still planned.
```

Replace:

```markdown
| App | Next.js website, mobile-first so it works in phone browsers (native app later) |
```

with:

```markdown
| Frontend | Next.js website, mobile-first so it works in phone browsers (native app later) |
| Backend | FastAPI (Python) — all server-side logic. The browser calls same-origin `/api/*`, which Next.js rewrites to it |
```

Replace:

```markdown
| Hosting | Render |
```

with:

```markdown
| Hosting | Render — two web services, one for Next.js and one for FastAPI |
```

Replace:

```markdown
Currently installed (from `package.json`): Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5.
```

with:

```markdown
Currently installed: Next.js 16.4.0, React 19.3.0, Tailwind CSS 4, TypeScript 5 (from `package.json`); FastAPI 0.143.0, uvicorn 0.54.0, httpx 0.28.1 on Python 3.13 (from `backend/requirements.txt`).
```

Replace:

```
                      v                                   v
                         Next.js app on Render
          |                     |                        |
```

with:

```
                      v                                   v
              Next.js frontend on Render (pages; proxies /api/*)
                                |
                                v
                  FastAPI backend on Render (Python)
          |                     |                        |
```

- [ ] **Step 3: `docs/DECISIONS.md`**

Replace:

```markdown
| 14 | Use Next.js for the app | — |
```

with:

```markdown
| 14 | Use Next.js for the app (narrowed to the frontend by 20) | — |
```

Append after the row for decision 19:

```markdown
| 20 | Next.js is the frontend only; all server-side logic runs in a FastAPI (Python) service, which the browser reaches through a Next.js rewrite of `/api/*` | — |
```

- [ ] **Step 4: `docs/CHANGELOG.md`**

Insert above `## 2026-10-12`:

```markdown
## 2026-10-13

- Added the backend as a FastAPI (Python) service in `backend/`: PayPal order create and capture (Orders API v2, sandbox) and the sample item list at `GET /api/items`. Next.js proxies `/api/*` to it.
- Removed the TypeScript route handlers and `lib/` that the Python service replaces.

```

- [ ] **Step 5: `docs/superpowers/specs/2026-10-12-paypal-checkout-design.md`**

Replace:

```markdown
PayPal JS SDK v6 loaded by script tag, and plain `fetch` to the Orders API v2 on the server. No new dependencies. Sandbox only.
```

with:

```markdown
PayPal JS SDK v6 loaded by script tag in the Next.js frontend. The FastAPI backend calls the Orders API v2 with `httpx` (see the [FastAPI backend design](2026-10-13-fastapi-backend-design.md)). No new frontend dependencies. Sandbox only.
```

Replace:

```markdown
| `lib/sample-list.ts` | Hardcoded packing list: three items, each with `id`, `name`, `priceCents`. Exports `totalCents(itemIds)`, which throws on an unknown or empty selection. |
| `lib/paypal.ts` | Server-only. Cached OAuth token (refreshed from `expires_in`), `createOrder(itemIds)`, `captureOrder(orderId)`. |
| `app/api/orders/route.ts` | `POST {itemIds: string[]}` → `{orderId}` |
| `app/api/orders/[id]/capture/route.ts` | `POST` → `{status, orderId}` |
| `app/checkout/page.tsx` | Server component. Reads `PAYPAL_CLIENT_ID` and passes it to the client component as a prop. |
```

with:

```markdown
| `backend/sample_list.py` | Hardcoded packing list: three items, each with `id`, `name`, `priceCents`. Defines `total_cents(item_ids)`, which raises on an unknown or empty selection. |
| `backend/paypal.py` | Cached OAuth token (refreshed from `expires_in`), `create_order(item_ids)`, `capture_order(order_id)`. |
| `backend/main.py` | `GET /api/items` → the list; `POST /api/orders {itemIds: string[]}` → `{orderId}`; `POST /api/orders/{id}/capture` → `{status, orderId}` |
| `app/checkout/page.tsx` | Server component. Reads `PAYPAL_CLIENT_ID`, fetches the items from `GET /api/items`, and passes both to the client component as props. |
```

Replace:

```markdown
The secret is only read in `lib/paypal.ts`.
```

with:

```markdown
The secret is only read in `backend/paypal.py`.
```

Replace:

```markdown
If either variable is missing, `/checkout` shows a plain "PayPal is not configured" message instead of the button.
```

with:

```markdown
If `PAYPAL_CLIENT_ID` is missing, `/checkout` shows a plain "PayPal is not configured" message instead of the button.
```

Replace:

```markdown
- One test for `totalCents`: correct sum, and throws on empty and unknown IDs. Run with Node's built-in test runner.
```

with:

```markdown
- Backend tests in `backend/`, run with `python -m unittest`: `total_cents`, the PayPal client against a fake PayPal, and the routes' error contract.
```

- [ ] **Step 6: `docs/superpowers/plans/2026-10-12-paypal-checkout.md` — header and constraints**

Insert after the line that starts `**Spec:**`:

```markdown

> **Updated 2026-10-13:** Tasks 1 and 2 were completed in TypeScript and then ported to Python by the [FastAPI backend plan](2026-10-13-fastapi-backend.md). Their text below is kept as a record; do not run them. Task 3 is updated for the FastAPI backend and is the only task left.
```

Replace:

```markdown
- No new dependencies. `package.json` gains only a `test` script.
```

with:

```markdown
- No new frontend dependencies.
```

Replace:

```markdown
The secret is read only in `lib/paypal.ts`.
```

with:

```markdown
The secret is read only in `backend/paypal.py`.
```

- [ ] **Step 7: `docs/superpowers/plans/2026-10-12-paypal-checkout.md` — Task 3**

All replacements in this step are inside `### Task 3: Checkout page`.

Replace:

```markdown
- Consumes: `ITEMS`, `totalCents` from `lib/sample-list.ts`; `POST /api/orders` and `POST /api/orders/{id}/capture` as defined in Task 2.
```

with:

```markdown
- Consumes: `GET /api/items` → `[{id, name, priceCents}]`, `POST /api/orders` and `POST /api/orders/{id}/capture`, all served by the FastAPI backend in `backend/main.py`. The browser reaches them at same-origin `/api/*`; the server page reaches the backend directly at `BACKEND_URL` (default `http://127.0.0.1:8000`).
```

In the `checkout-list.tsx` code block, replace:

```tsx
import { ITEMS, totalCents } from "@/lib/sample-list";
```

with:

```tsx
export type Item = { id: string; name: string; priceCents: number };
```

replace:

```tsx
export default function CheckoutList({ clientId }: { clientId: string }) {
```

with:

```tsx
export default function CheckoutList({ clientId, items }: { clientId: string; items: Item[] }) {
```

replace:

```tsx
  function toggle(id: string) {
```

with:

```tsx
  // For display only. The backend computes the amount that is charged.
  const total = items
    .filter((item) => selected.includes(item.id))
    .reduce((sum, item) => sum + item.priceCents, 0);

  function toggle(id: string) {
```

replace:

```tsx
        {ITEMS.map((item) => {
```

with:

```tsx
        {items.map((item) => {
```

and replace:

```tsx
          ? `Total: ${dollars(totalCents(selected))}`
```

with:

```tsx
          ? `Total: ${dollars(total)}`
```

Replace the whole `page.tsx` code block with:

```tsx
import type { Metadata } from "next";
import { Suspense } from "react";
import CheckoutList, { type Item } from "./checkout-list";

export const metadata: Metadata = { title: "Holiday packing — HeyList" };

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Fetches on every request, so it has to render inside <Suspense> (cacheComponents is on).
async function Checkout({ clientId }: { clientId: string }) {
  let items: Item[];
  try {
    const response = await fetch(`${BACKEND_URL}/api/items`);
    if (!response.ok) throw new Error(`Items request failed: ${response.status}`);
    items = await response.json();
  } catch (error) {
    console.error(error);
    return <p className="text-xl">The list could not be loaded. Please refresh the page.</p>;
  }
  return <CheckoutList clientId={clientId} items={items} />;
}

export default function CheckoutPage() {
  const clientId = process.env.PAYPAL_CLIENT_ID;

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 p-6">
      <h1 className="text-3xl font-semibold">Holiday packing</h1>
      {clientId ? (
        <Suspense fallback={<p className="text-xl">Loading the list…</p>}>
          <Checkout clientId={clientId} />
        </Suspense>
      ) : (
        <p className="text-xl">PayPal is not configured.</p>
      )}
    </main>
  );
}
```

Replace:

```markdown
Run: `npm run lint && npm test && npm run build`
Expected: lint clean, 2 tests pass, build succeeds and lists `/checkout`, `/api/orders` and `/api/orders/[id]/capture`.
```

with:

```markdown
Run: `npm run lint && npm run build && (cd backend && .venv/bin/python -m unittest)`
Expected: lint clean, build succeeds and lists `/checkout` with no `/api` routes, 17 backend tests pass. If the build reports uncached data accessed outside `<Suspense>`, read `node_modules/next/dist/docs/01-app/01-getting-started/08-caching.md` before changing `page.tsx`.
```

Replace:

```markdown
With the dev server running and `.env.local` filled in:
```

with:

```markdown
With both servers running (`cd backend && .venv/bin/uvicorn main:app --reload --env-file ../.env.local`, and `npm run dev`) and `.env.local` filled in:
```

- [ ] **Step 8: Check the docs agree with the code**

```bash
grep -rn "lib/paypal\|lib/sample-list\|app/api" README.md docs --include="*.md" | grep -v "2026-10-13-fastapi-backend" | grep -v "paypal-checkout.md"
```

Expected: no output. (The two FastAPI documents describe the deletion, and the checkout plan keeps Tasks 1 and 2 as a record, so those files are excluded.)

Run from `backend/`: `.venv/bin/python -m unittest`
Expected: `Ran 17 tests` and `OK`.

- [ ] **Step 9: Commit**

```bash
git add README.md docs
git commit -m "docs: describe the FastAPI backend" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
