# Changelog

## v0.3.0 (2026-04-01)

### 新功能
- 添加 `auto-log` 命令，可查看自动确认后台进程的活动日志
- auto-confirm 后台进程现在支持 VSCode、Visual Studio Code、VSCodium 等多种编辑器
- auto-confirm 支持中文"允许"按钮识别
- auto-confirm 日志带时间戳和点击次数计数

### 改进
- auto-confirm 启动时清空旧日志，避免日志累积
- auto-confirm 启动和停止时显示日志文件路径
- 日志同时输出到文件和 stdout
- 增加 AppleScript 超时时间从 2 秒到 5 秒

## v0.2.1 (2026-04-01)

### 改进
- 添加 README.md 和 CHANGELOG.md 发布文档

## v0.2.0 (2026-04-01)

### 改进
- 修复 psutil 依赖问题，改为可选导入
- 添加缺失的 subprocess 和 sys 导入
- 改进错误处理逻辑

## v0.1.0 (2026-03-xx)

### 初始发布
- 基础 sudo 工作流功能
- 文件修改、删除、创建、移动的日志记录
- 备份与回滚机制
- Diff 查看功能
- GitHub Actions CI/CD
