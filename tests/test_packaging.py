"""Check metadata through the legacy setup entry point, without API access."""
import configparser
from email.parser import Parser
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class TestPackaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="kinorium-packaging-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        source = Path(__file__).resolve().parents[1]
        cls.root = Path(cls.temp.name)
        for name in ("pyproject.toml", "setup.cfg", "setup.py", "README.md", "MANIFEST.in", "CHANGELOG.md", "get_session.py", "TEST_REPORT.md", "generate_async_version.py"):
            shutil.copy2(source / name, cls.root / name)
        shutil.copytree(source / "kinorium", cls.root / "kinorium",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        shutil.copytree(source / "tests", cls.root / "tests",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("get_session.local.json", ".env", "TEST_REPORT.local.md", "kinorium/session.local.json"):
            (cls.root / name).write_text("private-packaging-canary")
        result = subprocess.run(
            [sys.executable, "setup.py", "egg_info"], cwd=cls.root,
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.egg_info = cls.root / "kinorium.egg-info"

    def test_package_identity(self):
        metadata = Parser().parsestr((self.egg_info / "PKG-INFO").read_text())
        self.assertEqual(metadata["Name"], "kinorium")
        self.assertEqual(metadata["Version"], "0.1.1")
        self.assertEqual(metadata["Requires-Python"], ">=3.7")
        self.assertFalse((self.root / "UNKNOWN.egg-info").exists())

    def test_both_client_dependencies_are_declared(self):
        requirements = (self.egg_info / "requires.txt").read_text().splitlines()
        self.assertIn("requests>=2.25.0", requirements)
        self.assertIn("aiohttp>=3.8.0", requirements)

    def test_distribution_contains_all_package_modules(self):
        sources = set((self.egg_info / "SOURCES.txt").read_text().splitlines())
        expected = {p.relative_to(self.root).as_posix()
                    for p in (self.root / "kinorium").rglob("*.py")}
        self.assertTrue(expected)
        self.assertTrue(expected <= sources, expected - sources)

    def test_cli_entry_point(self):
        entry_points = configparser.ConfigParser()
        entry_points.read(self.egg_info / "entry_points.txt")
        self.assertEqual(entry_points["console_scripts"]["kinorium-auth"],
                         "kinorium.cli:main")

    def test_local_secret_files_are_excluded(self):
        sources = set((self.egg_info / "SOURCES.txt").read_text().splitlines())
        self.assertIn("get_session.py", sources)
        self.assertIn("tests/live_api_audit.py", sources)
        self.assertIn("generate_async_version.py", sources)
        for name in ("get_session.local.json", ".env", "TEST_REPORT.local.md", "kinorium/session.local.json"):
            self.assertNotIn(name, sources)
