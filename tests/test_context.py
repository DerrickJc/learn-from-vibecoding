"""Machine checks for the learn skill's bounded context helper."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills" / "learn" / "scripts" / "context.py"


class ContextHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="learn-context-test-")
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Learn Skill Tests")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, text=True, capture_output=True, check=False
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout

    def run_helper(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HELPER), *args],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
        )

    def commit_all(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")

    def test_diff_bundle_covers_staged_unstaged_and_new_files(self) -> None:
        core = self.repo / "src" / "core.py"
        core.parent.mkdir()
        core.write_text("def price(value):\n    return value\n", encoding="utf-8")
        self.commit_all()

        core.write_text("def price(value):\n    return value * 0.9\n", encoding="utf-8")
        self.git("add", "src/core.py")
        core.write_text(
            "def price(value):\n    return value * 0.9\n\n# unstaged note\n",
            encoding="utf-8",
        )
        new_test = self.repo / "tests" / "test_price.py"
        new_test.parent.mkdir()
        new_test.write_text("def test_discount():\n    assert True\n", encoding="utf-8")

        output = self.run_helper("diff-bundle")
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertIn("staged", output.stdout)
        self.assertIn("unstaged", output.stdout)
        self.assertIn("tests/test_price.py", output.stdout)
        self.assertIn("unstaged note", output.stdout)

    def test_diff_bundle_caps_paths_and_total_output_and_filters_noise(self) -> None:
        for name in ("a", "b", "c", "d"):
            path = self.repo / "src" / f"{name}.py"
            path.parent.mkdir(exist_ok=True)
            path.write_text("base\n", encoding="utf-8")
        (self.repo / "build").mkdir()
        (self.repo / "build" / "generated.py").write_text("base\n", encoding="utf-8")
        (self.repo / "package-lock.json").write_text("{}\n", encoding="utf-8")
        self.commit_all()

        for name in ("a", "b", "c", "d"):
            path = self.repo / "src" / f"{name}.py"
            path.write_text("base\n" + (name * 5_000) + "\n", encoding="utf-8")
        generated = self.repo / "build" / "generated.py"
        generated.write_text("changed\n", encoding="utf-8")
        lock = self.repo / "package-lock.json"
        lock.write_text('{"changed": true}\n', encoding="utf-8")
        learning = self.repo / ".learning" / "notes.md"
        learning.parent.mkdir()
        learning.write_text("private note\n", encoding="utf-8")

        output = self.run_helper("diff-bundle")
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertLessEqual(len(output.stdout), 12_000)
        self.assertLessEqual(output.stdout.count("===== "), 3)
        self.assertNotIn("generated.py", output.stdout)
        self.assertNotIn("package-lock.json", output.stdout)
        self.assertNotIn("private note", output.stdout)

        rejected = self.run_helper(
            "diff-read",
            "--file", "src/a.py",
            "--file", "src/b.py",
            "--file", "src/c.py",
            "--file", "src/d.py",
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("At most 3 paths", rejected.stderr)

    def test_diff_summary_indexes_paths_omitted_from_bundle(self) -> None:
        for index in range(30):
            source = self.repo / "src" / f"{index:03}.py"
            source.parent.mkdir(exist_ok=True)
            source.write_text(f"VALUE = {index}\n", encoding="utf-8")
        self.commit_all()
        for index in range(30):
            source = self.repo / "src" / f"{index:03}.py"
            source.write_text(f"VALUE = {index + 1}\n", encoding="utf-8")

        bundle = self.run_helper("diff-bundle")
        short_index = self.run_helper("diff-summary", "--limit", "25")
        expanded_index = self.run_helper("diff-summary", "--limit", "50")
        target = self.run_helper("diff-read", "--file", "src/029.py")

        self.assertEqual(bundle.returncode, 0, bundle.stderr)
        self.assertIn("Bounded sample: 3 of 30", bundle.stdout)
        self.assertNotIn("src/029.py", bundle.stdout)
        self.assertNotIn("src/029.py", short_index.stdout)
        self.assertIn("src/029.py", expanded_index.stdout)
        self.assertEqual(target.returncode, 0, target.stderr)
        self.assertIn("+VALUE = 30", target.stdout)

    def test_review_index_prioritizes_open_gaps_and_hides_answers(self) -> None:
        notes = self.repo / ".learning" / "notes.md"
        notes.parent.mkdir()
        notes.write_text(
            "## Gaps\n"
            "- [x] [GAP G-OLD] Closed gap | 2025-01-01\n"
            "  Correction: closed answer must not be a candidate\n"
            "- [ ] [GAP G-OPEN] Redis fallback | 2026-09-01\n"
            "  Correction: Redis exception propagates\n"
            "## Concepts\n"
            "- [x] [CONCEPT C-OLD] Cache aside | 2024-01-01\n"
            "  Answer: stale concept answer\n",
            encoding="utf-8",
        )

        index = self.run_helper("review-index", "--limit", "3")
        self.assertEqual(index.returncode, 0, index.stderr)
        self.assertIn("G-OPEN", index.stdout)
        self.assertLess(index.stdout.index("G-OPEN"), index.stdout.index("C-OLD"))
        self.assertNotIn("Redis exception propagates", index.stdout)
        self.assertNotIn("stale concept answer", index.stdout)
        self.assertNotIn("G-OLD", index.stdout)

        line = next(
            line.split(" |", 1)[0].removeprefix("line ")
            for line in index.stdout.splitlines()
            if "G-OPEN" in line
        )
        entry = self.run_helper("review-entry", "--line", line)
        self.assertEqual(entry.returncode, 0, entry.stderr)
        self.assertIn("Redis exception propagates", entry.stdout)
        self.assertNotIn("stale concept answer", entry.stdout)


if __name__ == "__main__":
    unittest.main()
