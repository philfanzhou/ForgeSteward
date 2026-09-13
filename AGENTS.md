# ForgeSteward 项目指引

## 规则来源

- 本文件是仓库级 Agent 指令的唯一事实来源。
- Codex 和 OpenCode 直接读取本文件。
- Claude Code 通过仓库根目录的 `CLAUDE.md` 导入本文件。
- 不要在平台适配文件中复制本文件的通用规则。通用规则只在此处维护，避免内容漂移。

## 主干交付

- 本仓库的 `main` 和默认分支只能通过 Pull Request 更新。修改前创建工作分支，commit 和 push 均在工作分支上进行，不在主干直接提交或推送。
- 不绕过、停用或放宽远端主干规则以完成交付。提交 PR 不代表获准合并；按用户授权和仓库审查要求另行处理合并。
- 远端规则禁止直接更新、强制推送和删除受保护主干，且不配置绕过名单。规则在 GitHub 上管理，本文件不能代替远端保护。

## 项目定位

ForgeSteward 是一组面向多种编码 Agent 和代码托管平台的仓库维护 Skill，用于增补接入工作流所需的项目约束、将 Issue 准备到可实施状态、按 Issue 清单实现并提交 Change Request、审查并在满足条件时合并 Change Request，以及根据 Review Feedback 修复代码。

各 Skill 应保持独立安装，但必须统一版本管理。Skill 名称和核心流程不得绑定 GitHub、GitLab、Gitea 等特定平台。只有真正跨 Agent、跨托管平台通用的行为才应共享；平台特有的 API、术语、清单、目录和调用方式应放在各自适配层中。

核心设计统一使用以下平台无关术语：

- `Issue` 表示托管平台上的问题或工作项。
- `Change Request` 表示等待审查和合并的变更，例如 GitHub Pull Request 或 GitLab Merge Request。
- `Review Feedback` 表示针对 Change Request 的 Comment、Discussion 或 Review Thread。

## 统一版本

- 根目录 `VERSION` 是当前源码目标版本的唯一事实来源，不含 `v` 前缀；它不代表该版本已经发布。
- 所有插件（包括未来新增插件）的 `plugin.json`、`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 中的版本必须与 `VERSION` 完全一致，不允许按插件独立升版。
- 每次发布统一升版，未修改功能的插件也同步版本；仅文档或安装器变更的发布同样遵守此规则。不要求每个开发提交都升版，未发布的同一目标版本可以继续完善。
- Agent 或自动化修改版本时，只能将 `X.Y.Z` 的最后一位 `Z` 加一，保持 `X.Y` 不变；即使新增 Skill、改名或存在不兼容变化，也不得自行提升 minor 或 major。只有用户明确指定目标版本或指定调整其他位时才按其要求执行。不兼容变化仍须记录迁移说明。候选版后缀及发布渠道的新增或变更也须由用户明确指定，不借后缀绕过此限制。
- 发布 Tag 必须为 `v` 加 `VERSION`，Release 对应表中的全部插件版本必须与其一致。发布前按 `docs/releasing.md` 核对；CI 必须校验所有插件清单与 `VERSION` 一致。
- 已发布 Tag 和历史版本对应表保持不变，不因采用新规则改写历史；修复必须使用新版本。修改版本规则不等于授权合并、发布或升级用户安装。

## 文档语言

- 除 `README` 文件外，所有项目设计文档必须使用简体中文编写。
- 项目设计文档包括架构说明、设计方案、规范、决策记录、实施计划和 `docs/` 下的设计类文档。
- `README` 文件不受上述语言限制，可根据公开分发和使用者需求选择语言。
- 代码标识符、API 名称、命令、文件路径和无法准确翻译的技术术语可以保留英文；必要时在中文上下文中解释。

## 托管平台协作语言

- Issue 标题必须使用英文。
- Change Request 标题必须使用英文，包括 GitHub Pull Request、GitLab Merge Request 及其他平台的等价对象。
- Issue 和 Change Request 的正文必须使用简体中文。
- Issue、Change Request 和 Review 中的 Comment、Discussion 与 Review Thread 必须使用简体中文。
- 引用代码、日志或外部原文时可以保留其原始语言，但分析、结论和行动说明必须使用简体中文。
