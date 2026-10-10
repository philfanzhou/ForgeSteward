## 运行记录与耗时

每次运行的交接、证据和各阶段耗时统一放在目标仓库 Git 公共目录的 `forge-steward/runs/<运行编号>/`，所有 worktree 共享，不改动受版本控制的文件，不放 `/tmp`。使用本技能包的 `scripts/run_record.py`：

```bash
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> start --cycles <轮数>
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> event --run <运行编号> --task <任务标识> --stage <阶段> --status <状态> [--wait <等待类型>] [--detail <说明>]
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> task-dir --run <运行编号> --task <任务标识>
python3 <本技能目录>/scripts/run_record.py --repo <目标仓库> summary --run <运行编号>
```

状态为 `started`、`finished`、`failed`、`wait-start`、`wait-end`；等待类型为 `ci`、`lock`、`review`、`external`、`other`。返回 `2` 表示参数或环境错误。

### 编排 Agent

1. 启动检查后运行 `start`，取得运行编号和目录；它同时只保留最近 20 次由该脚本创建的运行目录，不碰其他文件。
2. 每派发一个子 Agent 前记 `started`，确认其结束后记 `finished` 或 `failed`；阶段用 `check-workflow`、`prepare`、`implement`、`review`、`fix`、`merge`、`cleanup`。任务标识与[资源锁](verification.md)的任务标识一致。
3. 派发时告知子 Agent：运行编号、`task-dir` 给出的证据目录，以及等待 CI、锁、审批等外部结果时用 `event` 记录 `wait-start`/`wait-end`。子 Agent 的证据文件和交接文件都放在自己的证据目录。
4. [轮次、交接与终止](cycles.md) 要求的编排短交接保存为运行目录下的 `handoff.json`，上下文压缩或中断后先读取它恢复。
5. 最终报告附 `summary` 的结果，用日常说法写明：整次运行耗时、各阶段合计耗时、等 CI 与等锁的合计时间。

脚本无法运行或返回 `2` 时，在会话交接中说明并继续运行，不因记录失败中断交付；不要为此把证据改放到 `/tmp`，可写入会话交接。
