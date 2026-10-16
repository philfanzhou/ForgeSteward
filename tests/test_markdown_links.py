"""Check repository-relative Markdown files and GitHub heading fragments, including duplicate headings."""

import html
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit


REPO = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\((?:<([^>]+)>|([^\s)]+))(?:\s+\"[^\"]*\")?\)")


def prose_lines(text):
    """Headings and links in fenced examples do not define document navigation."""
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield line


def slug(text):
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = html.unescape(re.sub(r"<[^>]*>", "", text)).lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(text):
    used = set()
    lines = list(prose_lines(text))
    for index, line in enumerate(lines):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)
        heading = match.group(1) if match else None
        if heading is None and index + 1 < len(lines) and re.fullmatch(r"\s{0,3}(?:=+|-+)\s*", lines[index + 1]) and line.strip():
            heading = line.strip()
        if heading is not None:
            base = slug(heading)
            candidate, suffix = base, 0
            while candidate in used:
                suffix += 1
                candidate = base + "-" + str(suffix)
            used.add(candidate)
    return used


def check_links(root, paths):
    problems = []
    for path in paths:
        for number, line in enumerate(prose_lines(path.read_text(encoding="utf-8")), 1):
            for match in LINK.finditer(line):
                raw = match.group(1) or match.group(2)
                url = urlsplit(raw)
                if url.scheme or url.netloc:
                    continue
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
                where = str(path.relative_to(root)) + ": " + raw
                if not target.exists():
                    problems.append(where + " (missing target)")
                elif url.fragment and target.suffix.lower() == ".md":
                    if unquote(url.fragment) not in anchors(target.read_text(encoding="utf-8")):
                        problems.append(where + " (missing heading)")
    return problems


class MarkdownLinkTests(unittest.TestCase):
    def test_all_repository_relative_links_and_fragments_resolve(self):
        output = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=REPO)
        paths = sorted({REPO / name for name in output.decode().split("\0") if name.endswith(".md")})
        self.assertTrue(paths)
        self.assertEqual(check_links(REPO, paths), [])

    def test_github_fragments_include_duplicate_suffixes_and_ignore_fences(self):
        text = "# A `heading` / test!\n## A heading / test!\n## A heading / test!-1\n## A heading / test!\n```md\n# Hidden\n```\n"
        self.assertEqual(anchors(text), {"a-heading--test", "a-heading--test-1", "a-heading--test-1-1", "a-heading--test-2"})
        self.assertEqual(anchors("A *title*\n===\n"), {"a-title"})

    def test_missing_paths_and_english_fragments_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target.md"
            target.write_text("# Same\n## Same\n", encoding="utf-8")
            source = root / "source.md"
            source.write_text("[valid](target.md#same-1) [bad](target.md#same-2) [missing](absent.md)\n", encoding="utf-8")
            self.assertEqual(check_links(root, [source]), ["source.md: target.md#same-2 (missing heading)",
                                                         "source.md: absent.md (missing target)"])


if __name__ == "__main__":
    unittest.main()
