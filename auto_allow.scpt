#!/usr/bin/env osascript
(*
Claude Code Auto-Allow Daemon
在 sudo 模式下自动点击 "Allow" 按钮
*)

property isRunning : false
property allowCount : 0

-- 主循环
on run
	set isRunning to true
	display notification "Auto-Allow daemon started" with title "Sudo Mode"

	repeat while isRunning
		try
			set clickedButton to clickAllowButton()
			if clickedButton then
				set allowCount to allowCount + 1
				display notification "Auto-clicked Allow (#" & allowCount & ")" with title "Sudo Mode"
			end if
		on error errMsg
			-- 静默失败，继续循环
		end try

		-- 每 500ms 检查一次
		delay 0.5
	end repeat
end run

-- 点击 Allow 按钮
on clickAllowButton()
	tell application "System Events"
		-- 查找 Claude Code 进程
		if not (exists process "Claude Code") then
			return false
		end if

		tell process "Claude Code"
			-- 查找包含 "Allow" 的按钮
			try
				set allowButton to first button of window 1 whose name contains "Allow" or title contains "Allow"
				click allowButton
				return true
			on error
				-- 尝试查找 "Allow this bash command?" 对话框
				try
					set dialogWindow to first window whose name contains "Allow" or description contains "Allow"
					set allowButton to first button of dialogWindow whose name contains "Allow" or title contains "Allow"
					click allowButton
					return true
				on error
					return false
				end try
			end try
		end tell
	end tell
end clickAllowButton

-- 停止脚本
on quit
	set isRunning to false
	display notification "Auto-Allow daemon stopped" with title "Sudo Mode"
	continue quit
end quit
