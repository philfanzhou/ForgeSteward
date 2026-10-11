# 最终汇报

work-cycle 结束时给用户的汇报只按本文件生成，章节、顺序和用词以此为准；其他规则只说明什么内容记进哪个字段。

## 汇报数据

运行中把结果记入运行目录的 `handoff.json`（即[运行记录](run-record.md)中的短交接，其他已有字段照常保留，汇报不读）。写入前先按远端实际状态核对；脚本只检查格式和词表，不保证数据与远端一致。

| 字段 | 内容 |
| --- | --- |
| `requested_cycles`、`completed_cycles` | 请求轮数（正整数）、实际跑完的轮数（整数） |
| `stop_reason` | 停止原因，日常中文一句 |
| `startup_check` | 启动检查：check-workflow 运行还是跳过，缓存的版本和时间 |
| `startup_queue` | 开始前已有的 PR：`count` 个数，`note` 处理情况（可为空） |
| `concurrency` | `enabled`；开启时 `agent_limit`，未开启或退回串行时 `serial_reason`；可选 `note` 写多个 PR 同时跑 CI 的排队，排队多花的时间不算省下的时间 |
| `branch_cleanup` | 遗留分支清理的结果，保留了哪些分支和工作区 |
| `change_requests` | 每个 PR：`url`、`number`、`issues`（对应 Issue 列表）、`result`、`reason`、`next` |
| `issues_without_change_request` | 没有 PR 的 Issue：`issue`、`result`（只能是“已暂停”或“未开始”）、`reason`、`next` |
| `exceptions` | 每项 `what` 写实际错误；`recovery` 写状态核对、恢复动作及结果、最后确认的远端状态、未完成的阶段和恢复条件 |
| `needs_you` | 可选，其他需要用户处理的事项，一句一项 |
| `agent_check` | 可选，其他 Agent 安装检查（见[安装检查](agent-check.md)）：`file` 写运行目录下的结果文件名，检查做不了时只写 `unavailable` 原因；不填时写“未检查” |

除 `needs_you` 外都必填，列表可以为空。`reason`、`next` 可以是空字符串，但结果为“等你审批”“已暂停”时 `reason` 必填。Issue 写整数编号，跨仓库时写 `owner/repo#5` 这样的文本。

## 结果词

`result` 只能用下面 7 个词：

- 已合并
- 等你审批：检查都过了，仓库要求维护者批准
- 等待 CI
- 等待外部审批：需要用户以外的人或系统放行
- 已暂停：第三次修复后终审未过、真实阻塞，或运行停止时还没处理完；原因里写清楚
- 已关闭未合并
- 未开始：Issue 还没有 PR

用户中途停止时照常生成汇报，没处理完的项记“已暂停”并写原因。

## 生成与兜底

1. 结束时运行[运行记录](run-record.md)中的 `report` 子命令，把它的输出原样贴给用户，最多在末尾加一段“补充说明”。它同时写入运行目录的 `report.md`。
2. 返回 `1` 表示数据有问题，按输出列出的字段改正 `handoff.json` 后重试，最多 3 次。
3. 仍不通过、返回 `2`、找不到可用的 Python 或脚本无法运行时，照下方模板手写，第一行写“本次汇报由模型手写，原因：……”，其余格式不变。耗时取 `summary` 的结果或按事件记录推算，都没有时写“无记录”。

## 规格

脚本从这里读取章节、结果词和名称对照；规则和脚本共用这一份，不另写：

```json report-spec
{
  "title": "work-cycle 运行汇报",
  "sections": ["结论", "需要你处理", "PR 结果", "本次概况", "耗时", "异常与恢复", "其他 Agent 安装情况"],
  "results": ["已合并", "等你审批", "等待 CI", "等待外部审批", "已暂停", "已关闭未合并", "未开始"],
  "merged": "已合并",
  "needs_you": ["等你审批", "已暂停"],
  "issue_only": ["已暂停", "未开始"],
  "stages": {"check-workflow": "检查规则", "prepare": "准备", "implement": "实现", "review": "审查",
             "fix": "修复", "merge": "合并", "cleanup": "清理"},
  "waits": {"ci": "等 CI", "lock": "等本地资源"},
  "agents": {
    "unchecked": "未检查",
    "unavailable": "无法检查：{reason}",
    "absent": "未安装 Agent",
    "current": "最新",
    "none": "没有找到装了的受支持 Agent",
    "all_latest": "都已是最新（v{latest}）",
    "latest_unknown": "无法确认最新版本：{reason}",
    "other_scopes": "（另有非用户级安装）",
    "statuses": {
      "缺少": "{name}：未安装（最新 v{latest}）",
      "不完整": "{name}：缺 {missing}（最新 v{latest}）",
      "落后": "{name}：{versions}，落后于最新 v{latest}",
      "最新": "{name}：已是最新 v{latest}",
      "高于最新正式版": "{name}：{versions}，比最新正式版新，不处理",
      "无法判断": "{name}：无法判断：{reason}"
    },
    "without_latest": {
      "缺少": "{name}：未安装",
      "不完整": "{name}：缺 {missing}",
      "已装": "{name}：已装 {versions}"
    }
  }
}
```

## 模板

7 个章节按顺序每次都出现，没有内容的章节写“- 无”。

```markdown
## work-cycle 运行汇报

结论：合并 <已合并的 PR 数> 个 PR，<需要你处理的项数> 项需要你处理。共跑 <completed_cycles> 轮（上限 <requested_cycles>），<stop_reason>。

### 需要你处理
1. PR <PR 链接> <result>：<reason>；下一步：<next>。
2. Issue #<issue> 已暂停：<reason>；下一步：<next>。
3. <needs_you 的一项>。

### PR 结果
| PR | 对应 Issue | 结果 | 说明 |
|---|---|---|---|
| <PR 链接> | #<issue>、#<issue> | <result> | <reason>；下一步：<next> |
| 无 | #<issue> | <result> | <reason>；下一步：<next> |

### 本次概况
- 启动检查：<startup_check>
- 开始前已有的 PR：<count> 个，<note>
- 轮数：<completed_cycles> / <requested_cycles>，停止原因：<stop_reason>
- 同时进行：开启，最多 <agent_limit> 个；<note>
- 分支清理：<branch_cleanup>

### 耗时
- 总计 <总时长>：准备 12、实现 48、审查 25（分钟）
- 其中等 CI <时长>，等本地资源 <时长>

### 异常与恢复
- <what>。处理：<recovery>

### 其他 Agent 安装情况
- 未检查
```

填写说明：

- `<PR 链接>` 写成 Markdown 链接，文字为 `#<number>`，地址为 `url`。
- 需要你处理：先列结果为“等你审批”“已暂停”的 PR，再列“已暂停”的 Issue，最后列 `needs_you`，各按数据顺序连续编号；项数即结论里的数字。
- PR 结果：先按顺序列 PR，再列没有 PR 的 Issue（PR 列写“无”）；Issue 列表为空写“无”。
- 说明和需要你处理里，`reason`、`next` 为空的部分连同“下一步：”一起省略；文本中的换行换成空格，句末多余的标点去掉，表格里的 `|` 写成 `\|`。
- 同时进行：未开启或退回串行时写“同时进行：未开启，原因：<serial_reason>”；`note` 为空时省略分号及其后内容；开始前已有的 PR 的 `note` 为空时同样省略逗号及其后内容。
- 其他 Agent 安装情况：按规格 `agents` 的写法，`absent` 状态不列；全部为 `current` 且没有非用户级安装时只写一行 `all_latest`；查不到最新版时先写 `latest_unknown`，各 Agent 改用 `without_latest`，有版本的“无法判断”写“已装”；有非用户级安装时句末加 `other_scopes`；`{versions}` 是去重后的“vX、vY”，`{missing}` 是“a、b”。
- 耗时：总耗时是第一条到最后一条事件的间隔，不足 1 小时写“Y 分”，否则写“X 小时 Y 分”；各阶段按规格中的顺序只列有完成记录的阶段（规格外的阶段名按字母顺序排在后面，原样显示），一个都没有时省略冒号及其后内容；分钟四舍五入；等 CI、等本地资源没有记录写“0 分”；没有任何事件时整节只写“- 无记录”。
