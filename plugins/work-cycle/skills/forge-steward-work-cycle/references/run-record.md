## 运行记录与耗时

每次运行的交接、证据和各阶段耗时统一放在目标仓库 Git 公共目录的 `forge-steward/runs/<运行编号>/`，所有 worktree 共享，不改动受版本控制的文件，不放 `/tmp`。使用本技能包的 `scripts/run_record.py`：

```bash
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> start --cycles <轮数>
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> event --run <运行编号> --task <任务标识> --stage <阶段> --status <状态> [--wait <等待类型>] [--detail <说明>]
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> task-dir --run <运行编号> --task <任务标识>
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> summary --run <运行编号>
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> report --run <运行编号>
```

状态为 `started`、`finished`、`failed`、`wait-start`、`wait-end`；等待类型为 `ci`、`lock`、`review`、`external`、`other`。`report` 返回 `1` 表示 `handoff.json` 数据有问题；各命令返回 `2` 表示参数或环境错误。

### 找到可用的 Python

依次试 `python3 --version`、`py -3 --version`、`python --version`，用第一个能运行且版本不低于 3.9 的命令（避开 Windows 上只会打开应用商店的假入口）；本技能各规则中的 `python3` 都换成它。运行 `start` 前就确认，找不到时记入交接，运行照常进行，结束时按[最终汇报](report.md)手写。

### 编排 Agent

1. 启动检查后运行 `start`，取得运行编号和目录；它同时只保留最近 20 次由该脚本创建的运行目录，不碰其他文件。
2. 每派发一个子 Agent 前记 `started`，确认其结束后记 `finished` 或 `failed`；阶段用 `check-workflow`、`prepare`、`implement`、`review`、`fix`、`merge`、`cleanup`。任务标识与[资源锁](verification.md)的任务标识一致。
3. 派发时告知子 Agent：运行编号、`task-dir` 给出的证据目录，以及等待 CI、锁、审批等外部结果时用 `event` 记录 `wait-start`/`wait-end`。子 Agent 的证据文件和交接文件都放在自己的证据目录。
4. [轮次、交接与终止](cycles.md) 要求的编排短交接保存为运行目录下的 `handoff.json`，汇报要用的字段按[最终汇报](report.md)填写；上下文压缩或中断后先读取它恢复。
5. 结束时运行 `report`，把输出原样贴给用户；它读取 `handoff.json` 和事件记录，耗时取 `summary` 的结果，同时写入运行目录的 `report.md`。数据有错时的重试和脚本不可用时的手写兜底见[最终汇报](report.md)。

脚本无法运行或返回 `2` 时，在会话交接中说明并继续运行，不因记录失败中断交付；不要为此把证据改放到 `/tmp`，可写入会话交接。
