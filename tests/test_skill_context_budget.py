"""防止 prepare-work 入口再次超出 Codex 注入预算或丢失分阶段规则。"""

from pathlib import Path
import re
import unittest


SKILL = (Path(__file__).resolve().parents[1] / "plugins/prepare-work/skills"
         / "forge-steward-prepare-work")
# 上游当前主提示词上限为 8,000 UTF-8 字节；本项目保留 2,000 字节余量。
# 引用文件也限制单次读取规模，但这不是 Codex 工具输出的通用上限。
FILE_BUDGET_BYTES = 6_000


class SkillContextBudgetTests(unittest.TestCase):
    def test_prepare_entrypoint_and_references_fit_byte_budget(self):
        for path in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]:
            with self.subTest(file=path.name):
                self.assertLessEqual(len(path.read_bytes()), FILE_BUDGET_BYTES,
                                     "请将详细规则拆到按阶段读取的引用文件")

    def test_prepare_references_are_local_existing_and_reachable(self):
        visited = set()
        pending = [SKILL / "SKILL.md"]
        while pending:
            source = pending.pop().resolve()
            if source in visited:
                continue
            visited.add(source)
            for link in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
                if "://" in link or link.startswith("#"):
                    continue
                target = (source.parent / link.split("#", 1)[0]).resolve()
                self.assertIn(SKILL.resolve(), target.parents, link)
                self.assertTrue(target.is_file(), link)
                if target.suffix == ".md":
                    pending.append(target)
        references = {p.resolve() for p in (SKILL / "references").rglob("*.md")}
        self.assertTrue(references, "详细规则必须随技能分发")
        self.assertTrue(references.issubset(visited), "引用规则必须能从入口找到")


if __name__ == "__main__":
    unittest.main()
