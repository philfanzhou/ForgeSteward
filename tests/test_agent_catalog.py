"""Check Agent catalog and README install/upgrade/uninstall commands against the catalog, VERSION, and plugin directories."""

import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CATALOG = Path("plugins/work-cycle/skills/forge-steward-work-cycle/scripts/agents.json")
AGENT_IDS = {"claude-code", "codex", "zcode", "opencode", "deepseek-harness"}
PLACEHOLDERS = {"version", "plugin", "source", "zcode_cli"}
OPERATIONS = (("install", "Install", "Install"), ("upgrade", "Upgrade", "Upgrade"), ("uninstall", "Uninstall", "Uninstall"))
OVERVIEW = "Supported agents and installation"
# README placeholder syntax; substitute {version} during expansion.
README_VALUES = {"source": "$HOME/code/ForgeSteward-v{version}", "zcode_cli": "$ZCODE_CLI"}
SHELL_SAFE = re.compile(r"^[A-Za-z0-9_@%+=:,./-]+$")
VERSION_REF = re.compile(r"\bv(\d+\.\d+\.\d+(?:-rc\.\d+)?)\b")
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
LINK = re.compile(r"\]\(([^)\s]*)\)")


def load_catalog(repo):
    return json.loads((repo / CATALOG).read_text(encoding="utf-8"))


def plugin_names(repo):
    return sorted(path.name for path in (repo / "plugins").iterdir() if path.is_dir())


def render(argv, values):
    """Join argv into a README shell line; double-quote arguments containing $ or spaces."""
    words = []
    for arg in argv:
        for key, value in values.items():
            arg = arg.replace("{" + key + "}", value)
        words.append(arg if SHELL_SAFE.match(arg) else '"' + arg + '"')
    return " ".join(words)


def expected_steps(steps, version, plugins):
    """Return groups of (step, plugin or None, expected command line)."""
    values = {"version": version, "zcode_cli": README_VALUES["zcode_cli"],
              "source": README_VALUES["source"].replace("{version}", version)}
    groups = []
    for step in steps:
        if step["per_plugin"]:
            groups.append([(plugin, render(step["argv"], dict(values, plugin=plugin))) for plugin in plugins])
        else:
            groups.append([(None, render(step["argv"], values))])
    return groups


def section(lines, level, title):
    """Return lines under a heading up to the next equal/higher heading, or None if absent."""
    heading = "#" * level + " " + title
    for index, line in enumerate(lines):
        if line.rstrip() == heading:
            body = []
            for following in lines[index + 1:]:
                match = re.match(r"^(#+) ", following)
                if match and len(match.group(1)) <= level:
                    break
                body.append(following)
            return body
    return None


def code_lines(lines):
    inside = False
    result = []
    for line in lines:
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if inside and line.strip() and not line.strip().startswith("#"):
            result.append(line.strip())
    return result


def check_readme(repo):
    """Return README mismatches against catalog, VERSION, and plugin directories, or an empty list."""
    version = (repo / "VERSION").read_text(encoding="utf-8").strip()
    plugins = plugin_names(repo)
    catalog = load_catalog(repo)
    lines = (repo / "README.md").read_text(encoding="utf-8").splitlines()
    errors = []
    overview = section(lines, 2, OVERVIEW)
    if overview is None:
        return ['README lacks section "## {}"'.format(OVERVIEW)]
    table = [line for line in overview if line.startswith("|")]
    for line in table:
        for found in VERSION_REF.findall(line):
            if found != version:
                errors.append("README overview has v{}; VERSION is {}: {}".format(found, version, line.strip()))
    for agent in catalog["agents"]:
        name = agent["name"]
        if not any("[" + name + "]" in line for line in table):
            errors.append("README overview lacks a row for {}".format(name))
        body = section(overview, 3, name)
        if body is None:
            errors.append('README lacks section "### {}"'.format(name))
            continue
        for key, title, label in OPERATIONS:
            part = section(body, 4, title)
            if part is None:
                errors.append('README {} lacks subsection "#### {}"'.format(name, title))
                continue
            commands = code_lines(part)
            for command in commands:
                for found in VERSION_REF.findall(command):
                    if found != version:
                        errors.append("README {} {} command has v{}; VERSION is {}: {}".format(
                            name, label, found, version, command))
            if agent["install_mode"] == "all" and not any("--all" in command for command in commands):
                errors.append("README {} {} command does not use --all".format(name, label))
            cursor = 0
            for group in expected_steps(agent["commands"][key], version, plugins):
                positions = []
                for plugin, expected in group:
                    later = [i for i, command in enumerate(commands) if command == expected and i >= cursor]
                    if later:
                        positions.append(later[0])
                    elif expected in commands:
                        errors.append("README {} {} command order differs from catalog: {}".format(name, label, expected))
                    elif plugin:
                        errors.append("README {} {} is missing plugin {} command: {}".format(name, label, plugin, expected))
                    else:
                        errors.append("README {} {} is missing a command (or differs from catalog): {}".format(name, label, expected))
                if positions:
                    cursor = max(positions) + 1
    return errors


def slug(heading):
    """Generate GitHub heading anchors: lowercase, remove punctuation, replace spaces with hyphens."""
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path):
    return {slug(line.lstrip("#")) for line in path.read_text(encoding="utf-8").splitlines()
            if re.match(r"^#{1,6} ", line)}


class AgentCatalogTests(unittest.TestCase):
    def test_codex_install_query_is_limited_to_verified_marketplace(self):
        codex = next(agent for agent in load_catalog(REPO)["agents"] if agent["id"] == "codex")
        self.assertEqual(codex["detect_install"]["argv"],
                         ["codex", "plugin", "list", "--marketplace", "forge-steward", "--json"])
        self.assertEqual(codex["verified"],
                         {"version": "0.157.1", "date": "2026-10-13", "platforms": ["darwin"]})
        self.assertEqual((codex["detect_install"]["items"], codex["detect_install"]["id_field"],
                          codex["detect_install"]["version_field"]), ("installed", "pluginId", "version"))

    def test_catalog_lists_the_five_agents_with_required_fields(self):
        catalog = load_catalog(REPO)
        self.assertEqual(catalog["schema"], 1)
        self.assertEqual(catalog["repository"], "philfanzhou/ForgeSteward")
        self.assertEqual({agent["id"] for agent in catalog["agents"]}, AGENT_IDS)
        for agent in catalog["agents"]:
            with self.subTest(agent=agent["id"]):
                for field in ("name", "verified", "detect_agent", "detect_install", "install_mode",
                              "needs_local_source", "commands"):
                    self.assertIn(field, agent)
                self.assertTrue(agent["verified"]["version"])
                self.assertRegex(agent["verified"]["date"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertIn(agent["install_mode"], ("per-plugin", "all"))
                self.assertEqual(set(agent["commands"]), {"install", "upgrade", "uninstall"})
                uses_source = False
                for key, steps in agent["commands"].items():
                    self.assertTrue(steps, key)
                    for step in steps:
                        self.assertTrue(all(isinstance(arg, str) for arg in step["argv"]))
                        used = {name for arg in step["argv"] for name in PLACEHOLDER.findall(arg)}
                        self.assertLessEqual(used, PLACEHOLDERS, step["argv"])
                        self.assertEqual("plugin" in used, step["per_plugin"], step["argv"])
                        uses_source = uses_source or "source" in used
                    if agent["install_mode"] == "all":
                        self.assertTrue(any("--all" in step["argv"] for step in steps), key)
                    else:
                        self.assertTrue(any(step["per_plugin"] for step in steps), key)
                self.assertEqual(uses_source, agent["needs_local_source"])

    def test_plugin_agents_list_marketplaces_and_remove_only_existing_one(self):
        catalog = load_catalog(REPO)
        self.assertIn("only_if_marketplace", catalog["step_fields"])
        expected = {
            "claude-code": (["claude", "plugin", "marketplace", "list", "--json"], None),
            "codex": (["codex", "plugin", "marketplace", "list", "--json"], "marketplaces"),
            "zcode": (["node", "{zcode_cli}", "plugins", "marketplace", "list", "--json"], None),
        }
        for agent in catalog["agents"]:
            with self.subTest(agent=agent["id"]):
                if agent["install_mode"] != "per-plugin":
                    self.assertNotIn("detect_marketplace", agent)
                    continue
                argv, items = expected[agent["id"]]
                method = agent["detect_marketplace"]
                self.assertEqual((method["argv"], method["items"], method["name_field"]), (argv, items, "name"))
                for key, steps in agent["commands"].items():
                    for step in steps:
                        removes = "marketplace" in step["argv"] and "remove" in step["argv"]
                        self.assertEqual(step.get("only_if_marketplace", False), key == "upgrade" and removes,
                                         (key, step["argv"]))
        self.assertEqual({agent["id"] for agent in catalog["agents"] if agent["install_mode"] == "per-plugin"},
                         set(expected))

    def test_readme_matches_catalog_version_and_plugins(self):
        self.assertEqual(check_readme(REPO), [])

    def test_readme_anchors_referenced_by_docs_exist(self):
        targets = [REPO / "README.md"] + sorted((REPO / "docs").glob("*.md"))
        for source in targets:
            for link in LINK.findall(source.read_text(encoding="utf-8")):
                if "#" not in link or "://" in link:
                    continue
                path, anchor = link.split("#", 1)
                target = (source.parent / path).resolve() if path else source
                if target.suffix != ".md":
                    continue
                with self.subTest(source=source.name, link=link):
                    self.assertTrue(target.is_file(), link)
                    self.assertIn(anchor, anchors(target))


class ReadmeDriftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        for relative in ("README.md", "VERSION", CATALOG.as_posix()):
            (self.repo / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / relative, self.repo / relative)
        for name in plugin_names(REPO):
            (self.repo / "plugins" / name).mkdir(parents=True, exist_ok=True)

    def test_copy_is_consistent(self):
        self.assertEqual(check_readme(self.repo), [])

    def test_new_plugin_missing_from_readme_fails(self):
        (self.repo / "plugins" / "new-plugin").mkdir()
        errors = "\n".join(check_readme(self.repo))
        for name in ("Claude Code", "Codex", "ZCode"):
            self.assertIn("README {} Install is missing plugin new-plugin".format(name), errors)
        self.assertNotIn("OpenCode", errors)

    def test_version_change_without_readme_fails(self):
        version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
        (self.repo / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        errors = "\n".join(check_readme(self.repo))
        for name in ("Claude Code", "Codex", "ZCode", "OpenCode", "DeepSeek Harness"):
            self.assertIn("README {} Install command has v{}; VERSION is 9.9.9".format(name, version), errors)
        self.assertIn("README overview has v{}; VERSION is 9.9.9".format(version), errors)

    def test_catalog_and_readme_disagree_fails(self):
        path = self.repo / CATALOG
        catalog = json.loads(path.read_text(encoding="utf-8"))
        codex = next(agent for agent in catalog["agents"] if agent["id"] == "codex")
        codex["commands"]["install"][1]["argv"][2] = "install"
        path.write_text(json.dumps(catalog), encoding="utf-8")
        errors = check_readme(self.repo)
        self.assertTrue(errors)
        self.assertTrue(all(error.startswith("README Codex Install is missing plugin") for error in errors), errors)
        self.assertIn("codex plugin install prepare-work@forge-steward", "\n".join(errors))

    def test_reordered_readme_steps_fail(self):
        readme = self.repo / "README.md"
        text = readme.read_text(encoding="utf-8")
        version = (REPO / "VERSION").read_text(encoding="utf-8").strip()
        add = "codex plugin marketplace add philfanzhou/ForgeSteward --ref v{}\n".format(version)
        remove = "codex plugin marketplace remove forge-steward\n"
        upgrade = remove + add
        self.assertIn(upgrade, text)
        readme.write_text(text.replace(upgrade, add + remove, 1), encoding="utf-8")
        self.assertIn("README Codex Upgrade command order differs from catalog", "\n".join(check_readme(self.repo)))


if __name__ == "__main__":
    unittest.main()
