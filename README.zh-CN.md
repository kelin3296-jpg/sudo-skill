# sudo-skill

[![CI](https://github.com/kelin3296-jpg/sudo-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/kelin3296-jpg/sudo-skill/actions/workflows/ci.yml)
![Claude Code](https://img.shields.io/badge/runtime-Claude%20Code-5b5bd6)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![License](https://img.shields.io/badge/license-MIT-green)

给 Claude Code 用的更稳妥 `/sudo` 工作流：先备份、再修改；先看 diff、再回滚；对象不一致时拒绝 destructive rollback。

英文说明见 [`README.md`](README.md).

## 这个项目为什么存在

很多 Claude Code 使用场景确实需要 `/sudo` 这种心智模型，但“自动提权模式”既容易误导，也不安全。`sudo-skill` 的目标是保留熟悉的命令入口，同时把能力边界讲清楚：

- 进入显式特权工作流，而不是伪装成自动绕过沙箱
- 在改文件前留备份
- 在回滚前先看文本 diff
- 如果当前对象已经变了，就拒绝 destructive rollback
- 保留回滚后依然读得懂的审计记录

## 一眼看懂

- **运行环境**：仅支持 Claude Code
- **能力边界**：显式特权工作流，不自动修改宿主沙箱
- **核心能力**：备份、审计日志、unified diff、安全回滚、可发布 zip
- **默认存储**：写入 `~/.claude`，也支持 `SUDO_SKILL_HOME` 做隔离环境

## 快速开始

```bash
python sudo.py enter
python sudo.py log-modify ~/.ssh/config
# 编辑文件
python sudo.py finalize-modify ~/.ssh/config
python sudo.py diff ~/.ssh/config
python sudo.py rollback 1 --yes
python sudo.py exit
```

## 安装示例

从本地工作目录安装：

```bash
mkdir -p ~/.claude/skills
cp -R ./sudo-skill ~/.claude/skills/sudo
```

从 release zip 安装：

```bash
mkdir -p ~/.claude/skills
unzip dist/sudo-skill.zip -d /tmp/sudo-skill-release
rm -rf ~/.claude/skills/sudo
mv /tmp/sudo-skill-release/sudo-skill ~/.claude/skills/sudo
```

## 面向用户的公开命令

```bash
python sudo.py enter
python sudo.py exit
python sudo.py status
python sudo.py clean --days 7
python sudo.py purge --yes
python sudo.py history 20
python sudo.py rollback 1 --yes
python sudo.py diff [路径|历史序号]
```

## 供 skill / 集成层使用的记录命令

为了保持 `operation_logger.py` 是内部模块，对外只暴露 `sudo.py`：

```bash
python sudo.py log-modify <path>
python sudo.py finalize-modify <path> [--id OP_ID]
python sudo.py log-delete <path>
python sudo.py log-create <path>
python sudo.py log-move <src> <dst>
python sudo.py log-chmod <path> <旧权限八进制> <新权限八进制>
```

## 默认存储位置

默认写到 `~/.claude`：

- `~/.claude/sudo-backups/`
- `~/.claude/sudo-logs/`
- `~/.claude/sudo-state.json`

开发、测试或自定义安装时，可通过 `SUDO_SKILL_HOME` 覆盖。

## 风险说明

- 这个 skill **不会自动修改 Claude Code 的 bash 参数**。
- 如果当前文件对象与记录时不一致，回滚会拒绝执行 destructive 操作。
- 删除回滚不会覆盖后来占用了原路径的新文件。
- 创建回滚不会删除创建后又被改过的文件。

## 终端演示流程

```text
$ python sudo.py enter
Entered /sudo explicit privileged workflow.

$ python sudo.py log-modify ~/.ssh/config
Recorded modify operation #1 for /Users/you/.ssh/config

$ python sudo.py finalize-modify ~/.ssh/config
Finalized modify operation #1 for /Users/you/.ssh/config

$ python sudo.py diff ~/.ssh/config
--- before:/Users/you/.ssh/config
+++ current:/Users/you/.ssh/config
@@ ...

$ python sudo.py rollback 1 --yes
Rolled back modify: /Users/you/.ssh/config

$ python sudo.py exit
Exited /sudo workflow.
```

## 开发与发布

```bash
python3 -m venv .venv
./.venv/bin/pip install pytest
./.venv/bin/python -m pytest
python3 scripts/build_release.py
```

发布脚本会生成 `dist/sudo-skill.zip`，并自动排除 `__MACOSX`、测试文件和缓存目录。

推送 `v0.1.0` 这类 tag 时，`.github/workflows/release.yml` 会自动跑测试、构建 zip，并发布结构化的 GitHub Release 说明。

如果你最终把仓库发布到别的 GitHub 用户名或仓库名下，记得同步更新本文件顶部的 badge 链接。
