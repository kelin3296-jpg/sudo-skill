# 更新日志

这里记录这个项目的关键版本变更，采用轻量化的语义化版本方式维护。

## [0.1.4] - 2026-03-31

### 新增

- 中文主文档 `README.md`，并新增英文辅文档 `README.en.md`
- 正式的安装提示词，用户可以直接复制发给 Claude Code 安装 `sudo-skill`
- 中文版 GitHub Social preview 图资源 `docs/social-preview.svg` 和 `docs/social-preview.png`

### 调整

- 仓库首页改成中文优先，围绕“背景、痛点、能解决什么、兜底方案”重写说明
- `SKILL.md` 改成中文优先，明确说明日志、备份、diff 与回滚如何降低特权模式带来的后顾之忧
- release zip 现在会一起包含 `README.en.md`、`CHANGELOG.md`、`SECURITY.md`、`SUPPORT.md`
- Release notes 改成中文优先生成

## [0.1.3] - 2026-03-31

### 新增

- 正式 `CHANGELOG.md`
- GitHub 社交预览图素材 `docs/social-preview.svg` 和 `docs/social-preview.png`
- 中英双语的 Claude Code 安装提示词

### 调整

- README 增强了背景、痛点和情绪成本的表达
- 强化了“日志 + 备份 + 回滚”作为兜底路径的说明
- `SKILL.md` 开始强调 `/sudo` 到底承诺了什么，不承诺什么

## [0.1.2] - 2026-03-31

### 新增

- `SECURITY.md`，说明安全问题反馈方式和范围
- `SUPPORT.md`，说明使用支持范围和提问方式

### 调整

- README 增加安全与支持文档入口

## [0.1.1] - 2026-03-31

### 新增

- `CONTRIBUTING.md`、issue 模板、PR 模板等协作资产
- `scripts/build_release_notes.py` 结构化 release notes 生成逻辑
- 仓库演示图 `docs/demo-terminal.svg`

### 调整

- 首页文案和 release workflow 做了第一次整理

## [0.1.0] - 2026-03-31

### 新增

- `sudo-skill` 首个开源版本
- 显式特权工作流 CLI，包含备份、diff、审计日志和安全回滚
- clean release zip、CI workflow 和自动 GitHub Release
