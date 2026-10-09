"""Exercise the Linux process wrapper with disposable service commands."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "linux" and shutil.which("bash") and shutil.which("setsid"),
                     "Container entrypoint requires Linux bash and setsid")
class EntrypointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.log = self.root / "calls"
        self.environment = {**os.environ, "PATH": f"{self.root}:{os.environ['PATH']}",
                            "RUN_LOG": str(self.log), "BOOTSTRAP_EXIT": "0"}
        for name, body in {
            "python": 'echo bootstrap >> "$RUN_LOG"\nexit "$BOOTSTRAP_EXIT"',
            "langgraph": 'echo backend >> "$RUN_LOG"\nsleep 0.3\nexit 7',
            "node": 'echo ui >> "$RUN_LOG"\nsleep 30',
        }.items():
            command = self.root / name
            command.write_text(f"#!/bin/bash\n{body}\n")
            command.chmod(0o755)

    def run_entrypoint(self, *args):
        return subprocess.run(["bash", str(ROOT / "scripts/docker-entrypoint.sh"), *args],
                              env=self.environment, capture_output=True, text=True, timeout=10)

    def test_initialization_precedes_services_and_service_failure_stops_container(self):
        result = self.run_entrypoint()
        self.assertEqual(result.returncode, 7, result.stderr)
        calls = self.log.read_text().splitlines()
        self.assertEqual(calls[0], "bootstrap")
        self.assertEqual(set(calls[1:]), {"backend", "ui"})

    def test_initialization_failure_prevents_both_services(self):
        self.environment["BOOTSTRAP_EXIT"] = "9"
        result = self.run_entrypoint()
        self.assertEqual(result.returncode, 9, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ["bootstrap"])
        self.assertIn("Startup initialization failed", result.stderr)

    def test_one_off_commands_bypass_initialization(self):
        result = self.run_entrypoint("bash", "-c", "echo maintenance")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "maintenance")
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
