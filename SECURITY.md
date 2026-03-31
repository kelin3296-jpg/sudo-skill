# 安全策略

这个仓库提供的是一个 Claude Code skill，以及围绕备份、diff、审计日志和安全回滚的辅助能力。因为项目涉及敏感文件操作流程，发现安全问题时请尽量避免直接公开完整利用细节。

## 支持版本

| 版本 | 是否支持 |
| --- | --- |
| 0.1.x | 是 |
| < 0.1.0 | 否 |

当前默认支持最新的 `0.1.x` 版本线。

## 如何反馈安全问题

请 **不要** 直接提交带完整利用细节的公开 issue。

建议按下面顺序处理：

1. 如果仓库启用了 GitHub 私密漏洞反馈或 Security Advisory，优先走私密通道。
2. 如果暂时没有私密通道，请先提一个不含利用细节的最小 issue，请维护者提供私下沟通方式。
3. 只提供安全复现所需的最小信息，例如影响版本、平台、影响范围和高层步骤。

建议补充的信息：

- 受影响的文件或命令路径
- 是否影响备份、diff、日志或 rollback
- 是否可能导致误删、误覆盖或数据泄露
- 能安全提供的最小复现

## 维护者会重点关注的范围

- destructive rollback 行为
- 回滚前的对象身份校验
- 备份存储和恢复路径
- 容易被误读成“自动提权”的命令流程

## English note

This repository is Chinese-first for now. If you need to report a security issue in English, please open a minimal private report request and the maintainer can continue from there.
