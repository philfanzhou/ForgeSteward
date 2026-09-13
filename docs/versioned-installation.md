# 固定版本安装、升级与回退

README 已提供三种 Agent 的[升级快捷步骤](../README.md#upgrade-and-keep-only-the-selected-version)和[完整卸载步骤](../README.md#uninstall-and-verify)。本页补充固定版本、作用域及回退边界；升级 Agent 程序本身不等于升级固定 Tag 的技能。

## 先选择版本

从 [GitHub Releases](https://github.com/philfanzhou/ForgeSteward/releases) 选择已经发布的 Tag，并阅读对应表和迁移说明。下例使用 `v0.2.1`；在 Tag/Release 发布完成前不可将示例视作可用远端版本。

`v0.2.1` 是仓库快照，插件 `0.2.1` 是各自包版本；`find-work@forge-steward` 中的 `@` 后面是市场名称，不支持将它直接替换成包版本号。本仓库两个市场都从快照内的相对路径加载插件，因此选择 Tag 固定整份市场，而不是独立解析每个插件的历史版本。仍可只安装一个技能；若需要不同快照的插件混搭，需要另外设计分发来源，不能靠修改缓存实现。

固定 Tag 后不应自动跟随 main。Tag 按项目规范不可移动；若需要更强的可复现性，应记录 Release 正文给出的完整 commit SHA，并与实际 Git checkout 核对。首次发布以前不存在 `v0.1.x` Tag，不能凭插件曾用过的版本号推定远端存在同名 Tag。

## Codex

### 首次安装

在终端执行，要求 CLI 支持 `plugin marketplace add --ref`（已核对 `0.154.0` 帮助）：

```bash
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.1
codex plugin add find-work@forge-steward
codex plugin marketplace list
codex plugin list --json
```

需要其他技能时，将 `find-work` 换为 `check-workflow`、`review-and-merge`、`fix-feedback` 分别安装。新会话使用 `$forge-steward-find-work`。市场的 ref 支持 Git 分支、Tag 或提交；精确 SHA 可替换 `v0.2.1`，应使用 Release 的完整 SHA。依据：[Codex 市场配置](https://learn.chatgpt.com/docs/config-file/config-reference)、本机 `codex plugin marketplace add --help`。

### 切换已经配置的市场

1. 停止使用相关技能的会话，记录已安装插件、原 ref、配置层级和缓存内用户修改。若来源由管理员或项目配置控制，先按其规则处理，不绕过策略。
2. 按 [卸载文档](../README.md#uninstall-and-verify) 移除该市场下已安装的插件。只移除确实安装的项，不触及其他市场同名插件。
3. 移除旧的 `forge-steward` 市场配置，再添加目标 ref；不要假设再次 add 同名市场必然替换旧配置。

```bash
# 先完成上面的插件卸载与备份，再执行：
codex plugin marketplace remove forge-steward
codex plugin marketplace add philfanzhou/ForgeSteward --ref v0.2.1
codex plugin add find-work@forge-steward
```

4. 按记录重新安装需要的其他插件。使用 `marketplace list` 核对实际来源/ref，`plugin list --json` 核对安装状态/版本，检查相应缓存中的 manifest 和技能目录，并在新会话验证调用名。仅在可安装目录看到插件不等于已经安装。

升级和回退都使用上述流程，只是选择不同的已发布 ref。无需修改插件的版本字段来强迫客户端更新；如果不同内容竟然使用同一包版本，属于发布缺陷，应先由维护者纠正。

## Claude Code

### 首次安装

在终端执行（已核对 Claude Code `2.1.269` 命令帮助和官方文档）：

```bash
claude plugin marketplace add philfanzhou/ForgeSteward@v0.2.1
claude plugin install find-work@forge-steward --scope user
claude plugin marketplace list
claude plugin list
```

也可以在 Claude 会话中使用 `/plugin marketplace add philfanzhou/ForgeSteward@v0.2.1` 和 `/plugin install find-work@forge-steward`。新会话调用 `/find-work:forge-steward-find-work`。GitHub 来源的 `@ref` 支持分支/Tag；Git URL 使用 `#ref`。市场 ref 与插件来源的 SHA 字段是不同层级，不将插件来源 JSON 的 `sha` 当成 marketplace add 的参数。依据：[市场 ref 与版本规则](https://code.claude.com/docs/en/plugin-marketplaces)。

### 切换或回退

先记录该市场下全部插件与安装作用域、市场声明所在作用域和受影响项目，备份用户修改，按卸载文档处理 `user`、各项目的 `project`/`local` 安装。升级时若需保留插件持久数据，对插件卸载使用 `--keep-data`，并另外备份重要数据。**移除市场会连带卸载该市场插件，不能当作只切换一个技能的无副作用操作。** 市场声明与插件安装作用域是两个维度；当前 CLI 的 marketplace remove 省略 `--scope` 会移除所有作用域的声明。

以下仅适用于市场与插件都只在 `user` 作用域安装的情形，且已完成插件卸载：

```bash
claude plugin marketplace remove forge-steward --scope user
claude plugin marketplace add philfanzhou/ForgeSteward@v0.2.1 --scope user
claude plugin install find-work@forge-steward --scope user
```

混合作用域需要在各原项目目录按记录显式选择 `--scope project` 或 `--scope local` 处理对应声明；不要假定从一个项目运行 user 命令能清理其他项目。协调共享配置变更，管理员控制的配置交由其管理者处理。重新安装记录中的其他插件，在相应项目恢复原作用域；检查市场 ref、安装版本和新会话调用。保持 Tag 不变时刷新市场仍跟随该 ref，不会切回 main。显式包版本相同会使更新被跳过，不能把“刷新成功”当成已切换内容的证据。包内内容未变的相同版本不需要重装。

如果需要精确 commit 而非 Tag，可先克隆独立、干净的完整仓库，checkout Release SHA，然后通过 `claude plugin marketplace add /absolute/path/to/ForgeSteward` 添加本地市场；先处理同名旧市场。保留整个 checkout，不仅下载 marketplace.json，因为其插件路径是相对仓库的。不要在使用期间修改这个 checkout。

## OpenCode

### 首次安装固定快照

在 macOS/Linux 的终端执行；下面的目录必须尚不存在，有源码工作区时使用另一个目录而非覆盖：

```bash
mkdir -p "$HOME/code"
git clone --branch v0.2.1 https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-v0.2.1"
git -C "$HOME/code/ForgeSteward-v0.2.1" rev-parse HEAD
```

核对 HEAD 与 Release SHA 一致，再从要维护的目标项目目录执行：

```bash
python3 "$HOME/code/ForgeSteward-v0.2.1/scripts/opencode.py" install find-work --project .
python3 "$HOME/code/ForgeSteward-v0.2.1/scripts/opencode.py" status find-work --project .
opencode debug skill
```

全部安装使用 `--all`，用户级使用 `--user`；用户级应保留安装时的 `OPENCODE_CONFIG_DIR` / `XDG_CONFIG_HOME`。Windows 使用 Git 同样选择快照，通过 `py -3 "C:\path\ForgeSteward-v0.2.1\scripts\opencode.py" install find-work --project .` 运行安装器，替换为实际路径。

### 切换现有源码 checkout 与安装副本

以下使用已有 `$HOME/code/ForgeSteward`。先检查是否存在本地工作：

```bash
git -C "$HOME/code/ForgeSteward" status --short
git -C "$HOME/code/ForgeSteward" fetch origin --tags
```

确认工作区干净且无需要保留的分支工作后，再执行以下命令；否则新建独立 checkout。将 `v0.2.1` 替换为所选已发布 Tag 或完整 SHA：

```bash
git -C "$HOME/code/ForgeSteward" checkout --detach v0.2.1
git -C "$HOME/code/ForgeSteward" rev-parse HEAD
# 在目标项目目录执行；只选择实际已安装的技能：
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" update find-work --project .
python3 "$HOME/code/ForgeSteward/scripts/opencode.py" status find-work --project .
opencode debug skill
```

- checkout 只改变源码，不自动更新安装副本；`update` 才按当前源码显式替换，允许降级，未安装的项用 `install`。
- `update --all` 要求当前 checkout 的全部技能都已安装；只安装部分时按名称更新。新版移除或改名的技能需另按原安装名称卸载，不能认为 update 会清除不在新 catalog 中的旧项。
- `.forge-steward-install.json` 记录插件版本、复制时的源码提交及内容摘要；内容和版本完全相同时幂等不改收据，因此其 commit 不一定改为刚选择的 Tag SHA。此时核对内容摘要及当前 checkout，不将旧收据提交误判为内容不一致。
- 技能副本有用户修改、收据损坏或归属不明时会拒绝覆盖。先备份和人工确认差异，不删除收据或使用强制覆盖绕过保护。旧名/其他目录残留按卸载文档单独检查。
- 回退到首版之前的提交不保证存在同一安装器或调用接口，须先读那份快照文档；不要把未来脚本当作所有历史版本都支持的契约。

OpenCode 仍按自己的技能搜索目录发现技能；`status` 只核对本安装器的选定范围，实际发现还可能受用户级、兼容路径、祖先路径及重复副本影响。依据：[OpenCode 技能发现](https://opencode.ai/docs/skills/)。

## 从 v0.2.0 升级

目标为 `v0.2.1` 时，四个插件包均从 `0.2.0` 升至 `0.2.1`，主要改变 Codex 插件/技能的显示元数据。安装 ID、技能调用名、默认 prompt、SKILL.md 及安装器行为不变。旧 Tag 不会自动获得修复；按上文切换市场 ref 或源码并显式更新。若需回退，用相同流程选择仍保留的 `v0.2.0`，核对其[历史对应表](releases/v0.2.0.md)。完整变更见 [v0.2.1 对应表](releases/v0.2.1.md)。

## 完成标准

源 ref/SHA 与预期一致、选定插件版本符合 Release 对应表、实际安装内容与来源一致，并在新会话显示正确调用名。保留原版本和恢复记录；失败时报告实际已完成的卸载/安装，不把缓存刷新或命令退出当成完整切换。切换技能不自动回滚已修改的项目规则、代码、Issue、PR、评论或凭据。

“只保留新版”首先要求实际发现来源中不再有旧版副本：逐个核对环境、作用域和手工路径，不能以选择器只显示一个名字证明没有重复。磁盘清理另行核验：Codex 卸载命令声明清理对应本地缓存；Claude Code 旧版缓存有后台清理宽限期；OpenCode update 替换选中的受管目录，但不删除其他作用域、退役名称和手工副本。不要把这三种行为统一宣传为立即零残留。

需要立即清理磁盘时，停止相关会话，列明确切旧路径，核对 ForgeSteward 归属及所有配置/作用域的引用；受管安装用对应卸载命令，确认无人引用的缓存或手工副本先移出全部发现路径备份，复核后再删除。不得按宽泛通配符删除共享目录。旧源码 clone 与安装副本分开处理；OpenCode 安装器及本地路径市场仍依赖的 checkout 必须保留。详见 README 的[仅保留目标版本核验清单](../README.md#verify-that-only-the-intended-version-remains)。
