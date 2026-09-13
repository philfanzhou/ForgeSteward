# 准备与执行技能迁移

## 当前状态

当前目标为 `0.2.3`，尚未发布。本次将 `find-work` 改为 `prepare-work`，把原执行 prompt 收为独立 `execute-work`；两个技能不互相依赖安装，也不自动调用对方。全部五个插件的三份 manifest 与根目录 `VERSION` 一致。版本自动调整遵守 [AGENTS.md](../AGENTS.md#统一版本)，改名的不兼容性仍通过本说明披露。

| 旧标识 | 当前标识 | 使用变化 |
| --- | --- | --- |
| `find-work@forge-steward` | `prepare-work@forge-steward` | 持续调查、实验和方案收敛，直到可实施或真实外部阻塞；不实施生产代码 |
| `forge-steward-find-work` | `forge-steward-prepare-work` | 原 Issue 持久化完整交接；最终只输出一行编号，不输出执行 prompt |
| 手动复制长执行 prompt | `execute-work@forge-steward` / `forge-steward-execute-work` | 直接接收编号列表，逐项实现、验收并提交独立 PR/MR；不合并 |

其余三个插件保留名称。未提供旧名 alias，避免同时加载两份不同准备流程。旧版本中的 prompt 行为仍属于旧版本，不改写历史 Tag 或 Release。

## 使用交接

明确调用 prepare-work 后，其过程更新可报告调查进度和外部问题；最终响应只能是 `#123, #145, #167` 这样的一行，无手动换行。没有符合门禁的项为 `[]`。同号跨仓须用平台可识别的限定标识，不能唯一定位时用完整 Issue URL；仍保持同一行。跨仓实现归属写在原 Issue 中，不复制任务。

将该列表原样附在 execute-work 调用后。执行者自己读取 Issue 和实际仓库规则，复用仍有效的审计并补查相关变化；中途某项真正受阻时保留证据，继续其他独立项，不在首个 PR 后停止，不叠加未合并代码。

只读准备不发布 Issue 更新；必要交接缺失时该项不入选，过程中交代缺口。显式本地实施不发布 PR。只有讨论名称或隐式技能匹配时，仍以实际用户请求判断授权。

## 安装迁移

以下操作供选择新版的维护者使用；本次源码 PR 不执行用户安装或发布。正式使用等待确认发布的目标 Tag；提前验证开发源码时使用独立 checkout 和审查过的具体 commit，不把 `v0.2.3` 当作已存在 Tag。仓库根目录安装示例仍固定在已发布 `v0.2.1`，不能只替换插件名就取得新技能。

先记录当前来源、已安装子集与作用域，保留本地定制，停止旧技能的活动任务。Codex/Claude 通过各自插件管理器移除旧 `find-work@forge-steward`，再按 [版本切换指南](versioned-installation.md) 将 marketplace 指向选定新版快照。安装 `prepare-work@forge-steward`，需要执行能力时再装 `execute-work@forge-steward`；其余已选插件同步该快照版本。只替换市场目录不证明已安装副本升级。

开发验证也可将市场指向独立本地 checkout；用 Agent 支持的本地路径市场入口，不直接修改缓存或真实用户配置来冒充安装验证。安装成功后检查实际包版本、来源和新会话选择器，保存的快捷调用更新到新名称。Codex 使用 `$forge-steward-prepare-work`、`$forge-steward-execute-work`；Claude 使用 `/prepare-work:forge-steward-prepare-work`、`/execute-work:forge-steward-execute-work`。

OpenCode 从已选择的新版 checkout 调用以下命令；把 `/path/to/ForgeSteward` 替换为实际路径，从目标项目执行：

```bash
python3 /path/to/ForgeSteward/scripts/opencode.py uninstall find-work --project .
python3 /path/to/ForgeSteward/scripts/opencode.py install prepare-work execute-work --project .
python3 /path/to/ForgeSteward/scripts/opencode.py status prepare-work execute-work --project .
opencode debug skill
```

按顺序检查每步结果。用户级安装改为 `--user`，保留原 XDG/自定义配置选择。需要同步其余三个已有插件时按名称 `update`；`update --all` 不会安装缺失的新技能，也不会将旧名自动改为新名。`install --all` 只安装当前 catalog，不清除已退役名称，因此不能代替旧名卸载。

安装器不需要旧源码也能卸载有有效收据且未修改的旧技能。旧副本被定制、缺失收据或来自手动复制时会保留并报告；备份、确认归属并移出搜索路径后再继续，不绕过保护。其他 Agent 兼容路径中的旧副本也须单独核对，不能因新名已出现就认为旧流程已消失。回退选择历史快照并恢复历史名称，不回滚技能已产生的 Issue 或代码。

ZCode 的开发支持复用 Claude 兼容市场。若此前手动导入或安装过旧 `find-work`，按 [ZCode 维护流程](zcode.md) 卸载该旧插件、核对导入副本并切换市场快照，然后选择 `prepare-work` 和按需选择 `execute-work`；不直接复制 Codex/Claude 的命令。新任务使用 `$` 选择实际技能项，执行技能仍需附加明确清单。

## 验证边界

安装器回归覆盖当前五项安装、退役名称安全卸载、旧内容受保护及新增名称安装；格式和市场元数据校验不等于真实模型遵守行为。有限规则走查见 [场景验收](prepare-execute-scenarios.md)，实际执行的校验及安装结果记录在 PR。
