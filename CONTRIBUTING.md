# 参与贡献 sudo-skill

感谢你愿意参与这个项目。这个仓库刻意保持精简：它主要包含一个 Claude Code skill、一个薄 CLI 封装，以及围绕备份、diff、审计日志和安全回滚的核心逻辑。

## 适合的贡献方向

- 强化 rollback 的安全校验
- 补文档和示例
- 为边界场景补测试
- 改进 release 或仓库自动化
- 优化 issue / PR 的协作体验

## 本地开发

```bash
python3 -m venv .venv
./.venv/bin/pip install pytest
./.venv/bin/python -m pytest
python3 scripts/build_release.py
```

如果你想预览 release notes：

```bash
python3 scripts/build_release_notes.py v0.1.4-preview
```

## 项目边界

除非维护者明确决定调整，否则请尽量保持这些约束：

- 运行时目标仅限 **Claude Code**
- `/sudo` 是**显式工作流**，不是隐式绕过沙箱
- rollback 宁可拒绝不安全的 destructive 操作，也不要强行成功
- `operation_logger.py` 保持内部实现，对外命令统一走 `sudo.py`
- release zip 应继续保持干净、可安装

## 提交 PR 前建议

- 改动尽量聚焦，并说明对用户的实际影响
- 行为有变化时补测试或更新测试
- 命令、流程或安全承诺变动时同步改文档
- 运行 `./.venv/bin/python -m pytest`
- 如果改了打包逻辑，补跑 `python3 scripts/build_release.py`

## PR 描述建议包含

- 这次改动解决了什么问题
- 哪些安全行为或交互发生了变化
- 你跑了哪些测试
- 是否更新了文档或 release notes
- 是否还有后续工作适合拆到下一次 PR

## 协作风格

保持友好、具体、务实。相比“大而全”的混合改动，这个项目更欢迎小而清晰、便于 review 的 PR。
