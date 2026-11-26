"""Tests for `tepi web` local launcher (no DB touched, no browser spawned in tests)."""

import io
import json
import os
import signal
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import _guard  # noqa: F401  -- patch load_config before tepi binds it
from tepi.cli import main


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class WebCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._saved_dir = os.environ.get("TEPI_DATA_DIR")
        os.environ["TEPI_DATA_DIR"] = self.tmp.name
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self._saved_dir is None:
            os.environ.pop("TEPI_DATA_DIR", None)
        else:
            os.environ["TEPI_DATA_DIR"] = self._saved_dir

    def test_web_starts_server_reuses_it_and_never_opens_db(self):
        port = _free_port()
        out1 = io.StringIO()
        with redirect_stdout(out1):
            code1 = main(["web", "--port", str(port), "--no-open", "--json"])
        self.assertEqual(code1, 0)
        first = json.loads(out1.getvalue())
        self.assertEqual(first["url"], f"http://127.0.0.1:{port}/web/")
        self.assertTrue(first["started"])
        self.assertIsInstance(first["pid"], int)
        self.addCleanup(self._stop_pid, first["pid"])

        # Second call detects the listening port and does not spawn a second server.
        out2 = io.StringIO()
        with patch("tepi.cli.webbrowser.open") as opener, redirect_stdout(out2):
            code2 = main(["web", "--port", str(port), "--json"])
        self.assertEqual(code2, 0)
        second = json.loads(out2.getvalue())
        self.assertFalse(second["started"])
        self.assertIsNone(second["pid"])
        opener.assert_called_once_with(f"http://127.0.0.1:{port}/web/")

        # Never creates or opens tepi.sqlite.
        self.assertFalse((Path(self.tmp.name) / "tepi.sqlite").exists())

    @staticmethod
    def _stop_pid(pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    unittest.main()
