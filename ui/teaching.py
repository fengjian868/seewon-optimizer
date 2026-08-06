"""教学工具安装子页面。

支持安装包静默安装和压缩包解压到 D 盘两种部署方式。
"""
from __future__ import annotations

from core import paths
from ui.install_view_base import InstallViewBase


class TeachingView(InstallViewBase):
    local_dir = paths.TEACHING_DIR
    meta_path = paths.TEACHING_META

    def __init__(self, master, back_command, **kw):
        super().__init__(
            master, back_command,
            title="教学工具安装",
            desc="安装包静默安装；或压缩包解压到 D:\\教学工具\\ 并创建开始菜单快捷方式。",
        )
