"""壁纸设置引擎。

功能：
- 扫描壁纸文件夹下的图片
- 获取当前桌面壁纸路径
- 设为桌面壁纸（SystemParametersInfo SPI_SETDESKWALLPAPER，填充模式）
- 设为锁屏壁纸（注册表 PersonalizationCSP，Win10/11）
"""
from __future__ import annotations

import ctypes
import os
import winreg
from typing import Callable

from core import paths

SUPPORTED_EXT = (".jpg", ".jpeg", ".png", ".bmp")


def list_wallpapers() -> list[str]:
    """扫描壁纸文件夹，返回所有支持的图片绝对路径。"""
    if not os.path.isdir(paths.WALLPAPER_DIR):
        return []
    out: list[str] = []
    for fn in os.listdir(paths.WALLPAPER_DIR):
        if fn.lower().endswith(SUPPORTED_EXT):
            out.append(os.path.join(paths.WALLPAPER_DIR, fn))
    out.sort()
    return out


def get_current_wallpaper() -> str:
    """读取当前桌面壁纸路径。"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop", 0, winreg.KEY_READ,
        ) as k:
            val, _ = winreg.QueryValueEx(k, "WallPaper")
            return val or ""
    except Exception:
        return ""


def set_desktop_wallpaper(image_path: str) -> bool:
    """设为桌面壁纸，样式为填充（FIT）。"""
    if not os.path.exists(image_path):
        return False
    SPI_SETDESKWALLPAPER = 20
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02

    # 先设置壁纸样式为"填充"(10=FIT)
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop",
            0, winreg.KEY_WRITE,
        ) as k:
            winreg.SetValueEx(k, "WallpaperStyle", 0, winreg.REG_SZ, "10")
            winreg.SetValueEx(k, "TileWallpaper", 0, winreg.REG_SZ, "0")
    except Exception:
        pass

    # 转为绝对路径并调用 SystemParametersInfo
    path = os.path.abspath(image_path)
    try:
        user32 = ctypes.windll.user32
        result = user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, path,
            SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
        )
        return bool(result)
    except Exception:
        return False


def set_lockscreen_wallpaper(image_path: str) -> bool:
    """设为锁屏壁纸（Win10/11，通过 PersonalizationCSP）。"""
    if not os.path.exists(image_path):
        return False
    path = os.path.abspath(image_path)
    key_path = r"Software\Microsoft\Windows\CurrentVersion\PersonalizationCSP"
    try:
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path,
            0, winreg.KEY_WRITE,
        ) as k:
            winreg.SetValueEx(k, "LockScreenImagePath", 0, winreg.REG_SZ, path)
            winreg.SetValueEx(k, "LockScreenStatus", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(k, "LockScreenImageUrl", 0, winreg.REG_SZ, path)
            winreg.SetValueEx(k, "LockScreenImageStatus", 0, winreg.REG_DWORD, 1)
        return True
    except Exception:
        return False
