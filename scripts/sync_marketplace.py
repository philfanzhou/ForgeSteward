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
        raise ValueError("VERSION 不是受支持的统一版本")
    catalog = json.loads((root / MARKETPLACE).read_text(encoding="utf-8"))
    directories = {p.name for p in (root / "plugins").iterdir() if p.is_dir()}
    entries = catalog["plugins"]
    names = [entry["name"] for entry in entries]
    if not directories or len(names) != len(set(names)) or set(names) != directories:
        raise ValueError("市场条目必须与插件目录一一对应，不能重复或遗漏")
    for entry in entries:
        plugin = root / "plugins" / entry["name"]
        if entry["source"] != "./plugins/" + entry["name"]:
            raise ValueError("市场来源必须指向同快照内的插件目录")
        for relative in ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            manifest = json.loads((plugin / relative).read_text(encoding="utf-8"))
            if manifest["name"] != entry["name"] or manifest["version"] != version:
                raise ValueError("先统一插件名称及版本：" + str(plugin / relative))
        entry["version"] = version
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="只检查，不写文件")
    mode.add_argument("--write", action="store_true", help="同步当前源码市场版本")
    args = parser.parse_args()
    try:
        expected = expected_marketplace(REPO)
        path = REPO / MARKETPLACE
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual == expected:
            print("市场版本与 VERSION 一致")
            return 0
        if args.check:
            print("市场版本未同步：运行 python3 scripts/sync_marketplace.py --write")
            return 1
        path.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("已同步市场派生版本")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
