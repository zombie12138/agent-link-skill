#!/usr/bin/env python3
import subprocess
import tempfile
import unittest
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agentlink.py"


class AgentlinkTest(unittest.TestCase):
    def run_sync(self, *args: str, home: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = None
        if home is not None:
            env = os.environ.copy()
            env["HOME"] = str(home)
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=env,
        )

    @staticmethod
    def temp_dir():
        return tempfile.TemporaryDirectory(dir="/dev/shm" if Path("/dev/shm").is_dir() else None)

    @staticmethod
    def make_repo(root: Path) -> None:
        (root / ".git").mkdir()

    @staticmethod
    def make_plugin(root: Path, name: str, with_skill: bool = True) -> Path:
        plugin = root / ".claude" / "plugins" / "marketplaces" / name
        plugin.mkdir(parents=True)
        if with_skill:
            (plugin / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        return plugin

    def make_codex_plugin_symlink(
        self,
        root: Path,
        codex_skills: Path,
        name: str = "agentlink",
        create_plugin: bool = True,
    ) -> Path:
        if create_plugin:
            self.make_plugin(root, name, with_skill=False)
        target = codex_skills / name
        target.parent.mkdir(parents=True)
        target.symlink_to(Path("..") / ".." / ".claude" / "plugins" / "marketplaces" / name)
        return target

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

    def test_global_skills_link_entries_and_preserve_codex_system_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            claude_skills = home / ".claude" / "skills"
            codex_skills = home / ".codex" / "skills"
            (claude_skills / "agentlink").mkdir(parents=True)
            (codex_skills / ".system").mkdir(parents=True)

            result = self.run_sync("global", "skills", "--apply", home=home)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(codex_skills.is_symlink())
            self.assertTrue((codex_skills / ".system").is_dir())
            self.assertFalse((codex_skills / ".system").is_symlink())
            self.assertTrue((codex_skills / "agentlink").is_symlink())
            self.assertEqual((codex_skills / "agentlink").resolve(), (claude_skills / "agentlink").resolve())

    def test_global_skills_link_codex_real_entries_back_to_claude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            codex_skill = home / ".codex" / "skills" / "codex-only"
            codex_skill.mkdir(parents=True)

            result = self.run_sync("global", "skills", "--apply", home=home)

            target = home / ".claude" / "skills" / "codex-only"
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), codex_skill.resolve())

    def test_global_plugin_skills_link_marketplace_plugins_with_skill_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            plugin = self.make_plugin(home, "agentlink")

            result = self.run_sync("global", "plugin-skills", "--apply", home=home)

            target = home / ".codex" / "skills" / "agentlink"
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), plugin.resolve())

    def test_global_plugin_skills_skip_plugins_without_skill_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.make_plugin(home, "notes-only", with_skill=False)

            result = self.run_sync("global", "plugin-skills", "--dry-run", home=home)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("skip plugin-skill:notes-only: no top-level SKILL.md", result.stdout)
            self.assertFalse((home / ".codex" / "skills" / "notes-only").exists())

    def test_global_plugin_skills_without_marketplace_reports_specific_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            result = self.run_sync("global", "plugin-skills", "--dry-run", home=home)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("skip plugin-skills: no marketplace directory", result.stdout)
            self.assertNotIn("no matching entries", result.stdout)

    def test_global_plugin_skills_report_per_plugin_conflict_without_replacing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.make_plugin(home, "agentlink")
            ok_plugin = self.make_plugin(home, "ok-plugin")
            codex_skills = home / ".codex" / "skills"
            (codex_skills / "agentlink").mkdir(parents=True)

            result = self.run_sync("global", "plugin-skills", "--apply", home=home)

            self.assertEqual(result.returncode, 1)
            self.assertIn("conflict plugin-skill:agentlink", result.stdout)
            self.assertIn("plugin-skill:ok-plugin: Claude exists, Codex missing", result.stdout)
            self.assertFalse((codex_skills / "agentlink").is_symlink())
            self.assertTrue((codex_skills / "ok-plugin").is_symlink())
            self.assertEqual((codex_skills / "ok-plugin").resolve(), ok_plugin.resolve())

    def test_global_all_includes_plugin_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.make_plugin(home, "agentlink")

            result = self.run_sync("global", "--dry-run", home=home)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("plugin-skill:agentlink: Claude exists, Codex missing", result.stdout)

    def test_global_skills_skip_codex_symlink_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.make_codex_plugin_symlink(home, home / ".codex" / "skills")

            result = self.run_sync("global", "skills", "--dry-run", home=home)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("no matching entries", result.stdout)
            self.assertNotIn("skill:agentlink", result.stdout)

    def test_global_skills_skip_stale_codex_symlink_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.make_codex_plugin_symlink(home, home / ".codex" / "skills", create_plugin=False)

            result = self.run_sync("global", "skills", "--dry-run", home=home)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("no matching entries", result.stdout)
            self.assertNotIn("skill:agentlink", result.stdout)

    def test_repo_plugin_skills_link_marketplace_plugins_with_skill_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            plugin = self.make_plugin(repo, "repo-agentlink")

            result = self.run_sync("repo", "plugin-skills", "--repo", str(repo), "--apply")

            target = repo / ".agents" / "skills" / "repo-agentlink"
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), plugin.resolve())

    def test_repo_all_includes_plugin_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            self.make_plugin(repo, "repo-plugin")

            result = self.run_sync("repo", "all", "--repo", str(repo), "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("plugin-skill:repo-plugin: Claude exists, Codex missing", result.stdout)

    def test_repo_skills_link_codex_real_entries_back_to_claude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            codex_skill = repo / ".agents" / "skills" / "codex-only"
            codex_skill.mkdir(parents=True)

            result = self.run_sync("repo", "skills", "--repo", str(repo), "--apply")

            target = repo / ".claude" / "skills" / "codex-only"
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), codex_skill.resolve())

    def test_repo_skills_skip_codex_symlink_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            self.make_codex_plugin_symlink(repo, repo / ".agents" / "skills")

            result = self.run_sync("repo", "skills", "--repo", str(repo), "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("no matching entries", result.stdout)
            self.assertNotIn("skill:agentlink", result.stdout)

    def test_repo_skills_skip_stale_codex_symlink_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.make_repo(repo)
            self.make_codex_plugin_symlink(repo, repo / ".agents" / "skills", create_plugin=False)

            result = self.run_sync("repo", "skills", "--repo", str(repo), "--dry-run")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("no matching entries", result.stdout)
            self.assertNotIn("skill:agentlink", result.stdout)

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
