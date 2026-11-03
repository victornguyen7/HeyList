"""The Render cron job's command (render.yaml, heylist-sweep): calls POST /api/cron/sweep on heylist-api, which asks
PayPal again about payments still pending (decision 74). Standard library only, so the cron job needs no install.

Needs BACKEND_URL (heylist-api's public URL) and CRON_SECRET (the same value heylist-api has). Exits non-zero when
the sweep fails, so Render marks the run as failed and can notify the owner.
"""

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    url, secret = os.environ.get("BACKEND_URL"), os.environ.get("CRON_SECRET")
    if not url or not secret:
        print("BACKEND_URL and CRON_SECRET must be set", file=sys.stderr)
        return 1
    request = urllib.request.Request(f"{url.rstrip('/')}/api/cron/sweep", method="POST", headers={"Authorization": f"Bearer {secret}"})
    try:
        # The backend can take a minute to answer while it restarts or redeploys.
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"Sweep failed: {exc}", file=sys.stderr)
        return 1
    print(f"Sweep: {result}")
    return 1 if result.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
