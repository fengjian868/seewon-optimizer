"""UI 通用组件：按钮、卡片、子页面基类、状态栏等。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from core import paths


class PrimaryButton(tk.Button):
    """希沃蓝主按钮。"""

    def __init__(self, master, text: str, command: Callable | None = None, **kw):
        kw.setdefault("bg", paths.COLORS["primary"])
        kw.setdefault("fg", "#FFFFFF")
        kw.setdefault("activebackground", paths.COLORS["primary_hover"])
        kw.setdefault("activeforeground", "#FFFFFF")
        kw.setdefault("relief", "flat")
        kw.setdefault("cursor", "hand2")
        kw.setdefault("font", ("Microsoft YaHei UI", 11, "bold"))
        kw.setdefault("padx", 18)
        kw.setdefault("pady", 8)
        super().__init__(master, text=text, command=command, **kw)


class HomeCard(tk.Frame):
    """首页功能卡片。"""

    def __init__(self, master, icon: str, title: str, desc: str,
                 command: Callable, **kw):
        super().__init__(master, **kw)
        self.configure(bg=paths.COLORS["card_bg"], bd=0)
        self._command = command

        # 图标（用 emoji 文本，免外部图片依赖）
        self._icon = tk.Label(
            self, text=icon, bg=paths.COLORS["card_bg"],
            font=("Segoe UI Emoji", 28), fg=paths.COLORS["primary"],
        )
        self._icon.pack(pady=(18, 4))

        self._title = tk.Label(
            self, text=title, bg=paths.COLORS["card_bg"],
            font=("Microsoft YaHei UI", 13, "bold"),
            fg=paths.COLORS["text"],
        )
        self._title.pack(pady=(0, 4))

        self._desc = tk.Label(
            self, text=desc, bg=paths.COLORS["card_bg"],
            font=("Microsoft YaHei UI", 9),
            fg=paths.COLORS["text_sub"], wraplength=180, justify="center",
        )
        self._desc.pack(pady=(0, 14), padx=10)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        for w in (self._icon, self._title, self._desc):
            w.bind("<Button-1>", self._on_click)

    def _on_enter(self, _e):
        self.configure(bg=paths.COLORS["card_hover"])
        for w in (self._icon, self._title, self._desc):
            w.configure(bg=paths.COLORS["card_hover"])

    def _on_leave(self, _e):
        self.configure(bg=paths.COLORS["card_bg"])
        for w in (self._icon, self._title, self._desc):
            w.configure(bg=paths.COLORS["card_bg"])

    def _on_click(self, _e):
        self._command()


class StatusBar(tk.Frame):
    """底部状态栏：显示管理员权限、备份目录等。"""

    def __init__(self, master, **kw):
        kw.setdefault("bg", paths.COLORS["card_bg"])
        kw.setdefault("height", 26)
        super().__init__(master, **kw)
        self.pack_propagate(False)

        from core.admin import is_admin

        admin_text = "管理员: 已授权" if is_admin() else "管理员: 未授权"
        admin_fg = paths.COLORS["success"] if is_admin() else paths.COLORS["error"]
        self._admin = tk.Label(
            self, text=admin_text, bg=paths.COLORS["card_bg"],
            fg=admin_fg, font=("Microsoft YaHei UI", 9),
        )
        self._admin.pack(side="left", padx=12)

        self._path = tk.Label(
            self, text=f"备份目录: {paths.BACKUP_DIR}",
            bg=paths.COLORS["card_bg"], fg=paths.COLORS["text_sub"],
            font=("Microsoft YaHei UI", 9),
        )
        self._path.pack(side="right", padx=12)


class SubPage(tk.Frame):
    """子页面基类：返回按钮 + 标题 + 说明 + 主操作区 + 状态栏。

    子类调用 set_body() 填充主操作区。
    """

    def __init__(self, master, title: str, desc: str,
                 back_command: Callable, **kw):
        kw.setdefault("bg", paths.COLORS["bg"])
        super().__init__(master, **kw)

        # 顶部栏
        top = tk.Frame(self, bg=paths.COLORS["bg"])
        top.pack(fill="x", padx=20, pady=(14, 4))

        back = tk.Button(
            top, text="← 返回", bg=paths.COLORS["bg"], fg=paths.COLORS["primary"],
            relief="flat", cursor="hand2", activebackground=paths.COLORS["bg"],
            activeforeground=paths.COLORS["primary_hover"],
            font=("Microsoft YaHei UI", 11, "bold"), command=back_command,
        )
        back.pack(side="left")

        title_lbl = tk.Label(
            top, text=title, bg=paths.COLORS["bg"],
            font=("Microsoft YaHei UI", 16, "bold"), fg=paths.COLORS["text"],
        )
        title_lbl.pack(side="left", padx=16)

        desc_lbl = tk.Label(
            self, text=desc, bg=paths.COLORS["bg"], anchor="w",
            font=("Microsoft YaHei UI", 10), fg=paths.COLORS["text_sub"],
        )
        desc_lbl.pack(fill="x", padx=20, pady=(0, 8))

        # 分割线
        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", padx=20)

        # 主操作区占位
        self._body = tk.Frame(self, bg=paths.COLORS["bg"])
        self._body.pack(fill="both", expand=True, padx=20, pady=10)

        # 状态栏
        self._status = StatusBar(self)
        self._status.pack(side="bottom", fill="x")

    def body(self) -> tk.Frame:
        return self._body
