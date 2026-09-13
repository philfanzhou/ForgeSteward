"""同步 Claude / ZCode 市场的派生版本；不修改插件、用户配置或历史发布。"""

import argparse
import json
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[1]
MARKETPLACE = Path(".claude-plugin/marketplace.json")


def expected_marketplace(root):
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-rc\.(?:0|[1-9]\d*))?", version):
        raise ValueError("VERSION is not a supported unified version")
    catalog = json.loads((root / MARKETPLACE).read_text(encoding="utf-8"))
    directories = {p.name for p in (root / "plugins").iterdir() if p.is_dir()}
    entries = catalog["plugins"]
    names = [entry["name"] for entry in entries]
    if not directories or len(names) != len(set(names)) or set(names) != directories:
        raise ValueError("Marketplace entries must match plugin directories without duplicates or omissions")
    for entry in entries:
        plugin = root / "plugins" / entry["name"]
        if entry["source"] != "./plugins/" + entry["name"]:
            raise ValueError("Marketplace sources must reference plugins in the same snapshot")
        for relative in ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            manifest = json.loads((plugin / relative).read_text(encoding="utf-8"))
            if manifest["name"] != entry["name"] or manifest["version"] != version:
                raise ValueError("Synchronize plugin names and versions first: " + str(plugin / relative))
        entry["version"] = version
    return catalog


def main():
    # CLI 输出采用英文，兼容 Windows Python 3.9 重定向时的默认单字节编码。
    parser = argparse.ArgumentParser(description="Sync derived Claude / ZCode marketplace versions.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Check without writing files")
    mode.add_argument("--write", action="store_true", help="Sync versions in the source marketplace")
    args = parser.parse_args()
    try:
        expected = expected_marketplace(REPO)
        path = REPO / MARKETPLACE
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual == expected:
            print("Marketplace versions match VERSION")
            return 0
        if args.check:
            print("Marketplace versions differ: run python3 scripts/sync_marketplace.py --write")
            return 1
        path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Synchronized derived marketplace versions")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
