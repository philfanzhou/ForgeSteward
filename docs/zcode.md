# ZCode 支持、安装维护与验证

## 状态与方案

当前支持作为 `0.2.3` 未发布目标的一部分交付。保留五个独立插件和每项唯一的技能正文，不增设 `.zcode-plugin`、第二个市场、安装器或另一份工作流。ZCode 直接使用现有 `.claude-plugin/plugin.json` 与 `.claude-plugin/marketplace.json`；所有 `source` 仍指向同一快照的 `./plugins/<插件名>`。旧 Tag 不补写这些变化。

2026-09-13 核对的官方公开最新版为 ZCode 桌面 `3.11.2`，本机已是该版本，无需覆盖安装；其内置 CLI 独立编号为 `0.16.5`。应用更新和 ForgeSteward 技能更新是两件事，不通过改本仓库版本来更新 ZCode。

本次桌面自动化未能稳定进入设置页，未修改用户插件、账号或安全设置。此支持的已验证范围是格式契约和内置 CLI 的实际插件发现/读取，不是桌面市场安装、更新、卸载或模型行为认证。其他 ZCode 版本须复核，不能外推为全版本保证。

## 安装与调用

1. 打开要维护的工作区，在设置的插件页添加市场。官方页面称入口为“创建 → 添加插件市场”；部分客户端使用“发现 → +”。
2. 开发验证优先选择包含本说明的、已审查源码 checkout 的绝对根目录。不要选择 `.claude-plugin` 子目录，否则相对插件来源的基准可能不对。GitHub 来源 `philfanzhou/ForgeSteward` 用于跟随远端默认分支，不代表固定发布，也不会取得未合并的 PR 内容。
3. 在 `forge-steward` 市场中按需安装 `check-workflow`、`prepare-work`、`execute-work`、`review-and-merge`、`fix-feedback`，检查启用状态、版本及实际来源。
4. 在技能设置及新任务选择器确认名称。输入 `$` 选择技能，`/` 菜单也提供技能分组；若显示 `插件名:技能名` 则选择实际限定项。统一标识仍包含 `forge-steward-`，不承诺解析 Codex 的 `agents/openai.yaml` 显示标签。

选择技能无需再粘贴完整 prompt，但所选操作需要的输入和授权仍须具备。例如 prepare 可以按默认范围运行，execute 需要明确 Issue 列表，review-and-merge 需要有效的审查合并授权；“仅检查”“不推送”等明确限制优先，选择器本身不绕过仓库权限。CLI/连接器的托管平台认证、Git、项目测试环境由使用方提供，安装 Skill 不自动授予这些能力。

## 固定版本与回退

官方支持本地市场来源；本项目采用“已校验 Git 快照 + 本地市场”表达固定版本，避免臆造 ZCode 的 `--ref`、`repo@tag` 或 `#tag` 输入规则。下面是版本选择步骤，不是声称桌面完整切换已经实测。

1. 从远端 Release 选择已发布 Tag，核对非 draft、对应版本表与提交 SHA。当前 `v0.2.3` 尚未发布，不直接拿它执行 clone。
2. 为该版本创建独立、干净的源码 checkout，不在有用户工作的目录执行切换。下面变量必须替换为已核对的值；路径必须是尚不存在的新目录：

   ```bash
   forge_tag='REPLACE_WITH_PUBLISHED_TAG'
   forge_snapshot='/absolute/path/ForgeSteward-selected-release'
   git clone --branch "$forge_tag" --single-branch https://github.com/philfanzhou/ForgeSteward.git "$forge_snapshot"
   git -C "$forge_snapshot" checkout --detach "$forge_tag"
   git -C "$forge_snapshot" rev-parse HEAD
   ```

   macOS/Linux 使用上述 shell 写法；Windows PowerShell 使用 `$forge_tag = '...'`、`$forge_snapshot = 'C:\...'`，后面的 Git 参数不变。`rev-parse` 结果必须与 Release SHA 一致。审查开发源码时可用具体 commit，但明确标为未发布验证源。
3. 记录现有市场、安装子集、包版本、作用域和来源路径。保留定制及旧 checkout，停止活动任务。
4. 先卸载旧市场的已安装插件，再移除该市场来源；添加选定快照的**根目录**，重新安装原子集及明确需要的新插件。市场名称仍是 `forge-steward`，不要并行注册多个同名来源或直接改缓存冒充安装。
5. 核对实际安装内容和包版本，而不是只看市场版本。新会话中确认每个技能的实际路径与来源；更新或回退到不同名称集合时，按该版本表卸载退役名称并安装目标名称。若任何一步失败，保留已完成步骤记录，使用旧快照和原子集恢复。

固定快照不跟随新 Tag，市场刷新也不能选择新版本。支持之前的历史 Tag 可能结构兼容，但没有本轮版本索引与验证，尤其不能靠其更新提示判定是否存在新版。回退不撤销技能已产生的代码、Issue、PR、评论或项目约束。

## 更新检测与发布约束

ZCode 从市场条目的 `version` 判断可更新版本，插件自身的 `plugin.json` 表示安装包版本。因此共用市场必须包含派生版本，但不能成为独立版本源：

```bash
python3 scripts/sync_marketplace.py --write
python3 scripts/sync_marketplace.py --check
```

脚本先校验市场和当前插件目录一一对应、来源为同快照相对路径、三份 manifest 名称与统一版本一致，然后只同步市场 `version`；不改插件包、不抓取网络、不写用户配置。其他字段和顺序保留。版本不一致、缺项、重复或外部来源时报错，不靠改市场掩盖包版本问题。CI 在三种 OS 上运行检查；Codex 市场不添加 ZCode 字段。

跟随开发分支时，在客户端先刷新市场，再检查插件更新并更新已安装子集。未发布同版本内的代码变化可能没有更新提示，应重新安装并核对内容，不能为了提示而每次升版。发布仍须统一版本、不可移动旧 Tag，并按 [发布规范](releasing.md) 单独授权；本次 PR 不发布。

## 卸载与只保留目标版本

停用、卸载、移除市场来源和磁盘清理是不同动作。先备份定制并停止技能任务，通过插件详情卸载 ForgeSteward 的实际安装子集，再按需移除市场来源。新名不会自动替代旧名，历史 `find-work` 也要核对。

手动导入的技能独立于插件安装：Copy 不跟随后续源变化；Symlink 依赖源目录存活。不把其他 Agent 的版本缓存当作长期软链接源，避免升级清理后断链。检查用户与工作区的 `.zcode/skills`、`.agents/skills`、配置的其他根目录，以及远端环境；选择器的一条记录可能遮蔽同名副本。核对实际路径，不只数菜单条目。

确认归属及未被引用后，将冗余副本或链接移到所有发现路径之外保存；不要沿软链接删除另一 Agent 的来源。受管插件优先通过其管理器移除，缓存仅处理已确认不再引用的 ForgeSteward 路径。保留本地市场依赖的 checkout，不删除整个 `.zcode`、共享 plugins/cache 或其他 Agent 配置。卸载后新任务不再发现相应技能是运行层目标，立即零磁盘残留不在本轮保证内。SSH/WSL 的同步副本需在对应主机单独核验。

## 项目规则适配

ZCode 原生读取全局 `~/.zcode/AGENTS.md` 和当前 Workspace 的 `AGENTS.md`；不自动合并多层规则，也不展开 `@import` / `@include`。`CLAUDE.md` 不是持续加载入口。check-workflow 只在允许修改的项目入口增加明确的读取指示，保留原权威规则和跨 Agent 的回退关系，不迁移 CLAUDE 正文，不写全局规则，不宣称相对链接等于自动加载。具体约束见包内 [Agent 入口适配](../plugins/check-workflow/skills/forge-steward-check-workflow/references/agent-entrypoints.md)。

## 验证记录与复验

| 验证层级 | 本轮结果 / 边界 |
| --- | --- |
| 官方版本与安装包静态核对 | 桌面 3.11.2；安装包中的 `findMarketplaceManifestPath` 接受根 `marketplace.json` 或 `.claude-plugin/marketplace.json`；未覆盖安装 |
| 仓库契约 | `tests/test_zcode_packaging.py` 校验市场派生版本、平铺技能、元数据长度、正文大小、相对引用及同步拒绝路径；不是通用 ZCode schema 验证器 |
| 实际 CLI 发现 | 内置 CLI 0.16.5 在临时工作区加载重定位的五个插件，逐项 inspect 验证可读且不截断；关闭临时插件配置后不再从该路径发现 |
| 桌面市场生命周期 | 未完成 GUI 添加市场、安装、更新、回退、卸载实测；CLI 内联插件发现不能代替这些操作 |
| 模型行为 | 未调用模型，无真实业务 Issue/PR 写入，不宣称“仅选技能即可靠完成”或合并行为已通过 |

运行静态及回归测试：`python3 -m unittest discover -s tests -v`。可选实际 CLI 检查（需已安装官方应用与 Node.js；不用模型密钥、不改 HOME 或用户配置）：

```bash
FORGESTEWARD_ZCODE_CLI=/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs \
  python3 -m unittest discover -s tests -p test_zcode_packaging.py -v
```

未设置变量时真实运行测试明确 skip；CI 不下载或静默安装 ZCode，默认只证明静态契约。测试可读取当前环境的发现来源，但只断言临时项目的技能，不输出其他技能清单，也不执行模型任务。实际桌面流程后续在隔离工作区复验：添加审查过的市场 → 安装五项 → 检查限定名称/完整引用 → 切换已核对的版本 → 卸载 → 新任务确认无重复。模型验收另测只读/无发布限制、execute 必需清单、review 合并门禁，不借测试操作真实生产 PR。

## 依据

- [ZCode 安装](https://zcode.z.ai/cn/docs/install)：公开版本与支持平台。
- [ZCode Plugin](https://zcode.z.ai/cn/docs/plugin)：兼容清单、自建市场、更新检测与启停卸载。
- [ZCode Skill](https://zcode.z.ai/en/docs/skill)：格式限制、调用、导入及同步。
- [ZCode Agent](https://zcode.z.ai/cn/docs/agents)：AGENTS 指令来源和加载边界。

官方文档与客户端版本出现差异时，以已验证版本行为为准并记录差额；本轮未使用非官方同名 ZCode 项目作为规范依据。
