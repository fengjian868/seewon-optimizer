"""希沃一体机优化工具 - 程序入口。

启动流程：
1. 检测管理员权限；若未提权则尝试 relaunch_as_admin 弹 UAC
2. 确保运行时目录存在
3. 启动 tkinter 主窗口（首页）
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from core import paths
from core.admin import is_admin, relaunch_as_admin


def main() -> None:
    # 1. 权限检查
    if not is_admin():
        try:
            relaunch_as_admin()
        except PermissionError:
            # 用户拒绝 UAC：提示后退出
            try:
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    paths.APP_NAME,
                    "需要管理员权限才能运行本工具。\n请以管理员身份重新运行。",
                )
            except Exception:
                pass
        sys.exit(0)
        return

    # 2. 确保运行时目录
    paths.ensure_runtime_dirs()

    # 3. 启动主界面
    from ui.app import App

    root = tk.Tk()
    root.title(f"{paths.APP_NAME} v{paths.APP_VERSION}")
    root.geometry("1000x680")
    root.minsize(900, 600)
    root.configure(bg=paths.COLORS["bg"])

    App(root).pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
