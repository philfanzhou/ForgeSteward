"""Check all maintained text for English wording and retain the plugin path restriction.

This static check finds non-ASCII letters and CJK punctuation, including escaped
messages. It complements semantic review: English text can still prescribe the
wrong output language. Unicode boundary/path probes construct explicit code
points; only the two validated legacy-key fields in report-spec are exceptions.
"""

import ast
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import tokenize
import unicodedata
import unittest


REPO = Path(__file__).resolve().parents[1]
REPORT = "plugins/work-cycle/skills/forge-steward-work-cycle/references/report.md"
ESCAPE = re.compile(r"\\(?:u([0-9a-fA-F]{4})|U([0-9a-fA-F]{8})|x([0-9a-fA-F]{2}))")
# CJK sentence punctuation is wording, unlike neutral arrows, math signs, or emoji.
CJK_PUNCTUATION = {0x3001, 0x3002, 0xFF0C, 0xFF1A, 0xFF1B, 0xFF01, 0xFF1F, 0xFF08, 0xFF09}


def non_english(text):
    return any((ord(c) > 127 and unicodedata.category(c).startswith("L"))
               or ord(c) in CJK_PUNCTUATION for c in text)


def decode_escapes(text):
    return ESCAPE.sub(lambda m: chr(int(next(g for g in m.groups() if g is not None), 16)), text)


def files_to_check(root):
    """Git inventory includes hidden and newly staged files, plus untracked additions."""
    output = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root)
    names = sorted(set(output.decode("utf-8").split("\0")) - {""})
    if not names:
        raise ValueError("No repository files found; an empty inventory must not pass")
    return names


def mask_legacy_keys(name, text):
    """Allow only alias keys in the one report spec, with targets in its current vocabulary."""
    if name != REPORT:
        return text
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    match = re.search(r"```json report-spec\n(.*?)\n```", text, re.S)
    if not match:
        raise ValueError("Missing report-spec")
    spec = json.loads(match.group(1))
    block = match.group(1)
    for aliases, current in ((spec["result_aliases"], spec["results"]),
                             (spec["agents"]["aliases"], [spec["agents"]["absent"], *spec["agents"]["statuses"]])):
        if (len(aliases) != 7 or len(set(aliases.values())) != 7
                or any(not non_english(key) or value not in current for key, value in aliases.items())):
            raise ValueError("Invalid legacy input aliases")
        for key, value in aliases.items():
            # Match the exact escaped key/value pair, never a file, line, or free-text field.
            pair = json.dumps(key, ensure_ascii=True) + ": " + json.dumps(value)
            if block.count(pair) != 1:
                raise ValueError("Legacy aliases must use one exact escaped key/value pair")
            block = block.replace(pair, '"legacy input": ' + json.dumps(value))
    return text[:match.start(1)] + block + text[match.end(1):]


def decoded_strings(name, text):
    """Check decoded Python and JSON/JSONL, plus Unicode escapes in all text including YAML."""
    if name.endswith(".py"):
        # Byte literals encode technical bytes (for example UTF-8 BOM), not Latin text.
        # Decode valid UTF-8 byte messages separately; keep invalid-byte test data intact.
        tokens = []
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.STRING and re.match(r"(?i)^[br]*b[br]*[\"\']", token.string):
                token = tokenize.TokenInfo(token.type, "b''", token.start, token.end, token.line)
            tokens.append(token)
        yield decode_escapes(tokenize.untokenize(tokens))
        for node in ast.walk(ast.parse(text, filename=name)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield decode_escapes(node.value)
            elif isinstance(node, ast.Constant) and isinstance(node.value, bytes):
                try:
                    yield node.value.decode("utf-8")
                except UnicodeError:
                    pass
    else:
        yield decode_escapes(text)
    if name.endswith((".json", ".jsonl")):
        values = [json.loads(line) for line in text.splitlines() if line.strip()] if name.endswith(".jsonl") else [json.loads(text)]
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for k, v in value.items():
                    yield k
                    yield from strings(v)
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
        for value in values:
            yield from strings(value)


def find_non_english(root):
    hits = []
    for name in files_to_check(root):
        path = root / name
        try:
            text = path.read_bytes().decode("utf-8")
            if non_english(name):
                hits.append(name + ": non-English path")
            raw = [str(n) for n, line in enumerate(text.splitlines(), 1) if non_english(line)]
            if raw:
                hits.append(name + ": non-English wording on lines " + ", ".join(raw))
            checked = mask_legacy_keys(name, text)
            if any(non_english(value) for value in decoded_strings(name, checked)) and not raw:
                hits.append(name + ": non-English decoded string")
        except (OSError, UnicodeError, ValueError, SyntaxError, KeyError, TypeError) as error:
            hits.append(name + ": cannot inspect text: " + str(error))
    return hits


def find_forbidden_names(root):
    """Plugin file and directory names must not contain the old workflow term."""
    return [path.relative_to(root).as_posix() for path in sorted(root.rglob("*"))
            if "triage" in path.name.lower()]


class SkillWordingTests(unittest.TestCase):
    def test_all_repository_text_is_english(self):
        hits = find_non_english(REPO)
        self.assertEqual(hits, [], "Non-English maintained text:\n" + "\n".join(hits))

    def test_plugins_have_no_triage_names(self):
        self.assertTrue((REPO / "plugins").is_dir())
        self.assertEqual(find_forbidden_names(REPO / "plugins"), [])

    def test_new_hidden_and_staged_content_and_escapes_are_checked(self):
        # U+4E2D is technical foreign-letter input; U+00E9 also checks non-CJK letters.
        letter = chr(0x4E2D)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            cases = {"docs/new.md": letter, "src/message.py": "message = " + repr(letter),
                     ".hidden/settings.json": json.dumps({"note": letter}),
                     ".github/new.yml": 'note: "' + json.dumps(letter)[1:-1] + '"',
                     "plugins/new/skills/new/SKILL.md": letter,
                     "src/escaped.py": "message = " + ascii(letter),
                     "src/bytes.py": "message = " + repr(letter.encode("utf-8")),
                     "records.jsonl": json.dumps({"note": letter}) + "\n",
                     "other.md": chr(0x00E9)}
            for name, value in cases.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            self.assertEqual({line.split(":")[0] for line in find_non_english(root)}, set(cases))
            (root / "later.md").write_text(letter, encoding="utf-8")
            self.assertIn("later.md", {line.split(":")[0] for line in find_non_english(root)})

    def test_unreadable_or_non_utf8_text_never_silently_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "bad.txt").write_bytes(b"\xff")
            self.assertIn("cannot inspect text", find_non_english(root)[0])
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            (root / "bad.txt").unlink()
            self.assertIn("cannot inspect text", find_non_english(root)[0])

    def test_neutral_unicode_is_allowed_but_punctuation_is_not(self):
        self.assertFalse(non_english("English → ± 😀"))
        self.assertTrue(non_english(chr(0xFF1A)))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Queue-And-Triage.md").write_text("Screen the queue.\n", encoding="utf-8")
            self.assertEqual(find_forbidden_names(root), ["Queue-And-Triage.md"])

    def test_alias_exception_is_limited_to_exact_fields_and_valid_targets(self):
        original = (REPO / REPORT).read_text(encoding="utf-8")
        self.assertFalse(non_english(decode_escapes(mask_legacy_keys(REPORT, original))))
        self.assertFalse(non_english(decode_escapes(mask_legacy_keys(REPORT, original.replace("\n", "\r\n")))))
        # A new escaped message anywhere outside the alias keys must still be detected.
        injected = original + "\n" + json.dumps(chr(0x4E2D))
        self.assertTrue(non_english(decode_escapes(mask_legacy_keys(REPORT, injected))))
        with self.assertRaises(ValueError):
            mask_legacy_keys(REPORT, original.replace('"Merged",', '"Invalid",', 1))


if __name__ == "__main__":
    unittest.main()
