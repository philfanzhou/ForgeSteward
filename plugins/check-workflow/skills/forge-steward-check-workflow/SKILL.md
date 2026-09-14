---
name: forge-steward-check-workflow
description: Remove workflow policy rules that duplicate the ForgeSteward skills from a repository's agent instructions, contributor docs, and issue or change-request templates, including workflow blocks written by earlier check-workflow versions, then submit the deletion as a PR or MR without merging. Project conventions such as language, formats, build commands, and engineering constraints are kept. Explicit check-only requests remain read-only.
---

# Check Workflow

## 目标与授权

工作流政策只在 ForgeSteward 的 prepare-work、execute-work、review-and-merge 和 fix-feedback 技能正文中维护，包括：Issue ready 门禁、任务粒度、Change Request 范围、Review 分类与轮次、修复范围、合并后结项、交接和授权。项目里另写一套同类规则，无论与技能措辞相同、更严格还是更宽松，都会形成第二个规则来源：技能执行时出现冲突，技能升级后项目规则又会过时。本技能删除这些规则，使工作流政策只以技能为准。

本技能只删除，不写入：不向项目添加规则、标记区块、读取指示或 Agent 入口，也不代写替代条款。项目仍需要、但技能明确交由仓库决定的约定（见[项目约定](references/skill-owned-rules.md#项目约定保留)）予以保留。

用户明确调用本技能（包括仅选择技能、不附加 prompt）时，默认任务是：检查 → 删除 → 验证 → commit、push 并创建 Change Request（PR/MR），禁止合并。用户本轮的明确限制优先：仅检查时只报告删除候选，不写文件、不建分支；仅本地修改时不提交或推送。自动选中本技能、引用技能名称或询问用法，不构成外部发布授权。遵守目标仓库的权限、审批及分支保护，不以默认流程绕过限制。

## 管理范围

- **删除工作流政策条文**：候选文件中属于[技能管理的工作流政策](references/skill-owned-rules.md#技能管理的工作流政策)的规则句、列表项、章节、模板说明和检查项，不区分是项目自行编写还是旧版本增补。
- **删除旧版标记区块**：`0.2.5`、`0.2.6` 写入根目录 `AGENTS.md` 的 `forge-steward:workflow` 与 `forge-steward:claude-rules` 区块，由脚本确定性删除。
- **删除悬空引用**：全部内容都是工作流政策的文档整份删除；指向被删章节或文档的链接、目录项和读取指示一并删除。

候选位置、判定方法、不删除的情形和删除方式见 [技能管理的规则与删除方式](references/skill-owned-rules.md)。不修改业务代码、依赖、测试、CI、分支保护、全局或用户级 Agent 配置；不修改 `CLAUDE.md` 的 `@AGENTS.md` 等入口导入，除非导入目标因本次删除而不存在；不安装插件，不整理 Issue，不自动运行其他技能，不合并。

## 执行步骤

1. 定位目标仓库根目录、主线和工作区状态，记录已有改动，不覆盖用户工作。默认交付模式下刷新远端主线，查找源分支为 `forge-steward/remove-skill-duplicates` 的开放 Change Request；目标仓库规范另有分支命名要求时，改用一个符合规范的固定分支名，并在后续运行中沿用。存在旧版本遗留的 `forge-steward/workflow-block` 开放 Change Request 时，报告其已被本次变更取代，不自动关闭。
2. 基于最新主线运行旧版区块检查，`<skill>` 为本技能目录：

   ```bash
   python3 <skill>/scripts/remove_workflow_blocks.py --repo <仓库根目录> --check
   ```

   - 退出码 `0`：没有旧版区块。
   - 退出码 `1`：存在需要删除的区块，输出列出文件及原因。
   - 退出码 `2`：标记不成对或嵌套、代码围栏未闭合、文件不是 UTF-8 普通文件等。报告原因后停止写入，不猜测修复方式。
3. 基于同一主线识别工作流政策条文：读取全部候选位置，逐项对照参考文档的政策目录，记录文件、行范围、标题或首行、所属政策维度及对应技能、技能中的等价条款、处理方式（整段删除、删除分句、整份删除文档、删除引用），分为“确认删除”和“待维护者决定”。在对应技能正文中找不到等价语义的条文仍按参考文档处理，另记为“技能缺口”并保留原文。没有候选时记录已检查的位置。
4. 第 2 步退出码为 `0` 且第 3 步没有确认删除项时，零修改结束，不创建分支、commit 或 Change Request；若存在第 1 步的开放 Change Request，报告它已不再需要，不自动关闭。待决定项仍须在汇报中列出。
5. 需要变更时：已有第 1 步的开放 Change Request，就在其分支上继续，按仓库规范合入最新主线（不允许强推时使用 merge）；否则基于最新主线创建该分支。运行同一命令的 `--write` 删除区块，再按参考文档删除确认的条文，最后运行 `--check`，必须得到退出码 `0`。
6. 核对 diff：只允许出现删除。按分句删除时，被修改的行除删去的分句外逐字保留，不改写、合并或重新排版保留内容。删除后不得留下指向已删文档或章节的链接、目录项或读取指示，也不得留下只剩标题的空章节或断开的编号列表；需要改写保留内容才能消除时，撤回该项删除并改为待决定。发现其他变化时撤回并报告。
7. 环境没有 Python 3 时，按脚本的同一规则手工删除标记区块：从开始标记到结束标记整段删除，连同因此多出的一个空行；代码围栏中的标记不算区块。无法保证只删除区块时只报告，不提交。

## 提交与交接

1. 默认交付模式下，只暂存本任务修改或删除的文件。按目标仓库规范 commit、push，并创建或更新指向主线的 Change Request，不重复开 PR/MR。标题、正文语言和模板遵守目标仓库约定。
2. Change Request 正文说明：技能版本、检查命令及退出码；逐项列出删除内容（文件、原行范围、标题或首行、所属政策维度及对应技能、处理方式）和待维护者决定的候选及原因；单列技能缺口（原文、所属技能、缺少的语义）；说明删除后这些工作流约束只在调用 ForgeSteward 技能时生效，维护者可在审查中撤回任一删除。
3. 创建或推送的响应不明确时，先查询远端分支和同源 Change Request，确认后再重试。权限、认证、网络或仓库门禁阻止继续时，保存本地提交或差异，准确说明停在未提交、已提交未推送、已推送未建 PR/MR 中的哪一步。
4. 回读实际 Change Request 的链接、base/head 与状态后结束；不等待合并，不自行审查或合并。

## 汇报与变更汇总

结束时用目标项目约定的语言向用户汇报：操作模式、检查命令与退出码、Change Request 链接或零修改结论、待决定项、技能缺口、未完成事项和下一步。

本次运行修改了任何项目文件时（包括仅本地修改，或提交、推送、创建 Change Request 中途受阻），汇报中必须包含变更汇总。汇总依据实际的 `git status` 和 `git diff`（已提交时对比主线）填写，不按计划推测，不省略任何文件：

| 文件 | 操作 | 变更内容 | 行数 |
| --- | --- | --- | --- |

- **操作**：修改或删除。
- **变更内容**：写明删除的区块、章节、条文或引用（标题或首行、删除前行范围、所属政策维度及对应技能）。同一文件有多个动作时逐项列出。
- **行数**：该文件的新增与删除行数，例如 `+0 / -32`。

表后说明这些修改所处的状态：未提交、已提交（分支与 commit）、已推送，或已创建/更新的 Change Request 链接；再列出待维护者决定的候选，并注明未修改。变更汇总与 Change Request 正文中的变更说明保持一致。

没有修改任何项目文件时，明确说明“未修改项目文件”。仅检查模式下，另列执行删除时将修改的文件和原因，写明尚未修改，不写成已修改。

只宣称“确认的工作流政策条文和旧版区块已删除”；不宣称删除后项目中已不存在任何工作流约束，也不宣称各 Agent 运行时的行为已经改变。
