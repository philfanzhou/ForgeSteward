---
name: forge-steward-prepare-work
description: Prepare repository issues for implementation by investigating mainline blockers, resolving actionable technical questions, and persisting scope, acceptance criteria, and audit evidence. Return only a single-line list of independent ready issues, filling the batch first with backlog issues that were open at the cleanup-cycle baseline (including their split tasks and unblocking prerequisites) up to the default limit of 10 or the user's requested count, and only then with urgent or other newly created issues, without implementing them or generating an execution prompt. Use for work discovery, issue preparation, or advancing blocked tasks toward a PR; not for production implementation or review repair.
---

# Prepare Work

## 规则加载（先于准备操作）

本文件是入口，详细规则保存在同一技能目录的 `references/` 中。相对路径以本 `SKILL.md` 所在目录为基准，不以目标仓库或当前工作目录为基准。使用可用文件读取工具，按下列阶段完整读取对应文件后再执行该阶段；这些文件是必需规则，不是可选示例，不能仅凭本入口摘要判定 ready。

1. 开始准备前，读取 [队列与分诊](references/queue-and-triage.md) 和 [Ready 门禁](references/readiness.md)：冻结队列与审计基线，按完整门禁分诊和排序；默认最多 10 项，用户数量要求优先，先存量后周期新增。
2. 遇到准备缺口、主线阻塞或带有阻塞标记的存量候选时，先读取 [阻塞推进与复查](references/blockers.md)，持续完成可自主推进的调查与实验，不沿用旧阻塞结论跳过存量。
3. 首次更新 Issue、保存中间证据或切换任务前，读取 [交接与恢复](references/handoff.md)；最终输出前也须读取该文件，结合队列文件的复核要求确认交接完整。

每次读取都检查是否完整；工具输出若被截断，按行或段分批补读到文件末尾，不能将被截断的输出当作已读全文。引用文件缺失或不可读时，说明具体路径和影响，不依据不完整规则继续受影响的准备或入选判定。上下文压缩后，缺失当前阶段规则时重新读取对应文件。

## 目标与授权

把原 Issue 推进到下一位执行者只凭 Issue 就能开工的状态。发现候选、技术调查、最小实验、方案收敛和 Issue 整理属于同一准备流程；不要只跑一轮调查就把仍可自主完成的下一步交给用户。不要实施生产改动、创建实现分支或 Change Request，也不要生成或执行实现 prompt。

用户明确调用本技能且未限制范围时，默认包含必要调查和原 Issue 更新；用户要求只读、只讨论或限定写入位置时遵守该边界。隐式匹配技能或在讨论中提及名称不新增授权。依据实际远端选择连接器、CLI 或托管平台 API，不要求特定平台。读取、实验及写入遵守用户授权、实际所属仓库规范和环境权限。

Issue ready 门禁、任务粒度和准备交接以本技能为准，不采用目标仓库另行规定的同类工作流规则；语言、标题格式、Issue 模板结构、平台权限等项目约定仍按所属仓库执行。

## 最终输出契约

最终回复只能是一行有序 Issue 列表，项间使用英文逗号加空格；没有标题、解释、摘要、Markdown 链接、代码块、prompt 或手动换行。同一跟踪仓库且上下文明确时使用 `#123, #145, #167`。跨跟踪仓库时使用平台支持的完整限定标识；无法唯一定位平台或仓库时使用原 Issue 完整 URL，仍在同一行。实现跨仓本身不改变原 Issue 身份，所属仓库写在 Issue 内。

没有符合门禁的项输出 `[]`。此前须已完成可执行的准备行动，并在 Issue 或过程中交代真实阻塞、无权限、空队列或全部完成的事实；不能以 `[]` 代替尚可继续的准备。进度说明和必要问题放在工作过程中，最终不重复。准备完成不等于功能交付，不因 ready 就关闭 task。
