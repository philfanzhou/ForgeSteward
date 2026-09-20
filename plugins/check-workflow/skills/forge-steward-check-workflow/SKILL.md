---
name: forge-steward-check-workflow
description: Remove workflow policy rules that duplicate the ForgeSteward skills from a repository's agent instructions, contributor docs, and issue or change-request templates, including workflow blocks written by earlier check-workflow versions, then submit the deletion as a PR or MR without merging. Project conventions such as language, formats, build commands, and engineering constraints are kept. Explicit check-only requests remain read-only.
---

# Check Workflow

## 规则加载

开始检查前，完整读取 [技能管理的规则与删除方式](references/skill-owned-rules.md) 和 [检查、删除与提交步骤](references/procedure.md)，再按本次授权模式执行。只读检查同样需要这些判定和执行规则；不能只凭入口摘要选择删除项。核对其他技能的等价条款时，同时检查该技能入口指向的规则文件。

引用文件是本技能的必需规则，路径以本 `SKILL.md` 所在目录为基准，不以目标仓库或当前工作目录为基准。工具输出被截断时按行或段补读至文件末尾；文件缺失或不可读时说明具体路径和影响，不依据不完整规则继续受影响的操作。上下文压缩后，缺失当前阶段规则时重新读取对应文件。

## 目标与授权

工作流政策只在 ForgeSteward 的 prepare-work、execute-work、review-and-merge 和 fix-feedback 技能正文中维护，包括：Issue ready 门禁、任务粒度、Change Request 范围、Review 分类与轮次、修复范围、合并后结项、交接和授权。项目里另写一套同类规则，无论与技能措辞相同、更严格还是更宽松，都会形成第二个规则来源：技能执行时出现冲突，技能升级后项目规则又会过时。本技能删除这些规则，使工作流政策只以技能为准。

本技能只删除，不写入：不向项目添加规则、标记区块、读取指示或 Agent 入口，也不代写替代条款。项目仍需要、但技能明确交由仓库决定的约定（见[项目约定](references/skill-owned-rules.md#项目约定保留)）予以保留。

用户明确调用本技能（包括仅选择技能、不附加 prompt）时，默认任务是：检查 → 删除 → 验证 → commit、push 并创建 Change Request（PR/MR），禁止合并。用户本轮的明确限制优先：仅检查时只报告删除候选，不写文件、不建分支；仅本地修改时不提交或推送。自动选中本技能、引用技能名称或询问用法，不构成外部发布授权。遵守目标仓库的权限、审批及分支保护，不以默认流程绕过限制。

## 管理范围

- **删除工作流政策条文**：候选文件中属于[技能管理的工作流政策](references/skill-owned-rules.md#技能管理的工作流政策)的规则句、列表项、章节、模板说明和检查项，不区分是项目自行编写还是旧版本增补。
- **删除旧版标记区块**：`0.2.5`、`0.2.6` 写入根目录 `AGENTS.md` 的 `forge-steward:workflow` 与 `forge-steward:claude-rules` 区块，由脚本确定性删除。
- **删除悬空引用**：全部内容都是工作流政策的文档整份删除；指向被删章节或文档的链接、目录项和读取指示一并删除。

候选位置、判定方法、不删除的情形和删除方式见 [技能管理的规则与删除方式](references/skill-owned-rules.md)。不修改业务代码、依赖、测试、CI、分支保护、全局或用户级 Agent 配置；不修改 `CLAUDE.md` 的 `@AGENTS.md` 等入口导入，除非导入目标因本次删除而不存在；不安装插件，不整理 Issue，不自动运行其他技能，不合并。

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
