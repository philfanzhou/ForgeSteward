"""防止技能入口超出 Codex 注入预算或丢失分阶段规则。"""

from pathlib import Path
import re
import unittest


PLUGINS = Path(__file__).resolve().parents[1] / "plugins"
# 上游当前主提示词上限为 8,000 UTF-8 字节；本项目保留 2,000 字节余量。
ENTRYPOINT_BUDGET_BYTES = 6_000


class SkillContextBudgetTests(unittest.TestCase):
    def test_all_entrypoints_fit_byte_budget(self):
        skills = sorted(PLUGINS.glob("*/skills/*/SKILL.md"))
        self.assertTrue(skills, "必须存在可检查的技能入口")
        for path in skills:
            with self.subTest(skill=path.parent.name):
                self.assertLessEqual(len(path.read_bytes()), ENTRYPOINT_BUDGET_BYTES,
                                     "请将详细规则拆到按阶段读取的引用文件")

    def test_prepare_references_fit_read_budget(self):
        # 保留 prepare-work 已建立的分块读取预算；不是工具输出的通用上限。
        for path in (PLUGINS / "prepare-work/skills/forge-steward-prepare-work/references").glob("*.md"):
            with self.subTest(file=path.name):
                self.assertLessEqual(len(path.read_bytes()), 6_000)

    def test_all_references_are_local_existing_and_reachable(self):
        for entrypoint in sorted(PLUGINS.glob("*/skills/*/SKILL.md")):
            with self.subTest(skill=entrypoint.parent.name):
                self.check_references(entrypoint.parent)

    def check_references(self, skill):
        visited = set()
        pending = [skill / "SKILL.md"]
        while pending:
            source = pending.pop().resolve()
            if source in visited:
                continue
            visited.add(source)
            for link in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
                if "://" in link or link.startswith("#"):
                    continue
                target = (source.parent / link.split("#", 1)[0]).resolve()
                self.assertIn(skill.resolve(), target.parents, link)
                self.assertTrue(target.is_file(), link)
                if target.suffix == ".md":
                    pending.append(target)
        references = {p.resolve() for p in (skill / "references").rglob("*.md")}
        self.assertTrue(references.issubset(visited), "引用规则必须能从入口找到")


if __name__ == "__main__":
    unittest.main()
