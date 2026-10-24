#!/usr/bin/env python3
"""Check packaged stage-skill VERSION markers against one expected unified version.

A stage runs this read-only command against its own skill directory before its first
write. Exit 0 means every supplied directory matches; exit 1 lists each missing,
unreadable, or mismatched marker with the expected and actual values; exit 2 is a
usage error.
"""

import argparse
from pathlib import Path
import re
import sys


VERSION = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--expected", required=True,
                        help="expected unified version from the orchestrator's scripts/VERSION")
    result.add_argument("--skill-dir", action="append", required=True, default=[],
                        help="stage skill directory containing VERSION; repeat for each stage")
    result.add_argument("--rules-manifest", type=Path,
                        help="validate the complete retained set before checking stage markers")
    result.add_argument("--rules-identity", help="original pinned rule-set identity from run evidence")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    expected = args.expected.strip()
    if not VERSION.fullmatch(expected):
        print("preflight: invalid --expected version: " + repr(args.expected), file=sys.stderr)
        return 2
    if bool(args.rules_manifest) != bool(args.rules_identity):
        print("preflight: --rules-manifest and --rules-identity must be supplied together", file=sys.stderr)
        return 2
    if args.rules_manifest:
        try:
            sys.dont_write_bytecode = True
            from rule_snapshot import validate
            retained = validate(args.rules_manifest, args.rules_identity, expected)
            allowed = set(retained["packages"].values())
            for value in args.skill_dir:
                if str(Path(value).absolute()) not in allowed:
                    raise ValueError(f"{value}: stage must use its verified retained directory")
            print("preflight: retained rule-set identity " + retained["identity"])
        except (ImportError, OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
            print("preflight: retained rules invalid: {}. Stop writes; preserve run state and "
                  "original wait deadlines for explicit recovery.".format(error), file=sys.stderr)
            return 1
    gaps = 0
    for value in args.skill_dir:
        marker = Path(value) / "VERSION"
        try:
            if not marker.is_file():
                print("preflight: missing VERSION: {} (expected {})".format(marker, expected),
                      file=sys.stderr)
                gaps += 1
                continue
            actual = marker.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as error:
            print("preflight: unreadable VERSION: {}: {} (expected {})".format(
                marker, error, expected), file=sys.stderr)
            gaps += 1
            continue
        if actual != expected:
            print("preflight: version mismatch: {} is {} (expected {})".format(
                marker, actual or "<empty>", expected), file=sys.stderr)
            gaps += 1
            continue
        print("preflight: ok: {} {}".format(marker, actual))
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
