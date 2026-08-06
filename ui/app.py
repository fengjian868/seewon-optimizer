"""App 主容器：管理首页与各子页面之间的切换。"""
from __future__ import annotations

import tkinter as tk

from core import paths
from ui.widgets import HomeCard, StatusBar


class App(tk.Frame):
    """页面路由容器。通过 show(name) 切换页面，复用同一 root。"""

    def __init__(self, master, **kw):
        kw.setdefault("bg", paths.COLORS["bg"])
        super().__init__(master, **kw)

        self._current: tk.Frame | None = None
        self.show("home")

    def show(self, name: str) -> None:
        if self._current is not None:
            self._current.destroy()
            self._current = None

        if name == "home":
            self._current = HomeView(self, navigate=self.show)
        elif name == "optimize":
            from ui.optimize import OptimizeView
            self._current = OptimizeView(self, back_command=lambda: self.show("home"))
        elif name == "restore":
            from ui.restore import RestoreView
            self._current = RestoreView(self, back_command=lambda: self.show("home"))
        elif name == "software":
            from ui.software import SoftwareView
            self._current = SoftwareView(self, back_command=lambda: self.show("home"))
        elif name == "teaching":
            from ui.teaching import TeachingView
            self._current = TeachingView(self, back_command=lambda: self.show("home"))
        elif name == "wallpaper":
            from ui.wallpaper import WallpaperView
            self._current = WallpaperView(self, back_command=lambda: self.show("home"))
        else:
            raise ValueError(f"未知页面: {name}")

        self._current.pack(fill="both", expand=True)


class HomeView(tk.Frame):
    """首页：标题栏 + 5 个功能卡片。"""

    CARDS = [
        ("🚀", "一键优化系统", "清理临时文件/启动项/服务，释放内存，关闭贴靠布局", "optimize"),
        ("↩️", "一键还原系统", "精确回滚本次优化，或回滚系统还原点", "restore"),
        ("📦", "常用软件安装", "常用软件离线包优先、缺失在线下载，静默安装", "software"),
        ("🎓", "教学工具安装", "教学工具安装或压缩包解压部署到 D 盘", "teaching"),
        ("🖼️", "希沃壁纸更换", "从壁纸文件夹列表选择并设为桌面/锁屏壁纸", "wallpaper"),
    ]

    def __init__(self, master, navigate, **kw):
        kw.setdefault("bg", paths.COLORS["bg"])
        super().__init__(master, **kw)

        # 顶部标题栏
        header = tk.Frame(self, bg=paths.COLORS["bg"])
        header.pack(fill="x", padx=24, pady=(22, 10))

        tk.Label(
            header, text=paths.APP_NAME, bg=paths.COLORS["bg"],
            font=("Microsoft YaHei UI", 20, "bold"), fg=paths.COLORS["primary"],
        ).pack(side="left")

        tk.Label(
            header, text=f"v{paths.APP_VERSION}", bg=paths.COLORS["bg"],
            font=("Microsoft YaHei UI", 10), fg=paths.COLORS["text_sub"],
        ).pack(side="left", padx=(8, 0), pady=(6, 0))

        # 卡片网格容器
        grid = tk.Frame(self, bg=paths.COLORS["bg"])
        grid.pack(fill="both", expand=True, padx=24, pady=10)

        cols = 3
        for i, (icon, title, desc, key) in enumerate(self.CARDS):
            r, c = divmod(i, cols)
            card = HomeCard(grid, icon, title, desc, command=lambda k=key: navigate(k))
            card.grid(row=r, column=c, padx=12, pady=12, sticky="nsew")
            grid.grid_columnconfigure(c, weight=1, uniform="card")
        grid.grid_rowconfigure(0, weight=1)
        if len(self.CARDS) > cols:
            grid.grid_rowconfigure(1, weight=1)

        # 状态栏
        StatusBar(self).pack(side="bottom", fill="x")
