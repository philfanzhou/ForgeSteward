"""隔离托管平台替身：命令是一项平台操作，不负责派发或选择阶段。"""
import argparse
import json
import subprocess
from pathlib import Path


class Platform:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.file = self.root / "platform.json"
        self.state = json.loads(self.file.read_text(encoding="utf-8"))

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True,
                                       stderr=subprocess.STDOUT).strip()

    def save(self, operation, target=None):
        self.state["operations"].append({"key": "%s:%s:%d" % (operation, target, len(self.state["operations"])),
                                         "operation": operation, "target": target,
                                         "head": self.state["prs"].get(target, {}).get("head")})
        self.file.write_text(json.dumps(self.state, indent=2) + "\n", encoding="utf-8")

    def mutate(self):
        if self.state["constraints"]:
            raise ValueError("用户只读/不推送约束：禁止写入")
        if self.state["stopped"]:
            raise ValueError("用户已停止")

    def call(self, action, target="", head=""):
        if action == "view":
            return self.state
        if action == "prepare":
            self.mutate()
            # 原清单完整返回，包括会在 execute 遇到阻塞的成员。
            self.state["prepared"] = list(self.state["issues"])
            self.save(action)
            return self.state["prepared"]
        if action == "handoff":
            self.state["handoffs"].append(target)
            self.save(action, target)
            return {"persisted": target, "state": self.state}
        self.mutate()
        if action == "create":
            if not self.state["prepared"] or target not in self.state["prepared"]:
                raise ValueError("execute 必须有有效原 Issue 清单")
            if target in self.state["prs"]:
                raise ValueError("不重复创建：先 view 回查")
            self.git("switch", "-c", "fixture/" + target, "main")
            (self.root / (target + ".txt")).write_text("验收目标已实现\n", encoding="utf-8")
            self.git("add", target + ".txt")
            self.git("commit", "-qm", "Implement " + target)
            self.git("push", "-q", "origin", "HEAD")
            self.state["prs"][target] = {"head": self.git("rev-parse", "HEAD"), "round": 0,
                "reviewed": None, "feedback": None, "merged": False, "deleted": False}
        else:
            pr = self.state["prs"][target]
            if action == "review":
                pr["reviewed"] = pr["head"]
                pr["feedback"] = "required" if pr["round"] < self.state["required_rounds"].get(target, 0) else None
            elif action == "repair":
                if pr["feedback"] != "required" or pr["round"] >= 3:
                    raise ValueError("无可修反馈或已达三轮；禁止第四修复")
                self.git("switch", "fixture/" + target)
                with (self.root / (target + ".txt")).open("a", encoding="utf-8") as stream:
                    stream.write("修复 %d\n" % (pr["round"] + 1))
                self.git("add", target + ".txt")
                self.git("commit", "-qm", "Repair " + target)
                self.git("push", "-q", "origin", "HEAD")
                pr["head"] = self.git("rev-parse", "HEAD")
                pr["round"] += 1
                pr["reviewed"] = None
            elif action == "merge":
                if not self.state["approval"] or not self.state["checks"] or not self.state["protected"]:
                    raise ValueError("checks/审批/保护门禁未满足")
                if head != pr["head"] or pr["reviewed"] != head or pr["feedback"]:
                    raise ValueError("head 已变化、未审查或必修未解决")
                self.git("switch", "main")
                self.git("merge", "--no-edit", "fixture/" + target)
                self.git("push", "-q", "origin", "main")
                pr["merged"] = True
            elif action == "delete":
                if not pr["merged"] or self.git("status", "--porcelain", "--untracked-files=no"):
                    raise ValueError("未合并或工作区脏；不能清理")
                self.git("switch", "main")
                self.git("branch", "-d", "fixture/" + target)
                self.git("push", "-q", "origin", "--delete", "fixture/" + target)
                pr["deleted"] = True
            else:
                raise ValueError("未知平台操作")
        self.save(action, target)
        if action == "create" and self.state["uncertain"]:
            # 单次写已持久化；返回失败模拟连接断开，恢复只能回查。
            raise ValueError("写入回包未知：请 view 回查，不重复 create")
        return self.state["prs"][target]


def seed(root, scenario):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    remote = root / "remote.git"
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                       stderr=subprocess.STDOUT).strip()
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    git("init", "-q", "-b", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (root / ".gitignore").write_text(".dsh/\nremote.git/\nplatform.json\nAGENTS.md\nfixture.py\n", encoding="utf-8")
    (root / "baseline.txt").write_text("fixture\n", encoding="utf-8")
    git("add", ".gitignore", "baseline.txt")
    git("commit", "-qm", "Baseline")
    git("remote", "add", "origin", str(remote))
    git("push", "-q", "origin", "main")
    state = {"scenario": scenario, "issues": [] if scenario in ("startup", "constraints", "missing", "stop") else ["I1"],
             "prepared": [], "prs": {}, "required_rounds": {"I1": 1 if scenario == "repair" else 0},
             "approval": scenario != "waiting", "checks": True, "protected": True,
             "constraints": scenario == "constraints", "stopped": False, "uncertain": scenario == "uncertain",
             "operations": [], "handoffs": []}
    if scenario == "rounds":
        state["issues"] = ["I1", "I2"]
        state["required_rounds"]["I1"] = 4
    (root / "platform.json").write_text(json.dumps(state), encoding="utf-8")
    if scenario in ("startup", "constraints"):
        platform = Platform(root)
        platform.state["constraints"] = False
        platform.state["prepared"] = ["P0"]
        platform.call("create", "P0")
        platform.state["prepared"] = []
        platform.state["constraints"] = state["constraints"]
        platform.state["operations"] = []
        platform.save("seed")
        git("switch", "main")
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["view", "prepare", "create", "review", "repair", "merge", "delete", "handoff"])
    parser.add_argument("target", nargs="?", default="")
    parser.add_argument("--head", default="")
    args = parser.parse_args()
    try:
        print(json.dumps(Platform(Path.cwd()).call(args.action, args.target, args.head), ensure_ascii=False))
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + "\n")
