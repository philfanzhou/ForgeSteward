"""The three stage packages carry one normalized feature-size sentence.

prepare-work, execute-work, and review-and-merge install independently, so each
package must carry the sentence in its own rules rather than link to another
package or to a shared file. These checks compare the sentence text only; they
prove wording consistency, not whether a model classifies a task correctly.
"""

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
# The canonical wording already shared by prepare-work and review-and-merge.
SENTENCE = (
    "at least three public protocol surfaces, at least three stateful outputs, "
    "or coupling multiple domains among transactions/concurrency, migration, "
    "sensitive data flows, and capability enablement"
)
# The execute-work variant that this change replaced.
OLD_SENTENCE = (
    "coupling several of transactions/concurrency, data migration, "
    "sensitive data flows, and capability enablement"
)
SENTENCE_PATTERN = re.compile(
    r"at least three public protocol surfaces.*?capability enablement",
    re.DOTALL,
)
FILES = {
    "prepare-work": REPO / "plugins/prepare-work/skills/forge-steward-prepare-work/references/readiness.md",
    "execute-work": REPO / "plugins/execute-work/skills/forge-steward-execute-work/references/queue.md",
    "review-and-merge": REPO / "plugins/review-and-merge/skills/forge-steward-review-and-merge/references/review.md",
}


def normalized(text):
    return re.sub(r"\s+", " ", text.replace("\r\n", "\n").replace("\r", "\n")).strip()


def extract(package, path):
    """Return the package's one feature-size sentence, normalized, and its raw text."""
    text = path.read_text(encoding="utf-8")
    sentences = SENTENCE_PATTERN.findall(text)
    if len(sentences) != 1:
        raise AssertionError(
            f"{package} ({path.relative_to(REPO).as_posix()}) must carry exactly one "
            f"feature-size sentence, found {len(sentences)}"
        )
    raw = sentences[0]
    return normalized(raw), raw, normalized(text)


class FeatureSizeSentenceTests(unittest.TestCase):
    def test_every_package_carries_the_canonical_sentence(self):
        for package, path in FILES.items():
            with self.subTest(package=package, file=path.relative_to(REPO).as_posix()):
                self.assertTrue(path.is_file(), f"{path} is missing")
                found, _, _ = extract(package, path)
                self.assertEqual(
                    found,
                    SENTENCE,
                    f"{package} does not carry the canonical feature-size sentence",
                )

    def test_sentence_is_identical_across_the_three_packages(self):
        found = {}
        for package, path in FILES.items():
            with self.subTest(package=package):
                found[package], _, _ = extract(package, path)
        self.assertEqual(
            len(set(found.values())),
            1,
            f"feature-size sentences differ across packages: {found}",
        )

    def test_packages_do_not_depend_on_another_file_for_the_sentence(self):
        for package, path in FILES.items():
            with self.subTest(package=package):
                _, raw, _ = extract(package, path)
                self.assertNotIn("](", raw, f"{package} links to another file inside the sentence")
                self.assertNotIn("../", raw, f"{package} points at another package inside the sentence")

    def test_the_old_execute_work_variant_is_gone(self):
        for package, path in FILES.items():
            with self.subTest(package=package):
                _, _, text = extract(package, path)
                self.assertNotIn(
                    OLD_SENTENCE,
                    text,
                    f"{package} still carries the old feature-size wording",
                )


if __name__ == "__main__":
    unittest.main()
