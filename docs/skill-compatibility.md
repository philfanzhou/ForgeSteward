# 跨 Agent 技能长度与加载兼容

本说明记录 ForgeSteward 支持的 Codex、Claude Code、OpenCode 和 ZCode 的加载差异，以及本仓库如何防止修改后再次出现技能截断。仓库级修改要求见 [AGENTS.md](../AGENTS.md#skill-长度与跨-agent-兼容)；可执行预算的唯一数值来源是 [check_skill_limits.py](../scripts/check_skill_limits.py)。核对日期：2026-09-20。

## 已核对的差异

| Agent 与核对基线 | 入口或正文 | 描述、发现列表与恢复 | 结论 |
| --- | --- | --- | --- |
| Codex，上游提交 `d7d9f2b9b53b53568b30c4dea7e095ec276ebe9c` | 所选技能主提示词最多 8,000 UTF-8 字节，沿字符边界截断并发出用户遇到的告警 | 发现列表另有动态预算；不能把发现列表限制与所选技能正文混淆 | 采用更低的仓库入口预算，并在入口明确指向完整规则 |
| Claude Code，官方技能文档；本机 CLI `2.1.278` | 官方建议 `SKILL.md` 少于 500 行；本次未确认一般本地技能首次加载时的固定字节硬限制 | 压缩后每项保留前 5,000 tokens，总计 25,000 tokens，较旧技能可能不再附加；发现列表也有独立预算 | 将行数建议纳入本仓库维护约束；明确缺失规则时重新读取，不承诺压缩后全部永久保留 |
| OpenCode，CI 固定 `1.18.30`，提交 `3104c1428ec91f809e5ab86631300de41eb6952e`；本机 `1.18.31` | 核对的 CLI Skill 工具加载正文后，经通用工具输出截断器处理；默认 2,000 行 / 50 × 1,024 UTF-8 字节，可由配置改变，计入工具包装内容 | 官方格式要求名称 1–64 字符、描述 1–1,024 字符；发现、加载正文和模型实际接收输出是不同验证层 | 不把“读出了文件”当作模型必然完整收到；保持入口和引用短小，检测工具截断后补读 |
| ZCode 桌面 `3.14.0` / 内置 CLI `0.16.9`，官方技能文档及本机加载实现 | 官方称正文超过 100KB 截断；本机实际在去掉 frontmatter **之前**按整个文件 **100,000 字节**限制读取 | 描述超过 1,024 个 JavaScript UTF-16 单元时整项被忽略；发现列表使用描述摘要，另有总预算 | 不能沿用“正文 100 KiB”作为精确边界；使用更保守的共同入口预算，单独校验描述 |

Claude 的 500 行是编写建议；Codex 和 ZCode 上述数值是核对版本的截断边界；OpenCode 数值是通用工具输出的默认配置。三者不具有相同含义，也不是对所有历史和未来版本的保证。UTF-8 字节数、Unicode 字符数、JavaScript UTF-16 单元和模型 token 数不可互换。

依据：

- Codex：[主提示词预算及截断函数](https://github.com/openai/codex/blob/d7d9f2b9b53b53568b30c4dea7e095ec276ebe9c/codex-rs/ext/skills/src/render.rs)、[所选技能注入与告警](https://github.com/openai/codex/blob/d7d9f2b9b53b53568b30c4dea7e095ec276ebe9c/codex-rs/ext/skills/src/extension.rs)、[官方技能加载说明](https://developers.openai.com/zh-Hans/docs/build-skills)。
- Claude Code：[配套文件与 500 行建议](https://code.claude.com/docs/en/skills#add-supporting-files)、[技能内容生命周期](https://code.claude.com/docs/en/skills#skill-content-lifecycle)、[发现列表描述预算](https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short)。
- OpenCode：[官方格式约束](https://opencode.ai/docs/skills/)、[Skill 工具](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/opencode/src/tool/skill.ts)、[通用工具包装](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/opencode/src/tool/tool.ts)、[默认输出预算及配置覆盖](https://github.com/anomalyco/opencode/blob/3104c1428ec91f809e5ab86631300de41eb6952e/packages/opencode/src/tool/truncate.ts)。
- ZCode：[官方技能格式及上下文说明](https://zcode.z.ai/en/docs/skill)。本机 `zcode.cjs` 的 `NodeSkillAdapter.loadSkill` 与 Skill handler 使用 `1e5`；description 校验使用 `.length > 1024`。核对文件 SHA-256：`8f5cfccf2a899b92e57bc2a5760b949c1a928f739652fffc9e6d07c24f11ba05`。符号名可能随构建改变，以版本、文件哈希及实际边界探针共同识别，不能把本机路径当作别人机器上的固定路径。

## 仓库预算与组织方式

以下是本项目主动采用的维护预算，不是给四个 Agent 虚构一套相同限制。实际检查值从脚本读取；修改数值须连同本说明中的理由、兼容性证据和边界测试一起更新。

| 对象 | 当前维护预算 | 理由 |
| --- | --- | --- |
| 完整 `SKILL.md`，包括 frontmatter 和实际换行字节 | ≤ 6,000 UTF-8 字节，< 500 行 | 为当前最小的已知入口截断边界保留 2,000 字节余量，同时遵循 Claude 的行数建议 |
| 每个 `references/**/*.md` | ≤ 8,000 UTF-8 字节，< 500 行 | 控制一次文件读取的规模；引用并非自动注入入口，不强行套用 6,000 字节，也不宣称 8,000 是通用工具硬限制 |
| `description` | 非空，≤ 1,024 UTF-16 单元 | 覆盖已验证的 ZCode 字符串计数和其他平台公开描述要求；一个 emoji 可能占两个单元 |
| `name` | 1–64 位 ASCII 小写字母、数字和单连字符，与技能目录一致 | 保持共同发现格式，避免已装入包但不能发现 |

当前仓库的 `name`、`description` 使用不带引号、注释、别名或折行的单行文本。校验器拒绝不支持的写法，避免把 `description: >` 的一个符号当作整段描述长度。它不是通用 YAML 解析器；需要其他写法时先补齐解析与多 Agent 验证。

技能入口保留目的、授权、阶段导航和输出契约。详细规则按阶段放入包内 `references/`，用相对 Markdown 链接指明读取时机；文件路径以技能安装目录为基准。跨文件引用不能依赖仓库外文件或另一个插件的安装。规则不可藏到 `assets/`、脚本字符串或未受检 Markdown 中来绕过预算；大型非指令数据应作为任务数据，由工具定向处理。

预算是上限，不是建议写满。描述应先写用途和触发场景，详细流程留在正文。引用文件可按阶段继续拆分，但不能将原有保证改成可选项，也不能只靠摘要替代完整门禁。读取截断时分段补读到末尾；文件缺失时说明具体路径并停止受影响操作；上下文压缩后重读当前阶段缺失的规则。这些运行要求由各独立技能携带，静态检查不声称能证明模型一定遵守。

## 自动检查与本地使用

```bash
python3 scripts/check_skill_limits.py --check
python3 -m unittest discover -s tests -v
```

检查器无需网络或第三方 Python 包，不写文件。它自动遍历所有插件及新增技能，逐文件输出实际字节、行数和预算；输出描述总量供排查，但不把这个总量当作任一客户端的发现列表预算。出现超限、非法元数据、空技能集合、缺失/越界引用或不可达引用时返回非零状态，并指出文件和处理方向。

CI 在 Linux、macOS、Windows 安装器检查中执行同一命令；单元测试覆盖中文/emoji、UTF-16 边界、CRLF 原始字节、行数、临界值和超限一单位、重复/多行元数据、引用缺失/越界/循环、未来插件自动纳入和 CLI 只读退出状态。安装器测试继续核对所有资源逐字节一致，避免拆分后漏打包。无需额外安装本地 Git hook；即使贡献者忘了运行命令，PR 检查仍会报错。

## 运行验证与维护

OpenCode 的真实发现测试核对每项加载正文与源文件一致，CI 继续使用固定 `1.18.30`；本机 `1.18.31` 另行实测。ZCode 用临时插件目录检查五项完整正文、资源路径与 `truncated`，并通过临时技能验证 100,000 / 100,001 字节和 512 / 513 个 emoji 描述的边界。两者都不调用模型，也不修改用户插件或全局配置。可选 ZCode 验证命令见 [ZCode 文档](zcode.md#验证记录与复验)。

Codex 截断路径依据固定源码提交核对；Claude Code 依据官方说明核对，本机版本仅作环境记录。本轮不宣称完成两者的模型调用或压缩恢复端到端测试。ZCode 桌面 GUI 市场生命周期仍不在 CLI 验证范围内。

升级 Agent 验证版本或新增 Agent 时，先复核官方文档及可用加载实现，记录限制属于入口、元数据列表、工具输出还是上下文恢复，以及单位和是否可配置；必要时在临时目录执行边界探针。新发现更严格限制时同步缩减预算并整理超限技能；限制放宽也不自动增大入口。复验记录留在本说明和发布输入，不覆盖历史发布证据。

没有静态长度检查能保证所有用户配置、其他已安装技能、工具包装、任意模型和整段会话都不触发上下文限制。这里防止的是本仓库可控制的入口与资源增长回归；个性化更小预算、动态发现列表拥挤和压缩后的规则缺失，仍须由客户端告警及技能中的完整读取要求处理。
