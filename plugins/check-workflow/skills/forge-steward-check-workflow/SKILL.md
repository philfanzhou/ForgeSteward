---
name: forge-steward-check-workflow
description: Sync the ForgeSteward standard workflow block and agent entry import into a repository from the bundled template, replacing any block content that differs, then submit the change as a PR or MR without merging. Text outside the managed block is never changed. Explicit check-only requests remain read-only.
---

# Check Workflow

## 目标与授权

让目标仓库包含 ForgeSteward 工作流所需的标准约束区块。区块正文由本技能随包提供的模板唯一确定，不由 Agent 根据仓库情况撰写、改写或裁剪：目标仓库没有区块或区块内容与模板不同时，整体替换为模板；一致时不做任何修改。同一技能版本重复运行，不会产生新的差异。

用户明确调用本技能（包括仅选择技能、不附加 prompt）时，默认任务是：检查 → 同步区块和入口 → 验证 → commit、push 并创建 Change Request（PR/MR），禁止合并。用户本轮的明确限制优先：仅检查时只运行检查并报告，不写文件、不建分支；仅本地修改时不提交或推送。自动选中本技能、引用技能名称或询问用法，不构成外部发布授权。遵守目标仓库的权限、审批及交付规则，不以默认流程绕过限制。

## 管理范围

只管理以下内容，区块外的文字不评价、不修改：

- 根目录 `AGENTS.md` 中从 `<!-- forge-steward:workflow begin lang=… -->` 到 `<!-- forge-steward:workflow end -->` 的区块，正文取自 `assets/workflow.<语言>.md`。文件不存在时创建，没有区块时追加到文件末尾。
- 根目录 `CLAUDE.md` 中的 `@AGENTS.md` 导入行，缺少时追加到文件末尾，文件不存在时创建。
- `CLAUDE.md` 另有其他内容时，`AGENTS.md` 中的 `forge-steward:claude-rules` 读取指示区块，正文取自 `assets/claude-rules.<语言>.md`，首次写入时紧随工作流区块，已存在时原位更新；`CLAUDE.md` 不再有其他内容时移除该区块。

项目与模板不同的要求，由项目写在区块之外；模板正文已声明区块外的项目规则优先。不为适配项目改动区块正文，也不把区块外的规则搬进区块。不修改业务代码、依赖、测试、CI、分支保护、全局或用户级 Agent 配置；不安装插件，不整理 Issue，不自动运行其他技能，不合并。各 Agent 的加载关系和已知限制见 [Agent 入口适配](references/agent-entrypoints.md)。

## 执行步骤

1. 定位目标仓库根目录、主线和工作区状态，记录已有改动，不覆盖用户工作。默认交付模式下刷新远端主线，查找源分支为 `forge-steward/workflow-block` 的开放 Change Request；目标仓库规范另有分支命名要求时，改用一个符合规范的固定分支名，并在后续运行中沿用。
2. 确定语言：已有工作流区块时沿用其 `lang`，不传 `--lang`；用户指定语言时使用指定值；首次同步时，项目主要的 Agent 指令或 README 以中文编写则用 `zh-CN`，否则用 `en`。模板只提供 `zh-CN` 和 `en`，不自行翻译。
3. 基于最新主线的内容运行检查，`<skill>` 为本技能目录：

   ```bash
   python3 <skill>/scripts/sync_workflow_block.py --repo <仓库根目录> --check [--lang zh-CN|en]
   ```

   - 退出码 `0`：已与模板一致。零修改结束，不创建分支、commit 或 Change Request；若存在第 1 步的开放 Change Request，报告它已不再需要，不自动关闭。
   - 退出码 `1`：需要同步，输出列出将修改的文件及原因。
   - 退出码 `2`：标记不成对或嵌套、代码围栏未闭合、文件不是 UTF-8 普通文件、首次同步未指定语言等。报告原因后停止写入，不猜测修复方式。
   - 输出中的 `Warning` 只报告、不处理。例如根目录存在 `AGENTS.override.md` 时，Codex 在该目录读取 override 而看不到区块，报告为入口缺口。
4. 需要同步时：已有第 1 步的开放 Change Request，就在其分支上继续，按仓库规范合入最新主线（不允许强推时使用 merge）；否则基于最新主线创建该分支。随后运行同一命令的 `--write`，再运行 `--check`，必须得到退出码 `0`。
5. 核对 diff：只包含管理范围内的变化，区块外原有文字逐字节保留（脚本保留原有各行的换行符和 BOM，新增行使用文件中占多数的换行符）。发现其他变化时撤回并报告。
6. 环境没有 Python 3 时，按脚本的同一规则手工操作：把模板文件内容逐字放入标记之间，不改动任何字符，完成后逐行比对区块与模板。无法保证逐字一致时只报告，不提交。

## 提交与交接

1. 默认交付模式下，只暂存本任务修改的 `AGENTS.md` 和 `CLAUDE.md`，按目标仓库规范 commit、push，并创建或更新指向主线的 Change Request，不重复开 PR/MR。标题、正文语言和模板遵守目标仓库规则。
2. Change Request 正文说明：技能版本、区块语言、修改的文件和原因（新建、同步区块、追加导入、增删读取指示）、检查命令及退出码、`Warning` 和未解决的入口缺口。
3. 创建或推送的响应不明确时，先查询远端分支和同源 Change Request，确认后再重试。权限、认证、网络或仓库门禁阻止继续时，保存本地提交或差异，准确说明停在未提交、已提交未推送、已推送未建 PR/MR 中的哪一步。
4. 回读实际 Change Request 的链接、base/head 与状态后结束；不等待合并，不自行审查或合并。

用目标项目约定的语言汇报：操作模式、区块语言、检查命令与退出码、修改的文件、`Warning`、Change Request 链接或零修改结论、未完成事项和下一步。只宣称“区块与模板一致、入口文件已按规则写入”；没有运行目标 Agent 时，不宣称其运行时已加载这些规则。
