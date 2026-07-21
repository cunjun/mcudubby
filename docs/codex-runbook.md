# Codex 运行文档

本文记录 Codex 在本仓库中执行开发、验证和提交时应遵守的约定。

## 提交信息格式

提交信息必须使用中文，并采用多行说明格式：

```text
1、用一句话说明本次提交的目标。

- 说明第一个主要变化。
- 说明第二个主要变化。
- 说明验证、文档或迁移信息。
```

要求：

- 第一行使用中文编号开头，例如 `1、`，描述本次提交带来的价值。
- 空一行后使用 `-` 列出核心改动，不使用英文模板或空泛描述。
- 需要让 GitHub 提交列表和本地 `git log` 中能直接看懂本次提交做了什么。
- 不使用 `Merge branch ...` 作为面向用户的提交说明；需要合并提交时，也要改成中文说明。

示例：

```text
1、发布整合后的 McuBuddy 0.5.1。

- 将 Python 包、发布说明和 MCP Registry 元数据统一升级至 0.5.1。
- 补充 McuBuddy 命名统一、PyPI 所有权及 Registry 配置的变更记录。
- 更新 Registry 元数据测试并验证发布制品。
```

## 提交前检查

提交前优先运行：

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests scripts skills\mcubug\scripts
```

如果本地环境缺少依赖，先安装开发依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## GitHub 贡献图

提交需要满足 GitHub 的贡献统计条件：

- 提交必须在仓库默认分支或 `gh-pages` 分支上。
- 提交作者邮箱必须绑定并验证到 GitHub 账号。
- 推送到 GitHub 后贡献图可能需要等待一段时间刷新。
