import io
import json
import unittest
import urllib.error
from unittest import mock

import cron_sweep


def reply(body: dict):
    response = mock.MagicMock()
    response.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
    return response


class CronSweepTest(unittest.TestCase):
    ENV = {"BACKEND_URL": "https://api.example/", "CRON_SECRET": "s3cret"}

    def test_calls_the_sweep_with_the_secret(self):
        with mock.patch.dict(cron_sweep.os.environ, self.ENV), mock.patch.object(cron_sweep.urllib.request, "urlopen", return_value=reply({"failed": 0})) as urlopen:
            self.assertEqual(cron_sweep.main(), 0)
        request = urlopen.call_args.args[0]
        self.assertEqual((request.full_url, request.method), ("https://api.example/api/cron/sweep", "POST"))
        self.assertEqual(request.get_header("Authorization"), "Bearer s3cret")

    def test_a_failed_run_exits_non_zero(self):
        with mock.patch.dict(cron_sweep.os.environ, self.ENV):
            with mock.patch.object(cron_sweep.urllib.request, "urlopen", return_value=reply({"failed": 2})):
                self.assertEqual(cron_sweep.main(), 1)
            with mock.patch.object(cron_sweep.urllib.request, "urlopen", side_effect=urllib.error.URLError("down")):
                self.assertEqual(cron_sweep.main(), 1)

    def test_needs_its_settings(self):
        with mock.patch.dict(cron_sweep.os.environ, {}, clear=True), mock.patch.object(cron_sweep.urllib.request, "urlopen") as urlopen:
            self.assertEqual(cron_sweep.main(), 1)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
