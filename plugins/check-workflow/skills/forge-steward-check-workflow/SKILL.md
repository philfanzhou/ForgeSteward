---
name: forge-steward-check-workflow
description: Check branch cleanup settings, reconcile release tags, announcements and package feeds read-only, and remove workflow rules that duplicate the ForgeSteward skills from agent instructions, contributor docs and issue or change-request templates. Submit any deletion as a PR or MR without merging. Project conventions remain intact; release findings are reported only. Explicit check-only requests remain read-only.
---

# Check Workflow

## 规则加载

开始检查前，完整读取 [技能管理的规则与删除方式](references/skill-owned-rules.md)、[检查、删除与提交步骤](references/procedure.md) 和 [发布管线健康对账](references/release-audit.md)，再按本次授权模式执行。只读检查同样需要这些判定和执行规则；不能只凭入口摘要选择删除项。核对其他技能的等价条款时，同时检查该技能入口指向的规则文件。

引用文件是本技能的必需规则，路径以本 `SKILL.md` 所在目录为基准，不以目标仓库或当前工作目录为基准。工具输出被截断时按行或段补读至文件末尾；文件缺失或不可读时说明具体路径和影响，不依据不完整规则继续受影响的操作。上下文压缩后，缺失当前阶段规则时重新读取对应文件。

## 目标与授权

工作流政策只在 ForgeSteward 的 prepare-work、execute-work、review-and-merge 和 fix-feedback 技能正文中维护，包括：Issue 开工前的条件、任务大小、Change Request 范围、审查意见分类与轮数、修复范围、合并与关闭任务、交接和授权。项目里另写一套同类规则，无论与技能措辞相同、更严格还是更宽松，都会形成第二个规则来源：技能执行时出现冲突，技能升级后项目规则又会过时。本技能删除这些规则，使工作流政策只以技能为准。

本技能对受版本控制的项目文件只删除、不写入：不向项目添加规则、标记区块、读取指示或 Agent 入口，也不代写替代条款。项目仍需要、但技能明确交由仓库决定的约定（见[项目约定](references/skill-owned-rules.md#项目约定保留)）予以保留。另以只读方式检查托管平台的合并后自动删除源分支设置，记录启用、停用或无法确认；不修改仓库设置。合并后的实际分支清理由 `review-and-merge` 执行，本技能不合并或删除分支。

用户明确调用本技能（包括仅选择技能、不附加 prompt）时，默认任务是：检查 → 删除 → 验证 → commit、push 并创建 Change Request（PR/MR），禁止合并。用户本轮的明确限制优先：仅检查时只报告删除候选，不写文件、不建分支；仅本地修改时不提交或推送。自动选中本技能、引用技能名称或询问用法，不构成外部发布授权。遵守目标仓库的权限、审批及分支保护，不以默认流程绕过限制。

## 管理范围

- **删除工作流政策条文**：候选文件中属于[技能管理的工作流政策](references/skill-owned-rules.md#技能管理的工作流政策)的规则句、列表项、章节、模板说明和检查项，不区分是项目自行编写还是旧版本增补。
- **删除旧版标记区块**：`0.2.5`、`0.2.6` 写入根目录 `AGENTS.md` 的 `forge-steward:workflow` 与 `forge-steward:claude-rules` 区块，由脚本确定性删除。
- **删除悬空引用**：全部内容都是工作流政策的文档整份删除；指向被删章节或文档的链接、目录项和读取指示一并删除。

候选位置、判定方法、不删除的情形和删除方式见 [技能管理的规则与删除方式](references/skill-owned-rules.md)。不修改业务代码、依赖、测试、CI、分支保护、全局或用户级 Agent 配置；不修改 `CLAUDE.md` 的 `@AGENTS.md` 等入口导入，除非导入目标因本次删除而不存在；不安装插件，不整理 Issue，不自动运行其他技能，不合并。

### 发布管线健康对账（只读）

每次检查同时按 [发布对账规则](references/release-audit.md) 核对发布标签、发布公告（Release）与包 feed 的一致性、预发布标记、latest 指针及最近发布运行结果。判定基准和范围来自目标仓库自己的发布文档；缺少成文期望记为发现，对应判断为“无法确认”。结果只进最终汇报，与政策删除互不阻塞，沿用现有调用及 work-cycle 低频节奏。

## 汇报与变更汇总

结束前完整读取 [汇报与变更汇总规则](references/reporting.md)，按实际文件状态汇报删除变更及交付状态，并单列发布核对结论、发现、无法确认与不适用项。纯对账或其他零修改运行同样明确说明“未修改项目文件”；对账发现不进入清理 Change Request 正文，不登记或修复。进度说明和提问、汇报、子 Agent 交回的结果及 Issue、Change Request 的正文和评论都使用日常中文，不照搬本技能的内部术语，确需使用时首次附一句解释；artifact 一律写作“构建输出”。
