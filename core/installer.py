"""安装/解压引擎。

支持两种部署方式：
- install：静默安装 .exe/.msi 安装包
- extract：解压 .zip/.7z/.rar 压缩包到目标目录并建快捷方式

混合模式：优先用本地离线包，缺失则按内置 URL 在线下载。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from typing import Callable

import winreg

LogCB = Callable[[str], None]
StatusCB = Callable[[str, str], None]  # (item_id, status_text)


@dataclass
class SoftwareMeta:
    id: str
    name: str
    version: str = ""
    deploy: str = "install"          # install | extract
    detect_reg: dict | None = None   # {"hive":..., "key":..., "name":...}
    detect_path: str | None = None   # exe/目录路径
    offline_file: str = ""           # 本地离线包文件名
    download_url: str = ""
    silent_args: str = ""            # 静默安装参数
    target_dir: str = ""             # extract 方式的目标目录
    main_exe: str = ""               # extract 方式解压后的主 exe（建快捷方式用）
    icon: str = "📦"

    @classmethod
    def from_dict(cls, d: dict) -> "SoftwareMeta":
        return cls(
            id=d["id"], name=d["name"], version=d.get("version", ""),
            deploy=d.get("deploy", "install"),
            detect_reg=d.get("detect_reg"), detect_path=d.get("detect_path"),
            offline_file=d.get("offline_file", ""),
            download_url=d.get("download_url", ""),
            silent_args=d.get("silent_args", ""),
            target_dir=d.get("target_dir", ""),
            main_exe=d.get("main_exe", ""),
            icon=d.get("icon", "📦"),
        )


@dataclass
class InstallResult:
    item_id: str
    success: bool
    message: str
    skipped: bool = False


_HIVE = {
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKU": winreg.HKEY_USERS,
    "HKCC": winreg.HKEY_CURRENT_CONFIG,
}


def load_meta(meta_path: str) -> list[SoftwareMeta]:
    """从 JSON 文件加载软件元数据列表。"""
    if not os.path.exists(meta_path):
        return []
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [SoftwareMeta.from_dict(item) for item in data]


def detect_installed(meta: SoftwareMeta) -> bool:
    """按检测规则判断是否已安装/部署。"""
    # 注册表检测
    if meta.detect_reg:
        try:
            hive = _HIVE[meta.detect_reg["hive"]]
            with winreg.OpenKey(
                hive, meta.detect_reg["key"], 0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as k:
                winreg.QueryValueEx(k, meta.detect_reg["name"])
                return True
        except FileNotFoundError:
            return False
        except Exception:
            return False
    # 路径检测
    if meta.detect_path:
        return os.path.exists(meta.detect_path)
    return False


class Installer:
    """安装/解压执行器。

    用法：
        inst = Installer(local_dir, meta_path)
        results = inst.install_batch(selected_ids, log_cb, status_cb)
    """

    def __init__(self, local_dir: str, meta_path: str):
        self.local_dir = local_dir
        self.metas: list[SoftwareMeta] = load_meta(meta_path)

    def get_meta(self, item_id: str) -> SoftwareMeta | None:
        for m in self.metas:
            if m.id == item_id:
                return m
        return None

    def install_batch(
        self, selected_ids: list[str],
        log: LogCB = lambda m: None,
        status: StatusCB = lambda i, s: None,
    ) -> list[InstallResult]:
        results: list[InstallResult] = []
        for sid in selected_ids:
            meta = self.get_meta(sid)
            if meta is None:
                results.append(InstallResult(sid, False, "元数据缺失"))
                continue
            results.append(self._install_one(meta, log, status))
        return results

    def _install_one(self, meta: SoftwareMeta,
                     log: LogCB, status: StatusCB) -> InstallResult:
        log(f"【{meta.name}】开始处理…")
        # 1. 检测是否已安装
        if detect_installed(meta):
            status(meta.id, "已安装")
            log(f"  已安装，跳过")
            return InstallResult(meta.id, True, "已安装", skipped=True)
        status(meta.id, "获取安装包…")

        # 2. 获取安装包
        pkg_path = self._resolve_package(meta, log, status)
        if not pkg_path:
            status(meta.id, "失败：无安装包")
            return InstallResult(meta.id, False, "无法获取安装包")

        # 3. 部署
        try:
            if meta.deploy == "extract":
                ok = self._extract(meta, pkg_path, log, status)
            else:
                ok = self._silent_install(meta, pkg_path, log, status)
        except Exception as e:
            log(f"  ✗ 出错：{e}")
            status(meta.id, f"失败：{e}")
            return InstallResult(meta.id, False, str(e))

        # 4. 验证
        if ok and detect_installed(meta):
            status(meta.id, "完成")
            log(f"  ✓ 安装成功")
            return InstallResult(meta.id, True, "安装成功")
        elif ok:
            # extract 方式可能无 detect 规则，按部署成功计
            status(meta.id, "完成")
            log(f"  ✓ 部署完成")
            return InstallResult(meta.id, True, "部署完成")
        status(meta.id, "失败")
        return InstallResult(meta.id, False, "安装后检测未通过")

    # ---- 获取安装包 ----
    def _resolve_package(self, meta: SoftwareMeta,
                         log: LogCB, status: StatusCB) -> str | None:
        # 优先本地离线包
        if meta.offline_file:
            local_path = os.path.join(self.local_dir, meta.offline_file)
            if os.path.exists(local_path):
                log(f"  使用本地离线包：{meta.offline_file}")
                return local_path
            # 本地按扩展名模糊匹配
            if os.path.isdir(self.local_dir):
                for fn in os.listdir(self.local_dir):
                    if fn.lower().startswith(meta.id.lower()):
                        log(f"  使用本地离线包：{fn}")
                        return os.path.join(self.local_dir, fn)
        # 在线下载
        if meta.download_url:
            status(meta.id, "下载中…")
            return self._download(meta, log, status)
        return None

    def _download(self, meta: SoftwareMeta,
                  log: LogCB, status: StatusCB) -> str | None:
        if not meta.offline_file:
            ext = ".exe" if meta.deploy == "install" else ".zip"
            fname = meta.id + ext
        else:
            fname = meta.offline_file
        tmp = os.path.join(tempfile.gettempdir(), "seewon_dl_" + fname)
        try:
            log(f"  下载：{meta.download_url}")
            urllib.request.urlretrieve(meta.download_url, tmp)
            log(f"  下载完成：{tmp}")
            return tmp
        except Exception as e:
            log(f"  ✗ 下载失败：{e}")
            return None

    # ---- 静默安装 ----
    def _silent_install(self, meta: SoftwareMeta, pkg: str,
                        log: LogCB, status: StatusCB) -> bool:
        status(meta.id, "安装中…")
        args = meta.silent_args or ""
        ext = os.path.splitext(pkg)[1].lower()
        if ext == ".msi":
            cmd = ["msiexec", "/i", pkg, "/quiet", "/norestart"]
            if args:
                cmd.append(args)
        else:
            cmd = [pkg]
            if args:
                cmd += args.split()
        log(f"  静默安装：{' '.join(cmd)}")
        r = subprocess.run(cmd, capture_output=True, timeout=900)
        return r.returncode == 0

    # ---- 解压部署 ----
    def _extract(self, meta: SoftwareMeta, pkg: str,
                 log: LogCB, status: StatusCB) -> bool:
        status(meta.id, "解压中…")
        # 决定目标目录
        target = meta.target_dir
        if not target:
            base = self._default_target_base()
            target = os.path.join(base, meta.name)
        log(f"  解压到：{target}")

        # 已存在则覆盖
        if os.path.exists(target):
            log(f"  目标已存在，将覆盖")
            shutil.rmtree(target, ignore_errors=True)
        os.makedirs(target, exist_ok=True)

        ext = os.path.splitext(pkg)[1].lower()
        if ext == ".zip":
            with zipfile.ZipFile(pkg, "r") as z:
                z.extractall(target)
        elif ext == ".7z":
            try:
                import py7zr
                with py7zr.SevenZipFile(pkg, "r") as z:
                    z.extractall(target)
            except ImportError:
                log("  ✗ 需要 py7zr 才能解压 .7z")
                return False
        elif ext == ".rar":
            try:
                import rarfile
                with rarfile.RarFile(pkg, "r") as z:
                    z.extractall(target)
            except ImportError:
                log("  ✗ 需要 rarfile 才能解压 .rar")
                return False
        else:
            log(f"  ✗ 不支持的压缩格式：{ext}")
            return False

        # 创建开始菜单快捷方式
        if meta.main_exe:
            main_path = os.path.join(target, meta.main_exe)
            if os.path.exists(main_path):
                self._create_shortcut(meta.name, main_path)
                log(f"  已创建开始菜单快捷方式")

        return True

    def _default_target_base(self) -> str:
        """D 盘优先，无 D 盘回退 C 盘。"""
        if os.path.exists("D:\\"):
            return r"D:\教学工具"
        return r"C:\教学工具"

    def _create_shortcut(self, name: str, target_exe: str) -> None:
        """在开始菜单创建快捷方式。"""
        try:
            start_menu = os.path.join(
                os.environ.get("ProgramData", r"C:\ProgramData"),
                "Microsoft", "Windows", "Start Menu", "Programs",
            )
            os.makedirs(start_menu, exist_ok=True)
            lnk = os.path.join(start_menu, f"{name}.lnk")
            # 用 PowerShell 创建快捷方式（免依赖 comtypes）
            ps = (
                f'$ws = New-Object -ComObject WScript.Shell; '
                f'$sc = $ws.CreateShortcut("{lnk}"); '
                f'$sc.TargetPath = "{target_exe}"; '
                f'$sc.Save()'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, timeout=15,
            )
        except Exception:
            pass
