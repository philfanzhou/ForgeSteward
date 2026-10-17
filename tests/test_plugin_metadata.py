"""Check unified versions, display names, and stable install/invocation identifiers."""

import json
from pathlib import Path
import re
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[1]
TITLES = {
    "check-workflow": "Check Workflow",
    "prepare-work": "Prepare Work",
    "execute-work": "Execute Work",
    "review-and-merge": "Review and Merge",
    "fix-feedback": "Fix Feedback",
    "work-cycle": "Work Cycle",
}


class PluginMetadataTests(unittest.TestCase):
    def test_all_plugins_match_repository_version(self):
        version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-rc\.(?:0|[1-9]\d*))?$")
        plugins = sorted(path for path in (REPO / "plugins").iterdir() if path.is_dir())
        self.assertTrue(plugins, "At least one plugin must exist; an empty set must not pass version checks")
        for plugin in plugins:
            for relative in ("plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
                with self.subTest(plugin=plugin.name, manifest=relative):
                    manifest = json.loads((plugin / relative).read_text(encoding="utf-8"))
                    self.assertEqual(manifest["version"], version)

    def test_plugin_and_skill_display_names_match(self):
        for name, title in TITLES.items():
            with self.subTest(plugin=name):
                plugin = REPO / "plugins" / name
                manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
                expected = title + " - ForgeSteward"
                self.assertEqual(manifest["interface"]["displayName"], expected)
                skill = plugin / "skills" / ("forge-steward-" + name)
                metadata = (skill / "agents/openai.yaml").read_text(encoding="utf-8")
                # The project's double-quoted scalars are also JSON strings; Agent validators check full YAML.
                values = re.findall(r'^  display_name: (".*")\s*$', metadata, re.MULTILINE)
                self.assertEqual(len(values), 1)
                self.assertEqual(json.loads(values[0]), expected)

    def test_plugin_and_skill_default_prompts_match(self):
        for name in TITLES:
            with self.subTest(plugin=name):
                plugin = REPO / "plugins" / name
                manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
                metadata = (plugin / "skills" / ("forge-steward-" + name) / "agents/openai.yaml").read_text(encoding="utf-8")
                values = re.findall(r'^  default_prompt: (".*")\s*$', metadata, re.MULTILINE)
                self.assertEqual(len(values), 1)
                self.assertEqual(json.loads(values[0]), manifest["interface"]["defaultPrompt"])

    def test_manifest_identity_and_versions_stay_in_sync(self):
        for name in TITLES:
            with self.subTest(plugin=name):
                plugin = REPO / "plugins" / name
                manifests = [json.loads((plugin / path).read_text(encoding="utf-8"))
                             for path in ("plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json")]
                self.assertEqual({manifest["name"] for manifest in manifests}, {name})
                versions = {manifest["version"] for manifest in manifests}
                self.assertEqual(len(versions), 1)
                self.assertRegex(versions.pop(), r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
                skill_name = "forge-steward-" + name
                skill = plugin / "skills" / skill_name
                frontmatter = (skill / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
                self.assertIn("name: " + skill_name + "\n", frontmatter)
                self.assertIn("$" + skill_name, manifests[1]["interface"]["defaultPrompt"])

    def test_marketplaces_match_current_install_ids(self):
        for path in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            with self.subTest(marketplace=path):
                marketplace = json.loads((REPO / path).read_text(encoding="utf-8"))
                self.assertEqual(marketplace["name"], "forge-steward")
                names = [plugin["name"] for plugin in marketplace["plugins"]]
                self.assertCountEqual(names, TITLES)
                self.assertCountEqual([p.name for p in (REPO / "plugins").iterdir() if p.is_dir()], TITLES)
                for plugin in marketplace["plugins"]:
                    source = plugin["source"]
                    relative = source["path"] if isinstance(source, dict) else source
                    self.assertEqual((REPO / relative).resolve(), REPO / "plugins" / plugin["name"])
                    self.assertTrue((REPO / relative / "plugin.json").is_file())

    def test_reference_filenames_do_not_collide_with_instruction_entries(self):
        # A reference named agents.md or claude.md is exposed as AGENTS.md or CLAUDE.md on
        # case-insensitive filesystems, where an Agent may auto-load it as an instruction entry.
        tracked = subprocess.check_output(["git", "ls-files", "-z", "--", "plugins"], cwd=REPO)
        references = [name for name in tracked.decode().split("\0")
                      if re.fullmatch(r"plugins/[^/]+/skills/[^/]+/references/.+", name)]
        self.assertTrue(references, "No tracked Skill references found; an empty inventory must not pass")
        collisions = sorted(name for name in references
                            if Path(name).name.casefold() in {"agents.md", "claude.md"})
        self.assertEqual(
            collisions, [],
            "Skill reference names must not match AGENTS.md or CLAUDE.md ignoring case, because "
            "case-insensitive filesystems would load them as instruction entries; rename: " + repr(collisions))

    def test_orchestrator_bundled_version_matches_unified_version(self):
        bundled = REPO / "plugins/work-cycle/skills/forge-steward-work-cycle/scripts/VERSION"
        self.assertEqual(bundled.read_text(encoding="utf-8").strip(),
                         (REPO / "VERSION").read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
