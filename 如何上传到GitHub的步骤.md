# 手动上传到 GitHub 的步骤

由于网络问题无法直接 push，请按以下步骤手动上传：

## 方法 1：直接在 GitHub 网页上传文件（推荐）

1. 打开你的仓库：https://github.com/kelin3296-jpg/Claudecode.sudo-skill

2. 点击 "Add file" -> "Upload files"

3. 依次上传以下 3 个文件：
   - `SKILL.md`
   - `README.md`
   - `check_sudo_hook.py`

4. 在 "Commit changes" 处填写：
   - 标题：`feat: 添加智能 hook 和 / 命令提示支持`
   - 描述：
     ```
     - 更新 SKILL.md，添加所有子命令到 description，让 / 能显示完整 sudo 命令
     - 新增 check_sudo_hook.py，当 /sudo 激活时自动放行权限
     - 更新 README.md，添加 Windows 兼容性说明和 hook 配置文档
     ```

5. 点击 "Commit changes"

## 方法 2：使用 GitHub Desktop

如果你安装了 GitHub Desktop：

1. 用 GitHub Desktop 克隆仓库
2. 把这 3 个文件复制进去
3. Commit 并 Push

## 方法 3：在其他网络环境 push

如果你有其他能访问 GitHub 的网络环境：

1. 把整个 `C:\Users\谢洛\.claude\skills\sudo` 目录复制过去
2. 在那个环境下运行 `git push`
