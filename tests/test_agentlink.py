#!/usr/bin/env python3
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agentlink.py"


class AgentlinkTest(unittest.TestCase):
    def run_sync(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    @staticmethod
    def temp_dir():
        return tempfile.TemporaryDirectory(dir="/dev/shm" if Path("/dev/shm").is_dir() else None)

    @staticmethod
    def make_repo(root: Path) -> None:
        (root / ".git").mkdir()

    def test_one_sided_rules_links_missing_side(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            (repo / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")

            result = self.run_sync("repo", "rules", "--repo", str(repo), "--apply")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((repo / "AGENTS.md").is_symlink())
            self.assertEqual((repo / "AGENTS.md").resolve(), (repo / "CLAUDE.md").resolve())

    def test_conflict_returns_nonzero_and_does_not_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            (repo / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
            (repo / "AGENTS.md").write_text("# Codex\n", encoding="utf-8")

            result = self.run_sync("repo", "rules", "--repo", str(repo), "--apply")

            self.assertEqual(result.returncode, 1)
            self.assertIn("conflict rules", result.stdout)
            self.assertFalse((repo / "AGENTS.md").is_symlink())

    def test_same_target_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            claude = repo / "CLAUDE.md"
            codex = repo / "AGENTS.md"
            claude.write_text("# Shared\n", encoding="utf-8")
            codex.symlink_to("CLAUDE.md")

            result = self.run_sync("repo", "rules", "--repo", str(repo), "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("already share", result.stdout)

    def test_repo_all_processes_rules_and_each_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            (repo / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
            skills = repo / ".claude" / "skills"
            skills.mkdir(parents=True)
            (skills / "no-magic").mkdir()
            ((skills / "no-magic") / "SKILL.md").write_text("---\nname: no-magic\n---\n", encoding="utf-8")

            result = self.run_sync("repo", "all", "--repo", str(repo), "--apply")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((repo / "AGENTS.md").is_symlink())
            self.assertFalse((repo / ".agents" / "skills").is_symlink())
            self.assertTrue((repo / ".agents" / "skills" / "no-magic").is_symlink())
            self.assertEqual(
                (repo / ".agents" / "skills" / "no-magic").resolve(),
                (repo / ".claude" / "skills" / "no-magic").resolve(),
            )

    def test_skills_preserve_codex_system_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            claude_skills = repo / ".claude" / "skills"
            codex_skills = repo / ".agents" / "skills"
            (claude_skills / "agentlink").mkdir(parents=True)
            (codex_skills / ".system").mkdir(parents=True)

            result = self.run_sync("repo", "skills", "--repo", str(repo), "--apply")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((codex_skills / ".system").is_dir())
            self.assertFalse((codex_skills / ".system").is_symlink())
            self.assertTrue((codex_skills / "agentlink").is_symlink())

    def test_pair_links_explicit_memory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude_memory = root / ".claude" / "memory" / "MEMORY.md"
            codex_memory = root / ".codex" / "memory" / "MEMORY.md"
            claude_memory.parent.mkdir(parents=True)
            claude_memory.write_text("# Memory\n", encoding="utf-8")

            result = self.run_sync("pair", str(claude_memory), str(codex_memory), "--apply")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(codex_memory.is_symlink())
            self.assertEqual(codex_memory.resolve(), claude_memory.resolve())

    def test_non_git_directory_warns_and_uses_given_path(self) -> None:
        with self.temp_dir() as tmp:
            root = Path(tmp)
            (root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")

            result = self.run_sync("repo", "rules", "--repo", str(root), "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("warning repo: no .git found", result.stdout)
            self.assertIn("Claude exists, Codex missing", result.stdout)

    def test_pair_requires_two_paths(self) -> None:
        result = self.run_sync("pair", "/tmp/claude.md")

        self.assertEqual(result.returncode, 2)
        self.assertIn("pair usage", result.stderr)

    def test_dir_pairs_links_each_top_level_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude_memory = root / ".claude" / "memory"
            codex_memory = root / ".codex" / "memory"
            claude_memory.mkdir(parents=True)
            (claude_memory / "a.md").write_text("# A\n", encoding="utf-8")
            (claude_memory / "notes").mkdir()

            result = self.run_sync("dir-pairs", str(claude_memory), str(codex_memory), "--apply")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((codex_memory / "a.md").is_symlink())
            self.assertTrue((codex_memory / "notes").is_symlink())
            self.assertEqual((codex_memory / "a.md").resolve(), (claude_memory / "a.md").resolve())
            self.assertEqual((codex_memory / "notes").resolve(), (claude_memory / "notes").resolve())

    def test_removed_plugin_command_is_invalid(self) -> None:
        result = self.run_sync("claude-plugin-to-skills")

        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
