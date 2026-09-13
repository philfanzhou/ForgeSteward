"""校验统一版本、显示名称及稳定的安装和调用标识。"""

import json
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
TITLES = {
    "check-workflow": "Check Workflow",
    "prepare-work": "Prepare Work",
    "execute-work": "Execute Work",
    "review-and-merge": "Review and Merge",
    "fix-feedback": "Fix Feedback",
}


class PluginMetadataTests(unittest.TestCase):
    def test_all_plugins_match_repository_version(self):
        version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-rc\.(?:0|[1-9]\d*))?$")
        plugins = sorted(path for path in (REPO / "plugins").iterdir() if path.is_dir())
        self.assertTrue(plugins, "必须至少存在一个插件，禁止空集合通过版本检查")
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
                # 项目约定的双引号标量也是 JSON 字符串；完整 YAML 由 Agent 校验器校验。
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


if __name__ == "__main__":
    unittest.main()
