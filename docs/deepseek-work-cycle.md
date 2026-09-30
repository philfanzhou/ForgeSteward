# DeepSeek Harness 工作周期委派验收

本记录对应 Issue [#41](https://github.com/philfanzhou/ForgeSteward/issues/41)，源码目标版本 `0.2.15`，验证客户端为 macOS DeepSeek Harness `0.2.0-rc.2`。验收使用六项正式受管安装的共享技能；不修改其轮数、授权、阶段输出或平台无关术语。原 Issue 的“委派验收语义模型”仍是业务结果的依据，本文件记录测试输入、可观察证据和边界。

## 三类证据

| 层次 | 入口 | 实际覆盖 | 不代表什么 |
| --- | --- | --- | --- |
| 默认确定性回归 | `python3 -m unittest discover -s tests -v` | 临时 Git/bare remote 的独立平台操作：完整清单、单次写入、原分支修复、head/checks/审批/保护门禁、三轮暂停、独立项继续、清理及轨迹拒绝 | 没有运行模型，不能推定模型完成周期 |
| 原生工具、受控 provider | `FORGESTEWARD_DEEPSEEK=<包目录>` 后运行同一测试 | 动态加载真实 `dsh-tool-subagent`、调用它注册的 `execute`：等待 result 后仍等待 dispose；所有非 completed 失败；取消、缺失 provider/能力、背景回执、部分输出、双失败及不重派 | provider 的结果是测试注入，不是真实模型 |
| 原生 SDK、真实账号模型 | `tests/deepseek_work_cycle_probe.py` | 模型自己加载 work-cycle，派发真实原生 child，各 child 加载自己的技能和完整引用；SDK 生命周期、逐行读取 meta、前台结果、平台操作和持久交接由只读观察器核对 | fixture merge 是本地测试对象的合并，不是生产 GitHub PR 合并 |

`FORGESTEWARD_DEEPSEEK` 仍表示显式选定的 Harness 包目录，供原有 Provider 发现测试及原生工具探针使用。真实模型采用另一组输入 `FORGESTEWARD_DEEPSEEK_CLI`、`FORGESTEWARD_DEEPSEEK_PROVIDER`、`FORGESTEWARD_DEEPSEEK_MODEL` 或对应 CLI 参数，不重用包目录变量。没有选定模型输入时输出 `SKIP`；只提供部分输入、无效客户端、认证或协议失败均非零退出，不降级、不改认证或审批配置。

## 可重复运行

先完成[受管安装说明](deepseek-installer.md)中的来源核对。以下命令不下载客户端，不读取或输出凭据，由已安装客户端管理认证。模型验收需有明确调用授权；本次验收承接用户显式 work-cycle 调用的隔离模型测试授权。

```sh
python3 tests/deepseek_work_cycle_probe.py \
  --cli '/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh' \
  --provider deepseek-account --model deepseek-flash \
  --output /private/tmp/fs41-acceptance \
  --timeout 360 --max-tokens 8192
```

`--scenario startup` 可只运行一个场景。输出目录必须全新：每个场景新建真实 Git checkout、其中的本地 bare remote、平台状态和安装树。创建 SDK session 使用唯一 UUID；同一会话不得因失败重发 prompt。显式失败保留 `failure.json`、`sdk-events.json`、Git/平台现状，恢复时先回查，修正入口或夹具后用新目录重跑，不在未知写入对象上盲目重试。

真实验收默认八个有限场景；单场超时为有限秒数，finally 尝试 SDK shutdown，再有界 terminate/kill。`initialize` 完成后才发送 `session/prompt.contentBlocks`，入队 `messageId` 不算完成；父 `turn/end`、child `subagent.finished.stopReason` 才用于正常完成断言。`max-tokens` 从不作为成功，也不设置 `DSH_MAX_TOKENS_AS_SUCCESS`。8192 是本测试的输出上限，不是技能预算或客户端发现限制。

平台夹具 `tests/fixtures/deepseek_platform.py` 只提供独立平台操作，没有实现阶段编排函数。阶段 child 可额外只读加载 work-cycle 查询周期与修复计数，但必须完整加载自身阶段技能/引用，不能调用其他阶段操作或创建嵌套业务委派。父模型不能代做 `prepare/create/review/repair/merge/delete`；观察器检查每个真实 child 的技能调用、引用读取范围、终态和 handoff 操作，并在下一派发前核对父模型独立平台回查。`create` 是平台适配事务，同时创建测试分支、文件、提交、推送和夹具 PR；`merge/delete` 只处理具备本次测试授权、正确 head、通过检查/审批/保护的本地对象。

原生 `subagent` 显式 `run_in_background: false`，依赖阶段必须等终态。SDK 直接采集 child/session id，不要求模型扫描用户目录寻找 id。低频 check-workflow 在夹具种子中记录本版本 clean，其判定由现有缓存回归覆盖；本测试核对全部六项安装资源，实际所需 review/prepare/execute/fix child 依场景执行。它不声称另一次实际运行了低频清理 child。

## 场景与实际结果

| 场景 | 断言 |
| --- | --- |
| startup | 既有 P0：review child → 本地 merge/delete → prepare child `[]`；无 execute |
| repair | prepare 非空完整清单 → execute → review required → fix 原分支 → 新 review → merge/delete |
| constraints | 只读、不推送显式传到每个 child；无 create/repair/merge/delete |
| waiting | 审批未满足：保留未合并，不伪造 repair |
| uncertain | create 已持久化但回包失败：回查保持单次 create，不重新创建 |
| rounds | I1 三次修复后终审仍 required，保留暂停；I2 独立完成；无第四次修复 |
| missing | 删除 fix-feedback 后，父完整加载 work-cycle/startup/cycles、直接读取缺失资源得到诊断，最终明确报告停止且 completed；零阶段操作/派发并遵守隔离读取约束 |
| stop | 首个 child 开始即 SDK shutdown；观察器保存部分状态，核对平台未变及本次进程树已退出，不启动后继，不把 child 当 completed |

停止场景的特殊边界：此版本 SDK 在 root disposal 中先解除通知订阅，可能没有发出 child finished。观察器保留 child 终态 `unknown`，结合本次 shutdown 回包、原生 spawn 的进程内实现、CLI 及其已观察后裔退出、平台前后状态不变证明这次停止没有继续写入。它没有制造一个 `aborted/completed` 通知，也不宣称真实 child 业务成功。其他失败/超时场景同样保留未完成状态，原生工具探针分别验证明确 aborted/error/max-tokens 的失败映射。

missing 观察器只接受有限预检轨迹：本地 `read`、work-cycle `skill`、简单本地 `ls/cat` 或精确 `python3 fixture.py view`。路径按实际 root 解析，拒绝工作区外、相对逃逸和指向外部的符号链接；复合 shell、脚本、未知工具或阶段操作明确失败，不能根据最终文本推定它们安全。正常通过仍须完整资源、直接缺失读取诊断、诊断后的最终停止报告与父 completed，单独的空 completed 不足。此规则是测试验收准入，既不阻止命令运行，也不是生产运行时或任意恶意模型的通用沙箱保证。

默认回归进入现有三 OS CI，不向 CI 提供账号或模型 route。原生包与真实模型输入未配置的 skip 需与默认通过分列。原生 Windows、GUI 操作、任意其他客户端版本/配置、任意模型永远守约及生产平台均未保证；本次没有调整用户真实安装、发布 Tag/Release、迁移公开数据或部署服务。

## 2026-09-30 实际验收记录

本轮使用上述 CLI/route，隔离证据目录 `/private/tmp/fs41-acceptance3`、`/private/tmp/fs41-final`、`/private/tmp/fs41-final2`；可持久核对的 child id/head 与原始轨迹 SHA-256 见 [有限验收摘要](deepseek-work-cycle-evidence.json)。下表不将未完成场景算作通过。

| 证据 | 实际结果 |
| --- | --- |
| 默认标准库回归 | 首次实施 161 项，154 通过、7 skip；本次修复新增 4 项无模型 missing 准入反例（含多个子例），修复后结果见下文 |
| 显式原生工具 probe | 前台等待/dispose、六种 stop reason、背景回执、取消、不重派和缺失能力断言通过 |
| 真实模型 startup | 两个独立 child；平台合并与清理、prepare `[]`、完整资源、串行及依赖前独立回查通过 |
| 真实模型 repair | 5 child，完整清单→执行→必修→原分支修复→新审查、本地合并/清理及父独立回查通过 |
| 真实模型 waiting/uncertain | 各 3 child；审批等待无 merge；未知写回先回查，仅 1 次 create；通过 |
| 真实模型 rounds | 9 child；I1 恰 3 次修复后终审暂停，I2 独立合并/清理；同一原始日志按正确 actor 门禁复验通过 |
| 真实模型 missing | **未通过，撤回旧 passed 分类**：0 child、无阶段写及最终报告缺技能/停止是有限事实；父实际 `find / -maxdepth 6 ...`，随后成功读取 `/private/tmp/forgesteward-cycle2.tIPDCu` 的 fix-feedback 正文、收据及 YAML，违反工作区外读取禁令。新观察器重验同一原始 SHA 轨迹明确拒绝，未重跑模型，不主张完整 missing 通过 |
| 真实模型 stop | 仅 1 个未知终态 child，shutdown 确认、本次进程树退出、平台未变且无后继；通过有限停止断言，未计业务完成 |
| 真实模型 constraints | **未通过**：唯一一次修复夹具后复验中，两 child completed、约束均传递且平台无越界写，但 360 秒内未收到父 turn/end；保留父周期未完成，关闭本次 SDK，不重派 |

开发失败已保留：首个 prompt 的 `content` 字段被原生协议拒绝（正确字段为 `contentBlocks`），其后固定 session id 与持久会话冲突，均在模型写入前失败；修复入口后用 UUID 和新 root。早期 repair 轨迹在 review→repair 间省略父模型独立回查，强化观察器后判失败，未降低门禁。一次只读父会话在 4096 输出上限处 max-tokens，无 child 或平台写入；保留失败并在正常 SDK 输出预算下重新验收，不映射为 completed。

只读场景的早期失败进一步确认父 preflight 直接调用 `fixture.py prepare`，而夹具原 prepare 分支绕过 mutate 保护；已在适配夹具补上同一保护并增加回归。修复后只进行一次全新隔离复验，没有延长 deadline 或继续尝试让模型通过。最新失败不是旧的 prepare 越界，而是最终父模型输出没有在 360 秒内终态；原因尚未确定，不能推定是认证、审批或模型服务故障。

本次修复对应 [#44 首次必修反馈](https://github.com/philfanzhou/ForgeSteward/pull/44#issuecomment-5903446422)：旧观察器在 missing 提前返回，连未加载技能/无诊断的空 completed 都判通过；已要求完整预检和终态，并增加空轨迹、部分引用/正文、无诊断/停止报告、非 completed/缺终态、阶段操作、外部读取/扫描、相对逃逸和符号链接反例。旧 missing 原始 SHA `4dd88e1ebdd1efe1028e9d4ec12aa97ebdfc20ca4d9773737faed7e802dd8546` 保留，摘要改为 failed；没有发现密钥读取或生产写入，不扩大为未经证实的生产缺陷。

修复后验证：默认标准库共 165 项，158 通过、7 条件 skip；精确 `FORGESTEWARD_DEEPSEEK=/tmp/forgesteward-prepare.wYz4WN/harness/dsh` 的本切片 17 项全部通过（含真实原生工具、受控 provider，无付费模型）。技能预算、市场版本同步及 diff 检查通过。仅确定性验收资产/分类修复，没有新增真实模型运行，不能把合成有效轨迹通过当成真实 missing 已验收。

交付状态：新增测试/入口/记录可审查，但 #41 整体仍未完成。Draft Change Request 不关闭原 Issue，不符合完整验收的合并门禁。恢复条件分别为：全新隔离 root 的有界 missing 验收证明预检、停止和隔离读取全部满足；有界真实只读场景达到完整父终态，并重新核对约束、child 资源/终态、平台现状及交接。恢复前先读失败轨迹，不复用失败工作区重发同一写入。两个确定性反馈的修复不解除这些真实运行门禁。共享技能与实际用户安装均没有修改。
