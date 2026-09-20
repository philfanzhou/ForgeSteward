---
name: forge-steward-fix-feedback
description: Freeze the current repairable change-request queue, resolve only required review feedback, deterministic in-scope CI failures, and confirmed acceptance gaps, then commit and push each original branch without merging. Use for repairing PRs or MRs that need changes, not for items merely awaiting re-review.
---

# Fix Feedback

## 规则加载

对冻结待修清单中的候选进入修复、验证或推送阶段前，完整读取 [逐项修复规则](references/repair.md)。只读分类和跳过项按本入口处理；不得仅凭入口摘要改代码、推送或解决 Review Thread。

引用文件是本技能的必需规则，路径以本 `SKILL.md` 所在目录为基准，不以目标仓库或当前工作目录为基准。工具输出被截断时按行或段补读至文件末尾；文件缺失或不可读时说明具体路径和影响，不依据不完整规则继续受影响的操作。上下文压缩后，缺失当前阶段规则时重新读取对应文件。

## 授权与边界

修复当前开放 Change Request 中确实需要修改的项目。Change Request 是平台无关术语，包括 GitHub Pull Request、GitLab Merge Request 等等价对象。

修复范围、意见分类和 Review 轮次以本技能为准，不采用仓库另行规定的同类工作流规则；语言、提交格式、验证命令和分支保护等项目约定仍按仓库执行。

只有用户已授权修改代码并推送原分支且授权在当前任务中仍有效时才执行这些外部写入，不因切换会话要求重复授权。此 Skill 在任何情况下都不得合并 Change Request，也不得把“已推送”表述为“已验收完成”或“已合并交付”。使用当前环境可用的连接器、CLI 或平台 API，不要求特定托管平台。

## 冻结待修清单

1. 读取仓库规范、既定主线和上轮交接，获取当前开放 Change Request、Review、检查结果和关联任务。沿用清理周期期初 task 清单及未完成范围，不以修复提交重置目标或增加交付计数。
2. 冻结本轮待修清单，记录时间、base、head 提交和入选原因。后续新出现的 Change Request 不自动加入。
3. 只纳入至少存在一项必修内容的 Change Request：
   - 尚未解决且落在原范围内的明确 Review 意见；
   - 由当前分支确定性导致、可复现且属于本次范围的 CI 失败；
   - 已确认未满足的原始验收条件。
4. 跳过仅等待复审、等待已触发检查、只含可选建议、意见已经由当前 head 解决，或没有确定性修复项的 Change Request。说明跳过依据。
5. 跳过多轮往返项。一轮往返指：该 Change Request 上出现要求修改的 Review Feedback（包括请求修改的审查、Comment、Discussion 或 Review Thread），作者随后推送新提交作出回应。依据平台时间线及交接记录中的 Review 轮次计数，二者不一致时取较大值，不因换会话归零。已达到 3 轮或以上的项说明原始范围本身存在问题，即使仍有必修内容也不纳入本轮，等待人工处理：不修改，不推送，不回复或解决 Review Thread，不添加标签。只在输出中记录链接、轮次及计数依据。无法确定轮次时按正常流程判断，并标明轮次未知。用户本轮明确点名要求处理该项时除外。

## 交接记录

沿用已有 tracker、任务或仓库指定记录位置，保留一份当前状态；仅在授权范围内写入，没有可写位置时在输出中提供可直接交接的完整记录，不自行创建 tracker。字段按实际填写：清理周期基线与主线；task/Change Request 完整链接、实现仓库及主线；审计基线、覆盖范围与证据位置；当前 head、逐条验收证据；意见分类、Review 轮次、已解决意见与已接受边界；阻塞、下一步及解除条件。缺失项标明未知或不适用，不推定验收通过或将轮次归零。另记录提交、推送结果及可复审状态，不把已推送计作 task 完成；新增、返工和原清理目标的剩余范围分开，拆分或迁移不算交付，未知计数不推测。

## 完成条件

一个 Change Request 在以下情况下结束本轮处理：

- 所有已确认必修项已经修复并得到必要验证，提交已成功推送；或
- 存在无法继续的具体阻塞，已经记录事实、尝试过的解决方式和可执行下一步；或
- 复核后确认没有待修项，已经说明无需修改的依据。

不要因为一个分支推送完成而停止整个批次。继续处理冻结清单，直到每项都达到上述一种状态。

## 输出

处理完整个冻结清单后，用中文汇总：

- 冻结基线、实际待修项和跳过项。
- 因往返达到 3 轮或以上而跳过、等待人工处理的 Change Request，附轮次及计数依据。
- 每个 Change Request 的必修条目、修改、验证、提交和推送链接或标识。
- 已可复审但尚未验收的 Change Request。
- 未解决阻塞、并发变化、权限问题和下一步。
- 新发现问题的去重与分诊结果。

明确区分“已修改并推送”“等待复审”“验收成立”和“已合并”；本 Skill 不得产生最后一种状态。
