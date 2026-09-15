# 发布规范

## 版本与交付物

ForgeSteward 通过 Git 仓库快照和 Agent 各自的 marketplace 分发，不是 npm、PyPI 或 NuGet 包注册中心。当前没有自动打 Tag、上传包或生成 Release 的流水线；已有 CI 只在 PR 和 main 推送时运行测试。本规范先采用维护者授权的手动发布，不把推送任意分支等同于发布。

| 标识 | 管理内容 | 事实来源 |
| --- | --- | --- |
| 仓库 Tag `vX.Y.Z` | 整个仓库，包括市场索引、全部插件、安装器和文档 | 已审查 main 提交上的附注 Tag |
| 统一版本 `X.Y.Z` | 所有插件的完整包内容及本次仓库发布 | 根目录 `VERSION`；全部插件的三份 `plugin.json` 版本必须与其一致 |
| GitHub Release | 版本对应表、实际提交 SHA、变更说明、验证和边界 | 同名 Tag 的发布页面 |

仓库与所有插件采用统一版本：`VERSION` 为 `X.Y.Z` 时，全部插件的包版本均为 `X.Y.Z`，发布 Tag 必须为 `vX.Y.Z`；候选版后缀也须完全一致。该规则在 `0.2.2` 开发基线引入，当前未发布目标以 `VERSION` 为准，历史发布记录不改写。仓库级安装器随仓库 Tag 固定，目前没有独立安装器包版本。独立安装不等于独立升版，用户仍可仅安装其中一个插件；本项目未提供任意混搭各插件历史版本的解析器。

## 升版规则

- 仓库发布使用 `vX.Y.Z`；候选版可用 `vX.Y.Z-rc.N`，GitHub 标为 prerelease。`0.x` 阶段仍属早期接口，不代表 1.0 稳定承诺；首个正式编号为 `v0.2.0`，不追补不存在的历史 Tag。
- 自动升版的允许范围以 [AGENTS.md 的统一版本规则](../AGENTS.md#统一版本) 为准：默认只递增最后一位，其他位或候选版渠道由用户明确指定；变化规模不构成自动跨位升版的授权。不兼容变化必须在版本说明中写清迁移，不以 patch 编号暗示兼容。
- 根据整次发布的变化确定一个版本，同步更新 `VERSION` 和全部插件清单；即使某个插件功能未变，或只有根目录 README、安装器变化，也必须统一升版。开发提交可以继续使用尚未发布的目标版本，不要求逐提交升版。Agent 修改时是否自动升版以 [AGENTS.md 的统一版本规则](../AGENTS.md#统一版本) 为准：仅当 `VERSION` 等于已发布版本（远端存在对应 Tag 及非 draft Release）时才递增，否则保持未发布的目标版本不变；用户明确要求不升版时从其要求。
- 插件的 `plugin.json`、`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 同步名称及版本。Claude / ZCode 共用市场的 `plugins[].version` 是 ZCode 更新检测所需的派生值，不是独立版本源；统一清单后执行 `python3 scripts/sync_marketplace.py --write`，发布前运行 `--check`。Codex 市场格式不变。所有引用仍指向同快照内的相对路径，不通过索引版本单独切换插件代码。
- 同一已发布插件版本不得对应不同包内容；后续仓库 Release 不重用旧插件版本，即使功能未变也更新版本字段。尤其 Claude 的显式版本影响缓存更新，不应靠移动 Tag 或只改市场版本来绕过缓存。参见 [Claude 版本规则](https://code.claude.com/docs/en/plugin-marketplaces#version-resolution-and-release-channels)。
- 已发布 Tag 不移动、不覆盖、不删除再重建；修复发布新版本。附注 Tag 默认不等于密码学签名；需要签名时另行配置，不能将本规范冒充服务端 Tag 保护规则。

## 发布步骤与门禁

1. 维护者确定版本及授权。在工作分支准备变更，新增 `docs/releases/<tag>.md` 的版本对应表、变更、迁移、验证边界，区分 README 的未发布目标与已发布推荐版本，发布确认后才更新固定安装推荐。历史表不随当前插件升版而改写。
2. 核对 `VERSION`、全部插件的三份 manifest、共用市场的派生版本及完整资源，全部包版本必须相同且等于 `VERSION`，执行 `python3 scripts/sync_marketplace.py --check`。人工核对目标 Tag 恰为 `v` 加 `VERSION`，本次 Release 对应表全部插件版本相同；同时对照上次发布记录确认使用新版本。CI 的元数据测试校验源码中的版本一致性，不代替远端 Tag 和 Release 对应表的发布核对。
3. 提交并审查 PR。执行 `python3 -m unittest discover -s tests -v`、`git diff --check`、相对文档链接和版本表核对；执行可用的 Agent 校验。PR 的三个 OS 安装器检查及固定 OpenCode 发现检查必须通过。若 Agent 包有变化，补充受影响 Agent 的安装验证；明确未做模型行为验证。
4. 通过仓库保护合并，禁止向 main 直接推送或绕过检查。记录审查 head、实际 main 合并提交和 CI 链接；等待该 main 提交的四个检查通过，若合并后源码不同则补验。
5. 使用只读查询核对目标 Tag/Release 不存在；已存在时核对目标而非覆盖。只对上一步确切的已验证提交创建附注 Tag，推送这一条 Tag，不执行批量 `--tags` 推送。发布命令应使用已解析的明确 SHA，不能在 main 后续移动后重新猜测目标。
6. 推送后回读远端 Tag：附注对象与其指向的 commit 是两个不同 SHA，需解引用到 commit 并与审查记录核对。使用 `gh release create <tag> --verify-tag` 关联已有 Tag，不让平台静默从最新 main 创建标签。
7. Release 正文使用中文，列出确切 commit SHA、对应表、安装链接、CI、兼容性和迁移。当前只发布 Git 快照及 GitHub 自动源码归档，不宣称提供独立构建包或全 Agent 端到端行为认证。
8. 复核远端 Tag、Release 的 tagName/draft/prerelease 状态及链接；在 PR 留存交接。仅清理本任务已合并且无独有工作的分支/临时目录，不触及用户安装。

以上 `<tag>` 是参数占位符，不是可直接执行的 shell 文本。维护者执行前须填入经过核对的值。

## 状态、失败与回退

- 仓库里的版本文档是发布输入，不代表已发布。以远端 Tag 和非 draft 的同名 GitHub Release 共同确认完成。Release 正文记录完整提交 SHA；同一提交内的文档不写自身提交 SHA，避免循环依赖。
- Tag 已推送而 Release 创建失败：保留 Tag，核对目标后重试同一个 Release，不重新打 Tag。返回结果不确定时先查询，避免重复创建。
- 发现发布内容有问题：标明已知问题、建议用户回退，另开修复 PR 并发新版本；不要删除已有版本掩盖问题。版本说明更正须注明勘误，不能改变 Tag 的源码身份。
- 用户回退安装见 [固定版本安装](versioned-installation.md)。回退技能不自动撤销其已产生的代码、项目规则或托管平台操作。

## 当前发布输入

- [v0.2.10 对应表与说明](releases/v0.2.10.md)（是否发布以远端 Tag 和非 draft Release 为准）

## 发布记录

- [v0.2.9 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.9)；[对应表与说明](releases/v0.2.9.md)
- [v0.2.8 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.8)；[对应表与说明](releases/v0.2.8.md)
- [v0.2.7 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.7)；[对应表与说明](releases/v0.2.7.md)
- [v0.2.6 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.6)；[对应表与说明](releases/v0.2.6.md)
- [v0.2.5 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.5)；[对应表与说明](releases/v0.2.5.md)
- [v0.2.4 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.4)；[对应表与说明](releases/v0.2.4.md)
- [v0.2.3 GitHub Release](https://github.com/philfanzhou/ForgeSteward/releases/tag/v0.2.3)；[原准备文档](releases/v0.2.3.md)保留当时状态及历史对应表，实际发布记录以 Release 为准。
- [v0.2.1 对应表与说明](releases/v0.2.1.md)
- [v0.2.0 对应表与说明](releases/v0.2.0.md)
