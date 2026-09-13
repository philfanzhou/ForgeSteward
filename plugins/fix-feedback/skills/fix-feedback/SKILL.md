---
name: fix-feedback
description: Freeze the current repairable change-request queue, resolve only required review feedback, deterministic in-scope CI failures, and confirmed acceptance gaps, then commit and push each original branch without merging. Use for repairing PRs or MRs that need changes, not for items merely awaiting re-review.
---

# Fix Feedback

## 授权与边界

修复当前开放 Change Request 中确实需要修改的项目。Change Request 是平台无关术语，包括 GitHub Pull Request、GitLab Merge Request 等等价对象。

只有用户当前请求授权修改代码并推送原分支时才执行这些外部写入。此 Skill 在任何情况下都不得合并 Change Request，也不得把“已推送”表述为“已验收完成”或“已合并交付”。使用当前环境可用的连接器、CLI 或平台 API，不要求特定托管平台。

## 冻结待修清单

1. 读取仓库规范并获取当前开放 Change Request、Review、检查结果和关联任务。
2. 冻结本轮待修清单，记录时间、base、head 提交和入选原因。后续新出现的 Change Request 不自动加入。
3. 只纳入至少存在一项必修内容的 Change Request：
   - 尚未解决且落在原范围内的明确 Review 意见；
   - 由当前分支确定性导致、可复现且属于本次范围的 CI 失败；
   - 已确认未满足的原始验收条件。
4. 跳过仅等待复审、等待已触发检查、只含可选建议、意见已经由当前 head 解决，或没有确定性修复项的 Change Request。说明跳过依据。

## 逐项修复

对每个入选项：

1. 读取关联 Issue、原始范围、逐条验收、保证与非保证、历史意见、已接受边界和既有 Review 轮次。
2. 为每个必修条目记录来源、适用代码、为何属于范围和可验证的完成条件。合并重复意见，忽略被后续决定取代的意见。
3. 意见与原范围、仓库规范或已接受边界冲突时，先依据更高优先级规则判断。不能通过盲目扩张实现来满足矛盾或非保证要求；必要时回复理由并保留为未解决阻塞。
4. 在原 Change Request 的源分支上完成满足必修项的最小修改。每个 Change Request 使用独立分支或隔离 worktree，不叠加其他未合并 Change Request 的代码，也不顺手寻找新的改进点。
5. 运行覆盖修改和原验收缺口的必要验证。确定性 CI 失败应先本地复现或获得等价证据；无法运行时写明限制和剩余验证，不能宣称通过。
6. 必修项闭环后提交并推送原源分支。提交应只包含该 Change Request 的修复；推送前确认远端 head 没有出现未纳入的并发提交。无推送权限、源自不可写 fork 或发生并发冲突时停止写入并记录恢复步骤，不改推到新的替代 Change Request。
7. 只有实际修复且平台权限允许时才回复或解决对应 Review Thread。保留仍需复审的状态，不把等待复审当作新的修复任务。

新发现的问题先检索去重并按仓库规范登记或提出分诊建议。严重风险应及时处理或升级；其他新发现不得自动扩充冻结清单。完成当前项后保存提交、推送结果、修复证据、Review 轮次、已接受边界、未解决项和下一步，再安全清理由本轮创建且无未提交改动的环境，继续下一项。

## 完成条件

一个 Change Request 在以下情况下结束本轮处理：

- 所有已确认必修项已经修复并得到必要验证，提交已成功推送；或
- 存在无法继续的具体阻塞，已经记录事实、尝试过的解决方式和可执行下一步；或
- 复核后确认没有待修项，已经说明无需修改的依据。

不要因为一个分支推送完成而停止整个批次。继续处理冻结清单，直到每项都达到上述一种状态。

## 输出

处理完整个冻结清单后，用中文汇总：

- 冻结基线、实际待修项和跳过项。
- 每个 Change Request 的必修条目、修改、验证、提交和推送链接或标识。
- 已可复审但尚未验收的 Change Request。
- 未解决阻塞、并发变化、权限问题和下一步。
- 新发现问题的去重与分诊结果。

明确区分“已修改并推送”“等待复审”“验收成立”和“已合并”；本 Skill 不得产生最后一种状态。
