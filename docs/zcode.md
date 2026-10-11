# ZCode 支持、安装维护与验证

## 状态与方案

ZCode 支持从 `v0.2.3` 起交付。当前版本包含六个独立插件和每项唯一的技能正文，不增设 `.zcode-plugin`、第二个市场、安装器或另一份工作流。ZCode 直接使用现有 `.claude-plugin/plugin.json` 与 `.claude-plugin/marketplace.json`；所有 `source` 仍指向同一快照的 `./plugins/<插件名>`。旧 Tag 不补写这些变化。

2026-10-11 本机 ZCode 桌面为 `3.14.5`，内置 CLI 独立编号为 `0.16.9`（2026-09-27 核对技能发现时桌面为 `3.14.3`，CLI 编号相同）。应用更新和 ForgeSteward 技能更新是两件事，不通过改本仓库版本来更新 ZCode。

市场来源使用 GitHub 地址加版本号 `philfanzhou/ForgeSteward@vX.Y.Z`，不再依赖本地目录。已验证范围是内置 CLI 的市场添加、安装、换版本、卸载和移除市场，以及技能发现/读取；桌面界面的同类操作和模型行为未实测，不能外推为全版本保证。

## 安装与调用

当前版本的安装、升级、卸载命令以 [README 的 ZCode 一节](../README.md#zcode) 为准；命令由 work-cycle 技能包内的 `scripts/agents.json` 统一维护，测试保证 README 与它及 `VERSION` 一致。下面说明这些命令的依据和边界。

1. 内置 CLI 位于应用包内，macOS 默认是 `/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs`，用 Node.js 运行：`node "$ZCODE_CLI" plugins ...`。它与桌面界面共用 `~/.zcode/cli/plugins`，所以用 CLI 装好的插件桌面端也能看到；重启 ZCode 后生效。
2. `plugins marketplace add philfanzhou/ForgeSteward@vX.Y.Z` 添加名为 `forge-steward` 的市场，来源记录为 `{"source":"github","repo":"philfanzhou/ForgeSteward","ref":"vX.Y.Z"}`。不带 `@ref` 时跟随远端默认分支，不代表固定发布，也不会取得未合并的 PR 内容。
3. 逐个执行 `plugins install <插件>@forge-steward` 安装 `check-workflow`、`prepare-work`、`execute-work`、`review-and-merge`、`fix-feedback`、`work-cycle`。完整工作周期需要六项同版本插件。
4. 桌面界面“设置 → 插件 → 添加插件市场”（部分客户端为“发现 → +”）写入同一插件目录，在其中输入同样的 `philfanzhou/ForgeSteward@vX.Y.Z` 应当等效，但界面操作本身未实测。
5. 在技能设置及新任务选择器确认名称。输入 `$` 选择技能，`/` 菜单也提供技能分组；若显示 `插件名:技能名` 则选择实际限定项。统一标识仍包含 `forge-steward-`，不承诺解析 Codex 的 `agents/openai.yaml` 显示标签。

选择技能无需再粘贴完整 prompt，但所选操作需要的输入和授权仍须具备。例如 prepare 可以按默认范围运行，execute 需要明确 Issue 列表，明确选择 review-and-merge 即授权审查后直接合并满足条件的项，不再逐项确认；“仅检查”“不推送”等明确限制优先，选择器本身不绕过仓库权限。CLI/连接器的托管平台认证、Git、项目测试环境由使用方提供，安装 Skill 不自动授予这些能力。

## 固定版本与回退

版本由市场来源里的 Tag 决定：`@v0.2.21` 装到的就是 `0.2.21`，改成 `@v0.2.20` 装到的就是 `0.2.20`；`plugins marketplace update` 刷新后来源仍是原 Tag，不会自动跟随新版本。升级和回退使用同一套步骤，只是选择不同的已发布 Tag：

1. 从远端 Release 选择已发布 Tag，核对非 draft 及对应版本表。尚未发布的源码目标不可直接当作已发布 Tag 使用。
2. 记录现有市场来源、安装子集、包版本；保留定制并停止活动任务。
3. 逐个执行 `plugins uninstall <插件>@forge-steward --force --keep-data`。非交互终端里不加 `--force` 会拒绝卸载，`--force` 只是跳过“确认卸载”的提示；`--keep-data` 保留插件数据目录。没装过的插件报错可以忽略；旧版遗留的 `find-work` 也一并卸载。
4. 执行 `plugins marketplace remove forge-steward`。只移除市场不会卸载已装插件，所以必须先做第 3 步。
5. 执行 `plugins marketplace add philfanzhou/ForgeSteward@<所选 Tag>`，再逐个 `plugins install`。
6. 用 `plugins list --json` 核对每项 `version`，新任务中确认技能来源。任何一步失败时，按同样步骤装回记录中的旧 Tag。

`plugins update <插件>@forge-steward` 会把已装插件换成市场当前指向的版本，包括降级；但新版本新增的插件仍需 `install`，因此本文和 README 采用“卸载 → 换市场 → 重装”的写法。市场名称仍是 `forge-steward`，不要并行注册多个同名来源或直接改缓存冒充安装。

早期说明曾用本地源码目录作市场来源。这种来源依赖该目录一直存在，目录被删除后已装技能靠缓存暂时可用，但之后刷新或更新会失败。按上面的步骤换成 GitHub 来源后，旧目录不再被引用。确需审查未发布提交时仍可临时添加本地 checkout 的**根目录**（不是 `.claude-plugin` 子目录），使用期间不能删除该目录；`owner/repo@<完整提交 SHA>` 的写法未经验证。

回退不撤销技能已产生的代码、Issue、PR、评论或项目约束。

## 更新检测与发布约束

ZCode 从市场条目的 `version` 判断可更新版本，插件自身的 `plugin.json` 表示安装包版本。因此共用市场必须包含派生版本，但不能成为独立版本源：

```bash
python3 scripts/sync_marketplace.py --write
python3 scripts/sync_marketplace.py --check
```

脚本先校验市场和当前插件目录一一对应、来源为同快照相对路径、三份 manifest 名称与统一版本一致，然后只同步市场 `version`；不改插件包、不抓取网络、不写用户配置。其他字段和顺序保留。版本不一致、缺项、重复或外部来源时报错，不靠改市场掩盖包版本问题。CI 在三种 OS 上运行检查；Codex 市场不添加 ZCode 字段。

市场来源不带 `@ref`、跟随开发分支时，在客户端先刷新市场，再检查插件更新并更新已安装子集。未发布同版本内的代码变化可能没有更新提示，应重新安装并核对内容，不能为了提示而每次升版。发布仍须统一版本、不可移动旧 Tag，并按 [发布规范](releasing.md) 执行。

## 卸载与只保留目标版本

停用、卸载、移除市场来源和磁盘清理是不同动作。先备份定制并停止技能任务，卸载 ForgeSteward 的实际安装子集，再按需移除市场来源。命令行做法见 [README 的 ZCode 卸载](../README.md#zcode)：逐个 `plugins uninstall <插件>@forge-steward --force`，再 `plugins marketplace remove forge-steward`；不加 `--keep-data` 时插件数据目录一并删除。桌面端可在插件详情中卸载。新名不会自动替代旧名，历史 `find-work` 也要核对。

手动导入的技能独立于插件安装：Copy 不跟随后续源变化；Symlink 依赖源目录存活。不把其他 Agent 的版本缓存当作长期软链接源，避免升级清理后断链。检查用户与工作区的 `.zcode/skills`、`.agents/skills`、配置的其他根目录，以及远端环境；选择器的一条记录可能遮蔽同名副本。核对实际路径，不只数菜单条目。

确认归属及未被引用后，将冗余副本或链接移到所有发现路径之外保存；不要沿软链接删除另一 Agent 的来源。受管插件优先通过其管理器移除，缓存仅处理已确认不再引用的 ForgeSteward 路径。GitHub 来源不依赖本地目录；仍以本地目录为来源的，先按[固定版本与回退](#固定版本与回退)换成 GitHub 来源再删除该目录。不删除整个 `.zcode`、共享 plugins/cache 或其他 Agent 配置。卸载后新任务不再发现相应技能是运行层目标，立即零磁盘残留不在本轮保证内。SSH/WSL 的同步副本需在对应主机单独核验。

## 项目规则适配

ZCode 原生读取全局 `~/.zcode/AGENTS.md` 和当前 Workspace 的 `AGENTS.md`；不自动合并多层规则，也不展开 `@import` / `@include`。`CLAUDE.md` 不是持续加载入口。`0.2.5`、`0.2.6` 的 check-workflow 曾把标准工作流区块写入 Workspace 根目录的 `AGENTS.md`。从 `v0.2.7` 起，工作流政策只在技能正文中维护，check-workflow 删除这些区块及项目中与技能重复的工作流规则，不再向 `AGENTS.md` 写入任何内容，也不写全局规则。判定规则见包内 [技能管理的规则与删除方式](../plugins/check-workflow/skills/forge-steward-check-workflow/references/skill-owned-rules.md)。

## 验证记录与复验

2026-09-27 在桌面 `3.14.3` / 内置 CLI `0.16.9` 下重新核对六项技能发现、完整正文加载和长度边界；详见[跨 Agent 兼容性记录](skill-compatibility.md)。原静态测试中的“正文 100 × 1024 字节”已改为共同预算检查，因为已核对的实现实际限制完整文件为 100,000 字节。

| 验证层级 | 本轮结果 / 边界 |
| --- | --- |
| 本机版本与安装包静态核对 | 桌面 3.14.3、内置 CLI 0.16.9；安装包中的市场清单读取仍以实际 CLI 验证为准；未覆盖安装 |
| 仓库契约 | `tests/test_zcode_packaging.py` 校验市场派生版本、平铺技能、元数据长度、正文大小、相对引用及同步拒绝路径；不是通用 ZCode schema 验证器 |
| 实际 CLI 发现 | 内置 CLI 0.16.9 在临时工作区加载重定位的六个插件，逐项 inspect 验证可读且不截断；关闭临时插件配置后不再从该路径发现 |
| CLI 市场生命周期 | 2026-10-11 内置 CLI 0.16.9 在隔离的临时 HOME 中添加 `philfanzhou/ForgeSteward@v0.2.21`，六项装为 `0.2.21` 且与 Tag 逐文件一致；换成 `@v0.2.20` 装到 `0.2.20`；验证了卸载需 `--force`、移除市场不卸载插件、`plugins update` 跟随市场版本（含降级）；前后核对本机 `~/.zcode/cli/plugins` 与 `config.json` 未变化 |
| 桌面市场生命周期 | 未完成 GUI 添加市场、安装、更新、回退、卸载实测；界面与 CLI 共用插件目录，但界面操作本身仍未验证 |
| 模型行为 | 未调用模型，无真实业务 Issue/PR 写入，不宣称“仅选技能即可靠完成”或合并行为已通过 |

运行静态及回归测试：`python3 -m unittest discover -s tests -v`。可选实际 CLI 检查（需已安装官方应用与 Node.js；不用模型密钥、不改 HOME 或用户配置）：

```bash
FORGESTEWARD_ZCODE_CLI=/opt/ZCode/resources/glm/zcode.cjs \
  python3 -m unittest discover -s tests -p test_zcode_packaging.py -v
```

未设置变量时真实运行测试明确 skip；CI 不下载或静默安装 ZCode，默认只证明静态契约。测试可读取当前环境的发现来源，但只断言临时项目的技能，不输出其他技能清单，也不执行模型任务。实际桌面流程后续在隔离工作区复验：添加审查过的市场 → 安装六项 → 检查限定名称/完整引用 → 切换已核对的版本 → 卸载 → 新任务确认无重复。模型验收另测只读/无发布限制、execute 必需清单、review 合并门禁，不借测试操作真实生产 PR。

## 依据

- [ZCode 安装](https://zcode.z.ai/cn/docs/install)：公开版本与支持平台。
- [ZCode Plugin](https://zcode.z.ai/cn/docs/plugin)：兼容清单、自建市场、更新检测与启停卸载。
- [ZCode Skill](https://zcode.z.ai/en/docs/skill)：格式限制、调用、导入及同步。
- [ZCode Agent](https://zcode.z.ai/cn/docs/agents)：AGENTS 指令来源和加载边界。

官方文档与客户端版本出现差异时，以已验证版本行为为准并记录差额；本轮未使用非官方同名 ZCode 项目作为规范依据。
