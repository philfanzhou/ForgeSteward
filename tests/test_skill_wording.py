"""禁止技能文件使用“分诊”“制品”等内部用语，并禁止文件或目录名含 triage。"""

from pathlib import Path
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
FORBIDDEN_TERMS = ("分诊", "制品")
FORBIDDEN_NAME_PART = "triage"


def find_forbidden_terms(root):
    """返回 root 下所有可按 UTF-8 解码的文件中出现禁用词的位置。"""
    hits = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for term in FORBIDDEN_TERMS:
                if term in line:
                    hits.append(f"{path.relative_to(root).as_posix()}:{number}: 含“{term}”")
    return hits


def find_forbidden_names(root):
    """返回 root 下文件或目录名含 triage（不区分大小写）的路径。"""
    return [
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if FORBIDDEN_NAME_PART in path.name.lower()
    ]


class SkillWordingTests(unittest.TestCase):
    def test_plugins_do_not_contain_forbidden_terms(self):
        plugins = REPO / "plugins"
        self.assertTrue(plugins.is_dir(), "plugins 目录必须存在，禁止空集合通过检查")
        hits = find_forbidden_terms(plugins)
        self.assertEqual(hits, [], "技能文件中出现禁用词：\n" + "\n".join(hits))

    def test_plugins_have_no_triage_names(self):
        hits = find_forbidden_names(REPO / "plugins")
        self.assertEqual(hits, [], "技能目录中有文件或目录名含 triage：\n" + "\n".join(hits))

    def test_checker_detects_forbidden_terms_and_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "demo" / "skills" / "demo"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("第一行\n先做轻量分诊\n", encoding="utf-8")
            (skill / "plugin.json").write_text('{"note": "制品"}\n', encoding="utf-8")
            (skill / "binary.bin").write_bytes(b"\xff\xfe\x00")
            self.assertEqual(
                find_forbidden_terms(root),
                [
                    "demo/skills/demo/SKILL.md:2: 含“分诊”",
                    "demo/skills/demo/plugin.json:1: 含“制品”",
                ],
            )
            self.assertEqual(find_forbidden_names(root), [])
            (skill / "references").mkdir()
            (skill / "references" / "Queue-And-Triage.md").write_text("初筛\n", encoding="utf-8")
            self.assertEqual(
                find_forbidden_names(root),
                ["demo/skills/demo/references/Queue-And-Triage.md"],
            )

    def test_checker_passes_clean_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "SKILL.md").write_text("先做初筛；artifact 一律写作“构建输出”。\n", encoding="utf-8")
            self.assertEqual(find_forbidden_terms(root), [])
            self.assertEqual(find_forbidden_names(root), [])


if __name__ == "__main__":
    unittest.main()
