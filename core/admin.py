"""管理员权限检测与 UAC 提权。

本工具所有系统级操作都需管理员权限。设计为：启动即申请 UAC 提权
（通过 manifest 嵌入 requireAdministrator，打包后由 Windows 自动弹 UAC）。
此处提供运行时检测，供界面状态栏显示及防御性检查使用。
"""
from __future__ import annotations

import ctypes


def is_admin() -> bool:
    """返回当前进程是否拥有管理员权限。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except AttributeError:
        # 非 Windows 平台（开发/测试环境）
        return False


def relaunch_as_admin() -> None:
    """以管理员身份重新启动自身（弹 UAC）。

    仅在 manifest 未生效或被绕过时作为兜底；
    若用户拒绝 UAC，则进程直接退出。
    """
    import sys

    params = " ".join(f'"{a}"' for a in sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    # ShellExecuteW 返回值 <= 32 表示失败
    if rc <= 32:
        raise PermissionError("用户拒绝了 UAC 提权请求，无法以管理员身份运行。")
