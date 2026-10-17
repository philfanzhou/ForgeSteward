"""The shared scenario matrix has unique IDs and resolvable references.

`docs/skill-owned-policy-scenarios.md` is the cross-Skill policy contract. A
duplicated ID makes a walkthrough or a prose reference such as "R15's safety
conditions" ambiguous. IDs are checked per document because other scenario
documents keep independent ID spaces; a reference to a label from another
document must name that document.
"""

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
SCENARIOS = REPO / "docs/skill-owned-policy-scenarios.md"
ID = r"[A-Z][0-9]{2}"
ROW = re.compile(rf"^\|\s*({ID})\s*\|")
TOKEN = re.compile(rf"\b({ID})\b")
RANGE = re.compile(rf"\b([A-Z])([0-9]{{2}})\s*[\u2013-]\s*([A-Z])([0-9]{{2}})\b")


def table_rows(text):
    """Return the scenario rows in order, keyed by ID, plus duplicate IDs."""
    rows = {}
    duplicates = []
    for line in text.splitlines():
        match = ROW.match(line)
        if not match:
            continue
        scenario_id = match.group(1)
        if scenario_id in rows and scenario_id not in duplicates:
            duplicates.append(scenario_id)
        rows[scenario_id] = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return rows, duplicates


def referenced_ids(text):
    """Return identifiers mentioned outside the ID column, expanding ID ranges."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    references = set()
    for line in text.splitlines():
        if ROW.match(line):
            cells = line.strip().strip("|").split("|")
            line = "|".join(cells[1:])
        for match in RANGE.finditer(line):
            first_letter, first_number, last_letter, last_number = match.groups()
            references.update(("".join((first_letter, first_number)), "".join((last_letter, last_number))))
            if first_letter == last_letter and int(first_number) <= int(last_number):
                references.update(
                    first_letter + str(number).zfill(2)
                    for number in range(int(first_number), int(last_number) + 1)
                )
        references.update(TOKEN.findall(line))
    return references


class ScenarioIdentifierTests(unittest.TestCase):
    def test_scenario_ids_are_unique(self):
        rows, duplicates = table_rows(SCENARIOS.read_text(encoding="utf-8"))
        self.assertTrue(rows, "the shared scenario matrix must contain at least one row")
        self.assertEqual(duplicates, [], "scenario IDs must identify exactly one row each")

    def test_every_referenced_id_exists(self):
        text = SCENARIOS.read_text(encoding="utf-8")
        rows, _ = table_rows(text)
        missing = sorted(referenced_ids(text) - set(rows))
        self.assertEqual(
            missing,
            [],
            "prose references must resolve to a row in this document; "
            "a label from another scenario document must name that document",
        )

    def test_cleanup_safety_references_point_at_the_cleanup_rule(self):
        rows, _ = table_rows(SCENARIOS.read_text(encoding="utf-8"))
        self.assertIn("R15", rows)
        cleanup = [cell.lower() for cell in rows["R15"]]
        self.assertEqual(cleanup[0], "r15")
        self.assertEqual(cleanup[1], "review-and-merge")
        self.assertIn("automatic deletion disabled", cleanup[2])
        self.assertIn("delete remote", cleanup[3])
        for row_id in ("R13", "R14"):
            with self.subTest(row=row_id):
                expected = rows[row_id][3].lower()
                self.assertIn("r15's safety conditions", expected)

    def test_range_expansion_finds_every_member(self):
        self.assertEqual(referenced_ids("(R15\u2013R18)\n"), {"R15", "R16", "R17", "R18"})
        self.assertEqual(referenced_ids("(R07-R10)\n"), {"R07", "R08", "R09", "R10"})

    def test_references_inside_table_cells_are_checked(self):
        text = (
            "| ID | Skill | Input | Expected result |\n"
            "| --- | --- | --- | --- |\n"
            "| R01 | review-and-merge | Some input | Delete under R02's safety conditions |\n"
        )
        self.assertEqual(referenced_ids(text), {"R02"})


if __name__ == "__main__":
    unittest.main()
