---
name: forge-steward-work-cycle
description: Review the existing open change requests, then run a bounded number of complete ForgeSteward work cycles with mandatory stage subagents through issue preparation, implementation, repair, and eligible merges. An optional positive integer sets the maximum cycles; the default is five. Use only for an explicitly requested end-to-end run.
---

# Work Cycle

## 规则加载

开始前完整读取 [启动与低频检查](references/startup.md)、[子 Agent 生命周期与恢复](references/agents.md) 和 [轮次、交接与终止](references/cycles.md)。这些文件是本技能必需规则，路径以本 `SKILL.md` 所在目录为基准。读取结果截断时分段补读到末尾；文件缺失或不可读时说明路径并停止受影响操作。上下文压缩后重新读取缺失的当前阶段规则。

各阶段子 Agent 必须从自己实际安装的技能目录完整读取对应 `SKILL.md` 及该入口要求的引用文件；本编排技能不复制或替代五个技能的业务规则。

## 输入与授权

用户明确调用本技能时，执行完整的准备、实施、审查、必要修复及符合门禁时的合并。唯一可选输入是一个正整数，表示最多运行多少个工作周期；省略时默认 **5**。不要求用户另选模式或逐阶段再次确认。没有有效轮数时请求一个正整数，不猜测。仅提到本技能、隐式匹配或询问用法，不构成执行及合并授权。

显式调用授予本次完整流程所需的 Issue 更新、实现分支、commit、push、Change Request、Review Feedback 和符合条件的合并权限；仍遵守实际托管平台权限、必要检查与审批、分支保护及所属仓库规范。不得绕过门禁，不能把提交、等待 CI 或修复推送说成已合并。用户明确停止时停止；本技能不增加其他调用参数或默认的人工确认点。

## 必须使用子 Agent

编排 Agent 只负责预检、低频检查判定、派发、等待、核对交接和最终汇总。每次实际调用 `check-workflow`、`prepare-work`、`execute-work`、`review-and-merge`、`fix-feedback`，**必须**创建负责该阶段的子 Agent，让该子 Agent 加载并执行对应技能；不能由编排 Agent 在自身上下文代做，也不能只让子 Agent 提供建议后由编排 Agent 代做。后续再审查同样创建新的审查子 Agent。阶段完成后等待其结果，保存简短、可追溯的交接，再启动依赖它的阶段；同一仓库的写入阶段不并行。

启动前确认运行环境提供创建和等待子 Agent 的能力，并确认五个阶段技能均可由子 Agent 读取，且与本插件使用相同的统一版本。确认能力或技能缺失时记录具体缺口并停止，不悄悄退化为单 Agent 执行。额度较低、接近限制的提醒不构成能力缺失；实际调用失败先按 [生命周期与恢复规则](references/agents.md) 核对状态并有限恢复，不因一次失败直接结束。不同 Agent 的子 Agent API 属于各自适配层，本技能不指定某个平台命令。子 Agent 只继承本次显式调用的范围和仓库授权，执行自身技能的完整门禁。

## 总体顺序

1. 按 [启动与低频检查](references/startup.md) 对目标仓库判定是否启动一次 `check-workflow` 子 Agent。普通提交、候选文件变化、Change Request 的创建或合并都不触发它。它不占工作周期。
2. 启动时先冻结并处理已有的开放 Change Request 队列，按 [轮次、交接与终止](references/cycles.md) 派发审查、必要修复和复审子 Agent；这一步不占工作周期，也不依赖 `prepare-work` 是否返回 Issue。没有开放项时跳过。
3. 最多运行指定周期数。每周期依次派发准备、执行、审查，存在范围内必修反馈时派发修复，再派发必要的复审。详细阶段交接、第三轮终审和停止条件见 [轮次、交接与终止](references/cycles.md)。
4. `prepare-work` 返回 `[]` 时立即停止新增周期，即使尚未达到上限；一个 Issue/Change Request 暂停不阻止同轮其他项及后续独立工作。最后按实际远端状态报告已合并、待审查、等待外部门禁及暂停项，不按轮数推定交付。
