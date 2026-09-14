# Agent 入口适配

## 固定布局

check-workflow 只使用以下布局，不按项目另行设计入口：

| 文件 | 管理内容 | 作用 |
| --- | --- | --- |
| 根 `AGENTS.md` | `forge-steward:workflow` 区块 | Codex、OpenCode、ZCode 直接读取的工作流约束 |
| 根 `CLAUDE.md` | `@AGENTS.md` 导入行 | Claude Code 通过导入读取同一份区块 |
| 根 `AGENTS.md` | `forge-steward:claude-rules` 区块，仅当 `CLAUDE.md` 另有内容时存在 | 提示不读取 `CLAUDE.md` 的 Agent 去读取其中的项目规则 |

区块正文只有一份，位于 `AGENTS.md`；`CLAUDE.md` 只导入，不复制正文。区块外的文字不属于本技能管理范围；唯一例外是经内容和提交历史确认的旧版增补，见 [旧版增补识别与删除](legacy-additions.md)。

## 各 Agent 的加载关系与限制

| Agent | 加载关系 | 已知限制与处理 |
| --- | --- | --- |
| Codex | 从项目根到工作目录逐级读取 `AGENTS.md` | 同一目录存在 `AGENTS.override.md` 时读取 override 而不是 `AGENTS.md`。脚本只输出 `Warning`，不修改 override，报告为入口缺口 |
| Claude Code | 读取 `CLAUDE.md`，展开代码块之外的 `@相对路径` 导入 | 代码块中的导入不生效，脚本不把它视为已有导入。`CLAUDE.md` 是指向 `AGENTS.md` 的符号链接时，Claude 直接读到区块，脚本不写入 `CLAUDE.md` |
| OpenCode | 优先读取 `AGENTS.md`，不存在时才回退读取 `CLAUDE.md`；也可在 `opencode.json` 的 `instructions` 中配置文件 | 新建 `AGENTS.md` 后不再回退读取 `CLAUDE.md`，所以 `CLAUDE.md` 另有内容时写入读取指示区块。读取指示依赖 Agent 遵循，不等于自动加载；本技能不修改 OpenCode 配置 |
| ZCode Agent | 读取用户 `~/.zcode/AGENTS.md` 与当前 Workspace 的 `AGENTS.md` | 不展开 `@import`，不自动合并子目录规则，`CLAUDE.md` 不是持续加载入口；读取指示同样依赖 Agent 遵循。不修改用户级文件 |
| 其他 coding agent | 以其官方文档或实际配置为准 | 未验证是否读取 `AGENTS.md`；不为其生成额外入口，报告为未验证 |

## 验证层级

- **静态检查**：`sync_workflow_block.py --check` 退出码为 `0`，表示区块与模板逐行一致、`CLAUDE.md` 含有效导入、读取指示区块与 `CLAUDE.md` 的内容相符。
- **实际加载检查**：目标 Agent 可用且获得授权时，才在隔离的只读会话中确认其报告的规则来源；否则写明未运行，不为测试安装 Agent 或修改用户配置。
- **行为检查**：加载成功不等于行为正确，不承诺对所有版本、配置和任意 Agent 自动兼容。

## 技能分发

技能目录须完整分发，包括 `SKILL.md`、`assets/`、`scripts/` 和 `references/`；只复制 `SKILL.md` 时拿不到模板和脚本。Codex/Claude 插件清单属于发布适配，ZCode 复用 Claude 兼容插件清单；OpenCode 可使用其本地技能目录，例如 `.agents/skills/forge-steward-check-workflow/`。项目文档同步不会自动安装技能，也不要求其他技能已安装。

## 官方依据

以下行为于 2026-09-13 核对；使用方版本或配置不同时按实际支持范围验证。

- [Codex 项目指令发现](https://learn.chatgpt.com/docs/agent-configuration/agents-md)：目录链及 override/回退顺序。
- [Codex 技能发现](https://learn.chatgpt.com/docs/build-skills)：标准技能目录与 `.agents/skills`。
- [Claude Code 项目记忆](https://code.claude.com/docs/en/memory)：CLAUDE.md 与相对路径导入。
- [Claude Code Skills](https://code.claude.com/docs/en/skills)：标准技能正文、插件和资源路径。
- [OpenCode Rules](https://opencode.ai/docs/rules/)：AGENTS/CLAUDE 回退、instructions 与显式读取引用。
- [OpenCode Skills](https://opencode.ai/docs/skills/)：标准技能字段及本地目录发现。
- [ZCode Agent](https://zcode.z.ai/cn/docs/agents)：工作区 AGENTS 与全局入口、非递归及非自动导入边界。
- [ZCode Plugin](https://zcode.z.ai/cn/docs/plugin)：Claude 兼容插件清单；[ZCode Skill](https://zcode.z.ai/en/docs/skill)：技能选择与完整目录。
