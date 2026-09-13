# 发布规范

## 版本与交付物

ForgeSteward 通过 Git 仓库快照和 Agent 各自的 marketplace 分发，不是 npm、PyPI 或 NuGet 包注册中心。当前没有自动打 Tag、上传包或生成 Release 的流水线；已有 CI 只在 PR 和 main 推送时运行测试。本规范先采用维护者授权的手动发布，不把推送任意分支等同于发布。

| 标识 | 管理内容 | 事实来源 |
| --- | --- | --- |
| 仓库 Tag `vX.Y.Z` | 整个仓库，包括市场索引、四个插件、安装器和文档 | 已审查 main 提交上的附注 Tag |
| 单插件版本 `X.Y.Z` | 一个插件的完整包内容 | 该插件的三份 `plugin.json`，名称和版本必须一致 |
| GitHub Release | 版本对应表、实际提交 SHA、变更说明、验证和边界 | 同名 Tag 的发布页面 |

仓库 Tag 与各插件版本分别管理；数值相同只是首版的选择，不建立永远同号的约束。仓库级安装器随仓库 Tag 固定，目前没有独立安装器包版本。一个 Tag 固定整个市场快照，用户仍可仅安装其中一个插件；本项目未提供任意混搭各插件历史版本的解析器。

## 升版规则

- 仓库发布使用 `vX.Y.Z`；候选版可用 `vX.Y.Z-rc.N`，GitHub 标为 prerelease。`0.x` 阶段仍属早期接口，不代表 1.0 稳定承诺；首个正式编号为 `v0.2.0`，不追补不存在的历史 Tag。
- 兼容性修复、文档和安装器小修复提升仓库 patch；新增能力或 `0.x` 阶段不兼容变化提升 minor，并明确迁移。进入 `1.x` 后不兼容变化提升 major。
- 只有包内内容变化的插件才升版；包括技能正文、参考资源、manifest 和包内默认提示。兼容修复升 patch，新增能力升 minor；`0.x` 的不兼容变化升 minor 并明确迁移。不要为根目录 README 或安装器变化统一提升所有插件。
- 插件的 `plugin.json`、`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 同步名称及版本。市场引用路径须存在；不在市场重复维护同一插件版本字段。
- 同一插件版本不得对应不同包内容；未变化的插件可以跨多个仓库 Release 重用版本。尤其 Claude 的显式版本影响缓存更新，不应靠移动 Tag 或只改市场版本来绕过缓存。参见 [Claude 版本规则](https://code.claude.com/docs/en/plugin-marketplaces#version-resolution-and-release-channels)。
- 已发布 Tag 不移动、不覆盖、不删除再重建；修复发布新版本。附注 Tag 默认不等于密码学签名；需要签名时另行配置，不能将本规范冒充服务端 Tag 保护规则。

## 发布步骤与门禁

1. 维护者确定版本及授权。在工作分支准备变更，新增 `docs/releases/<tag>.md` 的版本对应表、变更、迁移、验证边界，更新 README 的推荐版本。历史表不随当前插件升版而改写。
2. 核对全部插件的三份 manifest、市场清单及完整资源。对照上次已发布 Tag 的包内容：变化必须升插件版本，不变不能仅为仓库发布强行同步升版。首次发布以对应表为基线。
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

## 发布记录

- [v0.2.1 对应表与说明](releases/v0.2.1.md)
- [v0.2.0 对应表与说明](releases/v0.2.0.md)
