# Agent 入口适配

## 适配原则

工作流正文只维护一份，入口只负责让实际使用的 Agent 读取它。保留项目现有权威文件、目录作用域、语言和工具特有规则；不使用自动 `/init` 或整份生成命令覆盖入口。这里只规定文档适配，不安装插件、不修改运行权限或用户级配置。

只适配用户指定或仓库已采用的 Agent。若两者均未给出且没有任何指令入口，可以在根 `AGENTS.md` 中放置新增的通用工作流约束，并新增只含 `@AGENTS.md` 的根 `CLAUDE.md`：前者供 Codex/OpenCode 读取，后者供 Claude Code 导入。创建前仍须检查隐藏配置及既有回退源，不能把“没有 AGENTS.md”当作“没有规则”。

## 已有入口的处理

| Agent | 检查的入口与风险 | 最小文档适配 |
| --- | --- | --- |
| Codex | `AGENTS.override.md`、`AGENTS.md`、已配置回退名，以及根到工作目录的实际作用域；同目录 override 可能使 AGENTS 不被读取 | 在实际生效、允许增补的入口中加入“进行此工作流前，读取并遵守 <仓库内相对路径> 的适用补充条款”。保留 override 和回退文件，不新建更高优先级文件来遮蔽旧规则。不把 Markdown 链接或 `@path` 当作自动导入证明 |
| Claude Code | `CLAUDE.md`、相关目录入口和 `.claude/rules`；既有导入的路径与作用域 | 保留现有正文，可增加到唯一工作流源的 `@相对路径` 导入，路径相对入口文件解析，放在代码块之外。已经可达时不重复导入；不导入一个会反向导入当前入口的文件 |
| OpenCode | `AGENTS.md`、`CLAUDE.md` 回退、现有 `opencode.json`/`opencode.jsonc` 的 instructions、禁用兼容设置及实际启动目录 | 优先在现有生效入口添加明确的读取指示；裸 `@path` 不是其自动导入协议。若仅有 CLAUDE 回退，不盲目新增 AGENTS 令旧规则失效；确需新增时必须保持旧规则仍明确可达、无循环且语义不变，否则保留为适配缺口。非文档配置不在本 Skill 修改范围 |
| 其他 coding agent | 项目现有指令文件、目录匹配和文档引用机制 | 根据该 Agent 当前官方文档或实际配置做薄入口引用；不猜测通用文件会自动加载，不为未使用的 Agent 批量生成入口。无可靠依据时报告未验证及所需证据 |

如果权威规则已经位于 CLAUDE.md，不将其迁移到 AGENTS.md 来满足统一布局。若一个入口的新增会改变另一 Agent 的原加载结果，先寻找不改变原规则路径的文档引用方式；无法做到时不执行该适配，其他独立增补可继续。

## 验证层级

- **静态文档检查**：原规则保留、相对路径存在、有效入口能到达工作流正文、无循环或覆盖、根和相关子目录的作用域明确；普通链接必须伴随明确读取指示。
- **实际加载检查**：目标 Agent 已可用且测试在授权范围内时，在隔离的只读检查中确认其报告的规则源。否则写明未运行，不为了测试安装 Agent、修改用户配置或启动未获授权的额外 Agent。
- **行为检查**：加载成功不等于行为正确。只有实际场景执行结果才能证明相应行为，不承诺对所有版本、配置和任意 Agent 自动兼容。

## 技能分发与规则接入的区别

ForgeSteward 提供同一份标准 `SKILL.md` 和包内相对引用；Codex/Claude 插件清单属于发布适配。OpenCode 可以使用其支持的本地技能目录（例如 `.agents/skills/check-workflow/`），需要包含整个技能目录及 `references/`，不能只复制 SKILL.md。项目文档增补不会自动完成技能安装，也不要求另外三个 Skill 已安装。现有安装流程保持独立，不在接入文档时顺手改造。

## 官方依据

以下行为于 2026-09-13 核对；使用方版本或配置不同时按实际支持范围验证。

- [Codex 项目指令发现](https://learn.chatgpt.com/docs/agent-configuration/agents-md)：目录链及 override/回退顺序。
- [Codex 技能发现](https://learn.chatgpt.com/docs/build-skills)：标准技能目录与 `.agents/skills`。
- [Claude Code 项目记忆](https://code.claude.com/docs/en/memory)：CLAUDE.md 与相对路径导入。
- [Claude Code Skills](https://code.claude.com/docs/en/skills)：标准技能正文、插件和资源路径。
- [OpenCode Rules](https://opencode.ai/docs/rules/)：AGENTS/CLAUDE 回退、instructions 与显式读取引用。
- [OpenCode Skills](https://opencode.ai/docs/skills/)：标准技能字段及本地目录发现。
