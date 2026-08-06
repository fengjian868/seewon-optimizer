"""全局路径与常量定义。

打包为单 exe 后，运行时目录以 exe 所在位置为基准
（PyInstaller --onefile 下 sys.frozen 为 True，用 sys.executable 取 exe 路径）。
"""
from __future__ import annotations

import os
import sys

# ---- 运行时基目录 ----
if getattr(sys, "frozen", False):
    # PyInstaller 打包后：exe 所在目录
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # 开发环境：项目根目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _base(*parts: str) -> str:
    return os.path.join(BASE_DIR, *parts)


# 用户资源文件夹（exe 同级）
SOFTWARE_DIR = _base("常用软件")
TEACHING_DIR = _base("教学工具")
WALLPAPER_DIR = _base("壁纸")

# 运行时生成的备份目录
BACKUP_DIR = _base("backup")

# 打包内资源目录（assets 在打包时随 exe 一起内嵌）
if getattr(sys, "frozen", False):
    ASSETS_DIR = os.path.join(sys._MEIPASS, "assets")  # type: ignore[attr-defined]
else:
    ASSETS_DIR = _base("assets")

SOFTWARE_META = os.path.join(ASSETS_DIR, "software.json")
TEACHING_META = os.path.join(ASSETS_DIR, "teaching_tools.json")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")

# ---- 配色方案（希沃蓝白科技风）----
COLORS = {
    "primary": "#0061FF",      # 希沃蓝
    "primary_hover": "#0050D4",
    "bg": "#FFFFFF",           # 背景
    "card_bg": "#F5F7FA",      # 卡片底色
    "card_hover": "#E8EEF7",
    "text": "#333333",         # 主文字
    "text_sub": "#666666",     # 次要文字
    "success": "#52C41A",
    "warning": "#FAAD14",
    "error": "#F5222D",
    "border": "#E5E7EB",
}

APP_NAME = "希沃一体机优化工具"
APP_VERSION = "1.0.0"


def ensure_runtime_dirs() -> None:
    """启动时确保运行时目录存在。"""
    for d in (BACKUP_DIR, SOFTWARE_DIR, TEACHING_DIR, WALLPAPER_DIR):
        os.makedirs(d, exist_ok=True)
