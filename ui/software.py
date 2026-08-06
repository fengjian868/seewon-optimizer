"""常用软件安装子页面。"""
from __future__ import annotations

from core import paths
from ui.install_view_base import InstallViewBase


class SoftwareView(InstallViewBase):
    local_dir = paths.SOFTWARE_DIR
    meta_path = paths.SOFTWARE_META

    def __init__(self, master, back_command, **kw):
        super().__init__(
            master, back_command,
            title="常用软件安装",
            desc="优先使用『常用软件』文件夹的离线包，缺失则在线下载，静默安装。",
        )
