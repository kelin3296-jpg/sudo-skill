# 支持说明

感谢使用 `sudo-skill`。

这个仓库目前是一个精简的开源项目，支持主要是 best-effort。通常最快的处理方式取决于问题类型。

## 问题应该发到哪里

- **Bug / 回归问题**：提交 GitHub bug report
- **功能建议**：提交 GitHub feature request
- **使用问题**：提交一个 GitHub issue，并在标题前加 `[Support]`
- **安全问题**：按 [`SECURITY.md`](SECURITY.md) 处理，不要公开完整利用细节

## 提问前建议附上

- sudo-skill 版本或 release tag
- Python 版本
- 操作系统与 shell
- 实际运行的 `python sudo.py ...` 命令
- 预期行为与实际行为
- 相关 stdout、stderr、diff 输出或截图

## 当前支持范围

当前支持范围主要包括：

- **Claude Code** 运行时
- 文档中定义的 `/sudo` 显式工作流
- GitHub Releases 发布的安装包

当前 **不提供一线支持** 的范围包括：

- OpenClaw、Codex CLI 或其他运行时
- 隐式绕过沙箱或隐藏提权能力
- 文档范围之外的环境定制操作

## 英文补充

This repository is Chinese-first for now. English support is still possible, but the fastest responses will usually come through the standard issue templates with a focused reproduction.
