# Learn from Vibe Coding
## 当你vibecoding时，你在coding什么。

AI 帮你写完代码后，花几分钟弄懂它。`learn` 是一个用于 Codex 和 Claude Code 的轻量 Skill：从当前编程会话、Git 改动、指定代码或技术主题中提炼值得理解的机制，用代码证据讲解，逐题检查理解，并在项目内留下少量可复习的错题和知识点。

它依附于你正在使用的 Coding Agent，无需单独部署模型服务、数据库或 WebUI。

## 一次学习是什么样的

下面是示意对话。示例路径和代码仅用于说明交互方式：

```text
你：$learn diff
Agent：这次认证改动增加了管理员角色检查（src/auth.py:42）。
       活跃的非管理员用户也会被拒绝。
Agent：如果用户 active=true、role="user"，现在能通过认证吗？为什么？
你：能，因为用户是活跃的。
Agent：不能。当前条件还要求 role="admin"（src/auth.py:42）。
       我已将这道错题保存到 .learning/notes.md。

过几天：$learn review
Agent：先复习上次的认证条件。若 role="user"，active=true 会改变结果吗？
```

学习流程保持简短：**定位材料 → 核对代码 → 讲解 2–3 个要点 → 一次问一道题 → 保存必要的错题与知识点**。项目事实会附当前 `file:line`；通用知识会与项目事实区分。回答错了才会记录对应缺口；未回答的题不会被保存。

## 如何使用

在项目目录中启动 Codex 或 Claude Code，明确选择学习来源：

| 目标 | Codex | Claude Code |
| --- | --- | --- |
| 学习刚完成的编程工作 | `$learn session` | `/learn session` |
| 学习当前暂存、未暂存及相关新文件的改动 | `$learn diff` | `/learn diff` |
| 理解指定文件或目录 | `$learn file src/auth.py` | `/learn file src/auth.py` |
| 学习技术主题，优先结合项目代码 | `$learn topic Redis TTL` | `/learn topic Redis TTL` |
| 复习项目内的错题和知识点 | `$learn review` | `/learn review` |

默认是**先简短讲解，再逐题测验**，每轮动态出 1–3 题、一次只问一道。你也可以加上“只讲解”或“先测验”。

`session` 用对话确定本轮工作，再核对当前代码；`diff` 以当前工作区为范围，不会擅自改看上一提交；`file` 只追查相关调用处和测试；`topic` 在项目没有实例时会明确按通用知识讲解。`review` 优先选择未掌握的错题，判题前会检查旧代码证据是否仍然有效。

## 如何退出

学习中直接回复“结束学习”“退出学习”或“stop”，即可结束本轮问答；也可以直接提出新的无关任务。尚未回答的题目不会被判分或记为错题。`learn` 不是常驻模式，无需退出 Codex 或 Claude Code。

## 安装

Skill 的完整目录是 [`skills/learn`](skills/learn)。复制**整个目录**，保留 `SKILL.md`、`references/` 和 `scripts/`：

```sh
git clone https://github.com/DerrickJc/learn-from-vibecoding.git
cd learn-from-vibecoding

# 安装到 Codex 项目
mkdir -p /path/to/project/.agents/skills/learn
cp -R skills/learn/. /path/to/project/.agents/skills/learn/

# 或安装到 Claude Code 项目
mkdir -p /path/to/project/.claude/skills/learn
cp -R skills/learn/. /path/to/project/.claude/skills/learn/
```

如果两个客户端都用，就复制到两个位置。路径 `/path/to/project` 请替换为你的项目目录；安装后在该项目中启动客户端。当前仓库已经通过 `.agents/skills/learn` 和 `.claude/skills/learn` 指向同一份 Skill，可直接试用。

大 Diff 和 Review 的取材脚本只依赖 Python 3 标准库；没有 Python 3 时，Skill 会按路径或条目进行受限读取。学习记录保存在项目的 `.learning/notes.md`，首次保存时会将 `.learning/` 加入该项目的 `.gitignore`。Skill 只在调用时运行，没有后台服务或定时任务。

## 轻量化边界

- 主入口 [SKILL.md](skills/learn/SKILL.md) 保持简短；Diff 和 Review 的细则按需读取。
- 大 Diff 先列变更路径与统计，再最多展开 3 个代表文件；`diff-bundle` 和 `diff-read` 的单次输出最多 12,000 字符。需要核对摘要外文件时再按路径读取。
- Review 先给最多 3 个候选标题，再读取选中的单条笔记，不把整个知识库交给模型。
- 错题和概念写入 Markdown；无需独立模型 Provider、数据库、WebUI、MCP Server 或第三方 Python 包。

这些限制控制**进入模型的项目材料**。整轮 token 还受 Agent 自身上下文、模型推理、缓存和工具重试影响，因此不保证比普通对话的总 token 更少。

更完整的流程、记录格式和验收边界见 [v0.1 规格](SPEC.md)。
