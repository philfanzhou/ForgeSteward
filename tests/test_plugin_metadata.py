"""校验插件与技能的显示名称一致，同时保留稳定的安装及调用标识。"""

import json
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
TITLES = {
    "check-workflow": "Check Workflow",
    "find-work": "Find Work",
    "review-and-merge": "Review and Merge",
    "fix-feedback": "Fix Feedback",
}


class PluginMetadataTests(unittest.TestCase):
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

    def test_marketplaces_keep_existing_install_ids(self):
        for path in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            with self.subTest(marketplace=path):
                marketplace = json.loads((REPO / path).read_text(encoding="utf-8"))
                self.assertEqual(marketplace["name"], "forge-steward")
                names = [plugin["name"] for plugin in marketplace["plugins"]]
                self.assertCountEqual(names, TITLES)


if __name__ == "__main__":
    unittest.main()
