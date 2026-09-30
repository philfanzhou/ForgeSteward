# DeepSeek Harness 安装与维护

## 范围及来源

从未发布源码目标 `0.2.15` 起提供 `scripts/deepseek.py`，适配 DeepSeek Harness 的原生文件系统技能发现。Python 3.9+ 标准库即可运行，无需 npm 插件、运行中的 Harness 或模型密钥。六项技能保留原始目录、正文、引用与脚本；`--all` 自动读取当前 catalog，不固定未来数量。Claude/Codex 的 marketplace 不是 Harness 原生市场。

共享生命周期实现位于 `scripts/skill_installer.py`；`scripts/opencode.py` 保留既有命令、作用域、schema 1 收据、输出及退出码。DeepSeek 薄适配只处理路径和发现提示，不改变技能业务规则。安装单项不要求同时安装全部；完整 `work-cycle` 还需同版本五项阶段技能和子 Agent 能力，该模型行为另由 [Issue #41](https://github.com/philfanzhou/ForgeSteward/issues/41) 验收。

依据：[官方 Skills 说明](https://deepseek-harness.github.io/deepseek-harness/en/reference/subsystems/skills)，以及 2026-09-30 本机桌面/内置包 `0.2.0-rc.2` 的实际 `FileSystemSkillProvider` 和 `resolveDshHome`。包内 `dsh-skill-filesystem/lib/index.js` SHA-256 为 `244e92e032ef15e96cb60c9e2cfddf5d89e167eb171fcbfd83e9415b0455a0d7`，`dsh-home-paths/lib/index.js` 为 `97c1c10b299a4f2aec5f34bac5370cad3834391cd75c91a76b1e7b8a643584f5`。这是核对版本的证据，不承诺未来所有客户端。

## 首次安装与作用域

先取得独立、可信的 checkout。下例跟随当前开发源码，使用前核对其 commit、`VERSION` 和修改；未发布 `0.2.15` 不能当作已发布 Tag。若已有源码，直接使用其绝对路径。

```bash
mkdir -p "$HOME/code"
git clone https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-deepseek"
git -C "$HOME/code/ForgeSteward-deepseek" rev-parse HEAD
git -C "$HOME/code/ForgeSteward-deepseek" status --short
# 在需要维护的项目目录执行：
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" list
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" install prepare-work --project .
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" status prepare-work --project .
```

选择完整名 `forge-steward-prepare-work` 等价；全部安装使用 `install --all --project .`。每条命令显式且互斥地选择 `--project PATH` 或 `--user`。项目 PATH 必须存在：从它向上寻找最近的 `.git` 标记（目录或 worktree 文件），写到该根的 `.dsh/skills/<name>`；没有 Git 标记时使用 PATH 本身，与核对的原生提供方一致。路径含空格时加引号，子目录不是自动创建另一个安装作用域。拒绝尚未解析和解析后的符号链接及 Windows reparse point，避免 resolve 丢失保护。

用户安装用 `install prepare-work --user`，目标为 `$DSH_HOME/skills`，未设置、空串或纯空白值回退到 OS home 的 `.dsh/skills`。支持 `~`、`~/` 和 `~\` 开头；非空相对值按调用 cwd 解析，保留非空值的前后空白。每次打印绝对目标。Harness 的显式 `dshHome` 配置优先于环境；如果客户端配置覆盖它，请让调用安装器的 `DSH_HOME` 指向相同路径。安装器不读或修改账号、凭据和配置。

Windows PowerShell 使用已安装的 Python 3.9+ 与实际 checkout：

```powershell
py -3 "$HOME\code\ForgeSteward-deepseek\scripts\deepseek.py" install --all --project .
```

新会话从目标项目打开，核对技能清单中的完整名称及来源，加载 `forge-steward-prepare-work` 后检查配套资源可读。安装器的 `status` 只核对选中目标，不替代客户端发现验证。当前提供方按项目 `.dsh/skills`、项目 `.agents/skills`、自定义根、用户 `$DSH_HOME/skills`、用户 `.agents/skills`、内置根提供候选排名；同名技能可能被更高优先级副本遮蔽。提供方不递归扫描插件市场目录，不能仅添加 ForgeSteward 仓库根便声称安装完成。

## 显式更新、固定源码及回退

```bash
# 在目标项目执行；仅选择实际已安装项：
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" update prepare-work --project .
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" status prepare-work --project .
```

全部安装时才能 `update --all`；缺失安装要求先 install，任一选中项有冲突则全批拒绝。安装器只用本地 checkout，不隐式 fetch、下载或执行远端命令。需要固定版本时先在 [Releases](https://github.com/philfanzhou/ForgeSteward/releases) 选择含本适配的已发布 Tag，或记录经审阅的完整 commit。不要使用早期 `v0.2.1`，它没有 DeepSeek 入口。独立快照目录不存在时：

```bash
# 先将 FULL_REVIEWED_COMMIT 替换为完整的可信 SHA：
git clone https://github.com/philfanzhou/ForgeSteward.git "$HOME/code/ForgeSteward-deepseek-fixed"
git -C "$HOME/code/ForgeSteward-deepseek-fixed" checkout --detach FULL_REVIEWED_COMMIT
git -C "$HOME/code/ForgeSteward-deepseek-fixed" rev-parse HEAD
git -C "$HOME/code/ForgeSteward-deepseek-fixed" status --short
python3 "$HOME/code/ForgeSteward-deepseek-fixed/scripts/deepseek.py" update prepare-work --project .
```

对已发布 Tag 使用相同 checkout 流程并核对非 draft Release 与 SHA。回退选取保存的旧快照，再显式 update；支持版本降级和同版本内容变化。不要对 detached checkout 使用 git pull，不覆盖有本地工作的源码。收据记录版本、source commit/dirty、全部文件摘要与空目录；相同版本及摘要的 install/update 保持字节、mtime、收据不变，因此收据的 commit 不一定随等价源码 checkout 改变。它不是签名，信任源码仍由调用方负责。

## 冲突、事务及卸载

未托管同名目录、用户增删改或空目录变化、损坏回执和链接不覆盖、不采用，不提供 force。备份完整目录及差异，将确认冲突的副本移到全部技能搜索路径之外，再安装；不要删回执绕过保护。不同 Agent、项目/用户和兼容根各自独立，更新不清理其他根。

写命令持有目标父目录的 `.forge-steward.lock`。全批先校验和暂存到父目录 `.forge-steward-txn-*`，随后 rename 发布完整资源与 schema 1 回执；普通 copy/rename 失败和 KeyboardInterrupt 逆序回滚，正常清理。回滚失败报告确切事务路径并保留 `old-<skill>` 备份，下次拒绝遗留事务。第二进程拒绝现有锁，不删第一进程锁。中断时确认进程已停止，保留整个事务并恢复实际安装，再移出事务及清理陈旧锁后重试。不保证 SIGKILL、断电、文件系统损坏、恶意并发写入或运行中 Agent 的多目录原子快照。

```bash
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" uninstall prepare-work --project .
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" uninstall --all --project .
# 用户作用域单独操作，保持同一个 DSH_HOME/cwd：
python3 "$HOME/code/ForgeSteward-deepseek/scripts/deepseek.py" uninstall --all --user
```

卸载无需原源码仍有该技能，只移除选中、有效且未修改的受管目录与回执，保留其他技能和空容器。`--all` 可移除有效项并报告无收据/手工/旧名候选；损坏、修改的选中受管项仍整批阻止。只扫描打印目标的直接子项：全部选择报告 `forge-steward-*` 与已知四个旧名，具名选择只报告所选名称及已知旧名。候选不代表归属，不跟随链接，不删除未知内容。

退出 `0` 表示有限扫描无残留，`1` 表示操作/扫描失败，`2` 表示有候选需人工确认（参数用法错误也可能是 2，应结合输出）。错误优先，不把残留或扫描失败写成清理成功。其他项目、用户、agents/custom/bundled 根及旧会话未扫描；项目卸载不证明用户副本消失。在新会话复核真实发现及资源来源，备份并仅处理已确认归属的副本，不删整个配置或缓存。卸载不撤销项目代码、规则、Issue、PR 或历史工作。

## 验证与支持边界

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_skill_limits.py --check
python3 scripts/sync_marketplace.py --check
git diff --check
```

共享生命周期回归在三 OS CI 执行，DeepSeek 套件复用 OpenCode 的完整事务和保护断言，并增加路径矩阵、固定完整 commit 回退及实际两个进程锁测试。真实包不自动下载：把解包后的 Harness 包目录（包含 `node_modules/@deepseek-ai/dsh-skill-filesystem/lib/index.js` 及 `dsh-home-paths` 和其依赖）显式交给测试；桌面 ASAR 应先由用户另行提取。需要可用 Node.js，默认 `node`，可用第二个变量指定绝对可执行路径。

```bash
FORGESTEWARD_DEEPSEEK=/absolute/path/to/dsh \
FORGESTEWARD_DEEPSEEK_NODE=/absolute/path/to/node \
python3 -m unittest discover -s tests -p test_deepseek_installer.py -v
```

未配置 `FORGESTEWARD_DEEPSEEK` 明确 skip，配置但缺包、缺 Node 或不兼容则失败。探针仅导入显式运行时，以隔离项目、用户、agents、custom、bundled 根调用真实 Provider，不输出其他用户技能、不调用模型。逐项比较全部完整正文、resourceBase 和资源摘要，检查 `.git` 文件子目录、home 矩阵和候选排名；项目 CLI 卸载后同提供方仍发现用户副本，再卸载用户后重发现为空。

本机 macOS 的 `0.2.0-rc.2` 实际包已通过上述验证；原生 Windows Harness、桌面 GUI、模型行为及完整 work-cycle 未验证。CI 不获取 Harness，只明确跳过真实测试；OpenCode 真实发现 CI 继续固定 `1.18.30` Linux。长度检查通过不证明模型永远完整收到全部规则，详见 [跨 Agent 兼容边界](skill-compatibility.md)。
