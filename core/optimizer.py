"""一键优化引擎。

提供 OPTIMIZE_ITEMS 优化项定义和 Optimizer 执行器。
Optimizer 通过 callback 把进度/日志实时回报给 UI，避免阻塞主线程。
执行在后台线程中运行；UI 通过 callback 更新。
"""
from __future__ import annotations

import ctypes
import glob
import os
import shutil
import subprocess
import tempfile
import winreg
from dataclasses import dataclass
from typing import Callable, Any

from core import backup as backup_mod
from core import paths

# 日志回调类型：(message: str) -> None
LogCB = Callable[[str], None]
# 进度回调类型：(current: int, total: int) -> None
ProgCB = Callable[[int, int], None]


# ---- 优化项定义 ----
OPTIMIZE_ITEMS = [
    ("temp",        "临时文件清理"),
    ("startup",     "启动项优化"),
    ("services",    "服务优化"),
    ("registry",    "注册表清理"),
    ("memory",      "内存释放"),
    ("defrag",      "磁盘碎片整理"),
    ("seewo",       "希沃特定项清理"),
    ("snap",        "关闭 Windows 贴靠布局"),
    ("touchpad",    "关闭三指/四指触摸手势"),
    ("uninstall_bloat", "卸载无线投屏/课堂助手"),
    ("display",     "设置缩放125%与分辨率1920x1080"),
]


# ---- Windows 注册表 hive 常量映射（便于序列化）----
HIVE_MAP = {
    winreg.HKEY_CLASSES_ROOT: "HKEY_CLASSES_ROOT",
    winreg.HKEY_CURRENT_USER: "HKEY_CURRENT_USER",
    winreg.HKEY_LOCAL_MACHINE: "HKEY_LOCAL_MACHINE",
    winreg.HKEY_USERS: "HKEY_USERS",
    winreg.HKEY_CURRENT_CONFIG: "HKEY_CURRENT_CONFIG",
}
HIVE_BY_NAME = {v: k for k, v in HIVE_MAP.items()}


# ---- 安全名单：启动项/服务优化时保留 ----
# 启动项只保留系统关键项 + 希沃视频展台/白板；其余非系统启动项一律禁用
KEEP_STARTUP_KEYWORDS = (
    # 系统关键项
    "security", "defend", "antivirus", "firewall", "windows", "microsoft",
    # 希沃保留项：视频展台、白板
    "视频展台", "visualpresenter", "seewopresenter",
    "希沃白板", "easinote", "seewopinco", "pinco",
)
# 明确要禁用的常见希沃非必要启动项（仅用于注释说明，非保留即禁用）
REMOVE_STARTUP_HINTS = ("无线投屏", "希沃课堂助手")

# ---- 一键优化中可卸载的希沃非必要软件 ----
BLOATWARE_TARGETS = {
    "无线投屏": ("无线投屏", "无线传屏", "screenmirror", "mirror", "传屏", "seewomirror"),
    "希沃课堂助手": ("课堂助手", "classassistant", "seewo assistant", "class assistant"),
}

KEEP_SERVICES = {
    "SeewoService", "SeewoMain", "wuauserv", "BITS", "WinDefend",
    "MpsSvc", "Schedule", "EventLog", "PlugPlay", "Winmgmt",
}

# ---- 预定义可关闭的非必要服务 ----
NON_ESSENTIAL_SERVICES = [
    "DiagTrack",   # 诊断跟踪
    "WSearch",     # Windows 索引
    "Fax",
    "SCardSvr",    # 智能卡
    "ScDeviceEnum",
    "SCPolicySvc",
    "TrkWks",      # 分布式链接跟踪客户端
    "WMPNetworkSvc",
]


@dataclass
class OptResult:
    """单次优化汇总。"""
    cleaned_bytes: int = 0
    disabled_startup: int = 0
    disabled_services: int = 0
    reg_cleaned: int = 0
    mem_before_mb: int = 0
    mem_after_mb: int = 0
    uninstalled_bloat: list[str] = None
    uninstall_failed: list[str] = None
    errors: list[str] = None

    def __post_init__(self):
        if self.uninstalled_bloat is None:
            self.uninstalled_bloat = []
        if self.uninstall_failed is None:
            self.uninstall_failed = []
        if self.errors is None:
            self.errors = []


class Optimizer:
    """优化执行器。

    用法：
        opt = Optimizer()
        opt.run(selected_items, log_cb, prog_cb)
    """

    def __init__(self):
        self.result = OptResult()
        self.record: backup_mod.BackupRecord | None = None

    # ---- 主入口 ----
    def run(self, selected: list[str],
            log: LogCB = lambda m: None,
            prog: ProgCB = lambda c, t: None) -> OptResult:
        selected = [k for k in selected if any(k == i[0] for i in OPTIMIZE_ITEMS)]
        total = len(selected) + 1  # +1 for 前置备份
        step = 0

        # 前置：建还原点 + 初始化回滚记录
        log("【准备】创建系统还原点与回滚记录…")
        ts = backup_mod.new_timestamp()
        rp = f"SeewonOptimizer_{ts}"
        ok = backup_mod.create_restore_point(rp)
        log(f"  系统还原点：{'已创建 ' + rp if ok else '创建失败（系统保护未开启），仍可使用精确回滚'}")
        self.record = backup_mod.BackupRecord(
            timestamp=ts,
            created_at=__import__("datetime").datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"),
            restore_point=rp,
            items={},
        )
        if "memory" in selected:
            self.result.mem_before_mb = _used_memory_mb()
            log(f"  优化前内存占用：{self.result.mem_before_mb} MB")

        step += 1
        prog(step, total)

        for key in selected:
            name = dict(OPTIMIZE_ITEMS).get(key, key)
            log(f"【{name}】开始…")
            try:
                getattr(self, f"_opt_{key}")(log)
            except Exception as e:
                log(f"  ✗ 出错：{e}")
                self.result.errors.append(f"{name}: {e}")
            step += 1
            prog(step, total)

        # 保存回滚记录
        if self.record:
            backup_mod.save_record(self.record)
            log(f"【完成】回滚记录已保存：{self.record.timestamp}.json")

        if "memory" in selected:
            self.result.mem_after_mb = _used_memory_mb()
            log(f"  优化后内存占用：{self.result.mem_after_mb} MB")
        return self.result

    # ---- 1. 临时文件清理 ----
    def _opt_temp(self, log: LogCB) -> None:
        targets: list[str] = []
        targets += [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp")]
        targets += [tempfile.gettempdir()]
        targets += [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Prefetch")]
        targets += [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                 "SoftwareDistribution", "Download")]
        # 浏览器缓存
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            targets += [
                os.path.join(local, r"Google\Chrome\User Data\Default\Cache"),
                os.path.join(local, r"Microsoft\Edge\User Data\Default\Cache"),
                os.path.join(local, r"Mozilla\Firefox\Profiles"),
            ]

        freed = 0
        skipped = 0
        for t in targets:
            if not os.path.exists(t):
                continue
            for root, dirs, files in os.walk(t):
                for fn in files:
                    fp = os.path.join(root, fn)
                    try:
                        sz = os.path.getsize(fp)
                        os.remove(fp)
                        freed += sz
                    except Exception:
                        skipped += 1
        self.result.cleaned_bytes += freed
        log(f"  清理 {freed / 1024 / 1024:.1f} MB，跳过占用文件 {skipped} 个")

    # ---- 2. 启动项优化 ----
    def _opt_startup(self, log: LogCB) -> None:
        run_keys = [
            (winreg.HKEY_CURRENT_USER,
             r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]
        disabled_sub = r"Software\Microsoft\Windows\CurrentVersion\Run\DisabledBySeewon"
        backed: list[dict] = []

        for hive, key_path in run_keys:
            try:
                access = winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
                with winreg.OpenKey(hive, key_path, 0, access) as src:
                    names = []
                    i = 0
                    while True:
                        try:
                            names.append(winreg.EnumValue(src, i)[0])
                        except OSError:
                            break
                        i += 1
                for name in names:
                    if _keep_keyword(name):
                        continue
                    with winreg.OpenKey(hive, key_path, 0, access) as src:
                        val, val_type = winreg.QueryValueEx(src, name)
                    # 备份
                    backed.append({
                        "hive": HIVE_MAP[hive],
                        "key": key_path,
                        "name": name,
                        "value": val,
                        "type": val_type,
                    })
                    # 移到 DisabledBySeewon 子键
                    disabled_hive = winreg.HKEY_CURRENT_USER
                    if hive == winreg.HKEY_LOCAL_MACHINE:
                        disabled_hive = winreg.HKEY_LOCAL_MACHINE
                    disabled_path = (r"Software\Microsoft\Windows\CurrentVersion\Run"
                                     r"\DisabledBySeewon")
                    _ensure_key(disabled_hive, disabled_path)
                    with winreg.OpenKey(disabled_hive, disabled_path, 0, access) as dst:
                        winreg.SetValueEx(dst, name, 0, val_type, val)
                    with winreg.OpenKey(hive, key_path, 0, access) as src:
                        winreg.DeleteValue(src, name)
            except Exception:
                continue

        self.record.items["startup"] = backed
        self.result.disabled_startup = len(backed)
        log(f"  禁用启动项 {len(backed)} 个")

    # ---- 3. 服务优化 ----
    def _opt_services(self, log: LogCB) -> None:
        backed: list[dict] = []
        for svc in NON_ESSENTIAL_SERVICES:
            if svc in KEEP_SERVICES:
                continue
            try:
                # 读取当前 Start 值
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    rf"SYSTEM\CurrentControlSet\Services\{svc}",
                    0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                ) as k:
                    before, _ = winreg.QueryValueEx(k, "Start")
                # 改为禁用(4)
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    rf"SYSTEM\CurrentControlSet\Services\{svc}",
                    0, winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY,
                ) as k:
                    winreg.SetValueEx(k, "Start", 0, winreg.REG_DWORD, 4)
                backed.append({"name": svc, "start_before": before})
            except FileNotFoundError:
                continue
            except Exception:
                continue

        self.record.items["services"] = backed
        self.result.disabled_services = len(backed)
        log(f"  禁用服务 {len(backed)} 个")

    # ---- 4. 注册表清理 ----
    def _opt_registry(self, log: LogCB) -> None:
        backed: list[dict] = []
        # 清理最近使用文档历史（MRU）等安全项
        mru_keys = [
            (winreg.HKEY_CURRENT_USER,
             r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU"),
            (winreg.HKEY_CURRENT_USER,
             r"Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths"),
        ]
        cleaned = 0
        for hive, key_path in mru_keys:
            try:
                access = winreg.KEY_READ | winreg.KEY_WRITE
                with winreg.OpenKey(hive, key_path, 0, access) as k:
                    names = []
                    i = 0
                    while True:
                        try:
                            names.append(winreg.EnumValue(k, i)[0])
                        except OSError:
                            break
                        i += 1
                    for name in names:
                        val, vt = winreg.QueryValueEx(k, name)
                        backed.append({
                            "hive": HIVE_MAP[hive], "key": key_path,
                            "name": name, "old_value": val,
                        })
                        winreg.DeleteValue(k, name)
                        cleaned += 1
            except FileNotFoundError:
                continue
            except Exception:
                continue

        self.record.items["registry"] = backed
        self.result.reg_cleaned = cleaned
        log(f"  清理注册表项 {cleaned} 个")

    # ---- 5. 内存释放 ----
    def _opt_memory(self, log: LogCB) -> None:
        try:
            import psutil
        except ImportError:
            log("  跳过：未安装 psutil")
            return

        psapi = ctypes.WinDLL("psapi.dll")
        kernel = ctypes.WinDLL("kernel32.dll")
        EmptyWorkingSet = kernel.EmptyWorkingSet
        EmptyWorkingSet.argtypes = [ctypes.wintypes.HANDLE]
        EmptyWorkingSet.restype = ctypes.wintypes.BOOL

        freed_procs = 0
        for proc in psutil.process_iter(["pid"]):
            try:
                h = kernel.OpenProcess(0x0200 | 0x0400, False, proc.info["pid"])  # QUERY_LIMITED|SET
                if h:
                    if EmptyWorkingSet(h):
                        freed_procs += 1
                    kernel.CloseHandle(h)
            except Exception:
                continue
        log(f"  释放 {freed_procs} 个进程工作集")

    # ---- 6. 磁盘碎片整理 ----
    def _opt_defrag(self, log: LogCB) -> None:
        sys_drive = os.environ.get("SystemDrive", "C:")
        # /O 按介质类型自动优化（SSD 执行 TRIM，HDD 执行 defrag）
        try:
            r = subprocess.run(
                ["defrag", sys_drive, "/O", "/U"],
                capture_output=True, text=True, timeout=600,
            )
            if r.returncode == 0:
                log(f"  {sys_drive} 优化完成")
            else:
                log(f"  {sys_drive} 优化返回码 {r.returncode}")
        except Exception as e:
            log(f"  跳过磁盘优化：{e}")

    # ---- 7. 希沃特定项清理 ----
    def _opt_seewo(self, log: LogCB) -> None:
        appdata = os.environ.get("APPDATA", "")
        cleaned = 0
        if appdata:
            seewo_dir = os.path.join(appdata, "Seewo")
            if os.path.isdir(seewo_dir):
                # 清理缓存子目录，保留配置文件
                cache_subs = ["Cache", "cache", "Temp", "Logs", "log"]
                for sub in cache_subs:
                    target = os.path.join(seewo_dir, sub)
                    if os.path.isdir(target):
                        try:
                            shutil.rmtree(target, ignore_errors=True)
                            cleaned += 1
                        except Exception:
                            continue
        log(f"  清理希沃缓存目录 {cleaned} 个")

    # ---- 8. 关闭 Windows 贴靠布局 ----
    def _opt_snap(self, log: LogCB) -> None:
        backed: list[dict] = []
        # 项 1：将窗口拖动到屏幕顶部时显示贴靠布局
        backed += _set_reg(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            "WindowArrangementActive",
            "0",
        )
        # 项 2：拖动窗口时自动贴靠而无需拖到边缘
        backed += _set_reg(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
            "SnapInDock",
            "0",
        )
        self.record.items["snap"] = backed
        log(f"  贴靠布局设置已关闭（{len(backed)} 项）")

    # ---- 9. 关闭三指/四指触摸手势 ----
    def _opt_touchpad(self, log: LogCB) -> None:
        backed: list[dict] = []
        base_key = r"Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad"

        # 主开关：滑动与点击
        for name in ("ThreeFingerSlideEnabled", "FourFingerSlideEnabled",
                     "ThreeFingerTapEnabled", "FourFingerTapEnabled"):
            backed += _set_reg_dword(winreg.HKEY_CURRENT_USER, base_key, name, 0)

        # 各方向子键
        directions = ("SwipeUp", "SwipeDown", "SwipeLeft", "SwipeRight")
        for sub, _label in (
            (f"{base_key}\\ThreeFingerGestures", "三指"),
            (f"{base_key}\\FourFingerGestures", "四指"),
        ):
            for direction in directions:
                backed += _set_reg_dword(winreg.HKEY_CURRENT_USER, sub, direction, 0)

        self.record.items["touchpad"] = backed
        log(f"  三指/四指触摸手势已关闭（{len(backed)} 项）")

    # ---- 10. 卸载无线投屏/希沃课堂助手 ----
    def _opt_uninstall_bloat(self, log: LogCB) -> None:
        uninstalled: list[str] = []
        failed: list[str] = []

        for label, keywords in BLOATWARE_TARGETS.items():
            targets = _find_uninstall_entries(keywords)
            if not targets:
                log(f"  未找到 {label}")
                continue
            for display_name, cmd in targets:
                log(f"  正在卸载：{display_name}")
                if _run_uninstall_silent(display_name, cmd, log):
                    uninstalled.append(display_name)
                else:
                    failed.append(display_name)

        # 卸载操作不可回滚，仅记录已卸载列表用于汇总
        self.record.items["uninstall_bloat"] = {
            "uninstalled": uninstalled,
            "failed": failed,
        }
        self.result.uninstalled_bloat = uninstalled
        self.result.uninstall_failed = failed
        log(f"  卸载完成 {len(uninstalled)} 个，失败 {len(failed)} 个")

    # ---- 11. 设置缩放 125% 与分辨率 1920x1080 ----
    def _opt_display(self, log: LogCB) -> None:
        backed: list[dict] = []

        # 备份当前分辨率
        cur_w, cur_h = _get_current_resolution()
        backed.append({
            "type": "resolution",
            "width": cur_w,
            "height": cur_h,
        })

        # DPI：LogPixels 96=100%, 120=125%, 144=150%
        target_dpi = 120
        backed += _set_reg_dword(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            "LogPixels",
            target_dpi,
        )
        backed += _set_reg_dword(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            "Win8DpiScaling",
            1,
        )

        # 设置分辨率
        ok = _set_resolution(1920, 1080)
        if ok:
            log("  分辨率已设为 1920x1080")
        else:
            log("  ✗ 分辨率设置失败，可能是当前显示器不支持")

        self.record.items["display"] = backed
        log("  显示缩放已设为 125%，注销或重启后完全生效")


# ---- 辅助函数 ----
def _ensure_key(hive, path: str) -> None:
    winreg.CreateKeyEx(hive, path, 0, winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)


def _set_reg(hive, key_path: str, name: str, new_value: str) -> list[dict]:
    """设置注册表字符串值，备份原值。返回备份条目列表。"""
    backed: list[dict] = []
    access = winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
    try:
        _ensure_key(hive, key_path)
        with winreg.OpenKey(hive, key_path, 0, access) as k:
            try:
                old, _ = winreg.QueryValueEx(k, name)
            except FileNotFoundError:
                old = None
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, new_value)
            backed.append({
                "hive": HIVE_MAP[hive], "key": key_path,
                "name": name, "old_value": old,
            })
    except Exception:
        pass
    return backed


def _set_reg_dword(hive, key_path: str, name: str, new_value: int) -> list[dict]:
    """设置注册表 DWORD 值，备份原值。返回备份条目列表。"""
    backed: list[dict] = []
    access = winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
    try:
        _ensure_key(hive, key_path)
        with winreg.OpenKey(hive, key_path, 0, access) as k:
            try:
                old, _ = winreg.QueryValueEx(k, name)
            except FileNotFoundError:
                old = None
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, new_value)
            backed.append({
                "hive": HIVE_MAP[hive], "key": key_path,
                "name": name, "old_value": old,
            })
    except Exception:
        pass
    return backed


def _find_uninstall_entries(keywords: tuple[str, ...]) -> list[tuple[str, str]]:
    """根据关键词在已安装软件列表中查找卸载命令。

    返回 [(DisplayName, UninstallString), ...]
    """
    results: list[tuple[str, str]] = []
    uninstall_roots = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, root in uninstall_roots:
        try:
            access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            with winreg.OpenKey(hive, root, 0, access) as k:
                idx = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(k, idx)
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(hive, f"{root}\\{subkey_name}",
                                            0, access) as sk:
                            display_name, _ = winreg.QueryValueEx(sk,
                                                                  "DisplayName")
                            uninstall_string, _ = winreg.QueryValueEx(
                                sk, "UninstallString")
                            name_lower = display_name.lower()
                            if any(kw.lower() in name_lower
                                   for kw in keywords):
                                results.append((display_name,
                                                uninstall_string))
                    except (OSError, FileNotFoundError):
                        pass
                    idx += 1
        except Exception:
            continue
    return results


def _run_uninstall_silent(display_name: str, cmd: str,
                          log: LogCB) -> bool:
    """静默执行卸载命令，尝试常见静默参数。"""
    cmd = cmd.strip()
    lowered = cmd.lower()

    # MSI 安装包：改为静默卸载 /qn
    if "msiexec" in lowered:
        silent_cmd = lowered.replace("/i", "/x").replace("/i", "/x")
        if "/qn" not in silent_cmd and "/qb" not in silent_cmd:
            silent_cmd += " /qn"
        try:
            r = subprocess.run(silent_cmd, shell=True, capture_output=True,
                               text=True, timeout=180)
            if r.returncode == 0:
                return True
            log(f"    MSI 返回码 {r.returncode}：{r.stderr.strip()}")
        except Exception as e:
            log(f"    MSI 卸载异常：{e}")
        return False

    # EXE 安装包：尝试常见静默参数
    for arg in ("/S", "/s", "/silent", "/quiet", "/uninstall /s"):
        try:
            r = subprocess.run(f'"{cmd}" {arg}', shell=True,
                               capture_output=True, text=True, timeout=180)
            if r.returncode == 0:
                return True
        except Exception:
            continue

    # 最后尝试原命令（可能弹出卸载向导）
    try:
        r = subprocess.run(f'"{cmd}"', shell=True, capture_output=True,
                           text=True, timeout=180)
        return r.returncode == 0
    except Exception as e:
        log(f"    卸载异常：{e}")
        return False


def _keep_keyword(name: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in (k.lower() for k in KEEP_STARTUP_KEYWORDS))


def _used_memory_mb() -> int:
    try:
        import psutil
        return int(psutil.virtual_memory().used / 1024 / 1024)
    except ImportError:
        return 0


# ---- 显示设置相关 API ----
class _DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_ubyte * 32),
        ("dmSpecVersion", ctypes.c_ushort),
        ("dmDriverVersion", ctypes.c_ushort),
        ("dmSize", ctypes.c_ushort),
        ("dmDriverExtra", ctypes.c_ushort),
        ("dmFields", ctypes.c_ulong),
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_ubyte * 32),
        ("dmLogPixels", ctypes.c_ushort),
        ("dmBitsPerPel", ctypes.c_ulong),
        ("dmPelsWidth", ctypes.c_ulong),
        ("dmPelsHeight", ctypes.c_ulong),
        ("dmDisplayFlags", ctypes.c_ulong),
        ("dmDisplayFrequency", ctypes.c_ulong),
        ("dmICMMethod", ctypes.c_ulong),
        ("dmICMIntent", ctypes.c_ulong),
        ("dmMediaType", ctypes.c_ulong),
        ("dmDitherType", ctypes.c_ulong),
        ("dmReserved1", ctypes.c_ulong),
        ("dmReserved2", ctypes.c_ulong),
        ("dmPanningWidth", ctypes.c_ulong),
        ("dmPanningHeight", ctypes.c_ulong),
    ]


def _get_current_resolution() -> tuple[int, int]:
    """获取当前屏幕分辨率。"""
    try:
        user32 = ctypes.windll.user32
        dm = _DEVMODE()
        dm.dmSize = ctypes.sizeof(_DEVMODE)
        ENUM_CURRENT_SETTINGS = -1
        if user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS,
                                       ctypes.byref(dm)):
            return int(dm.dmPelsWidth), int(dm.dmPelsHeight)
    except Exception:
        pass
    return 0, 0


def _set_resolution(width: int, height: int) -> bool:
    """使用 ChangeDisplaySettingsW 设置屏幕分辨率。"""
    try:
        user32 = ctypes.windll.user32
        dm = _DEVMODE()
        dm.dmSize = ctypes.sizeof(_DEVMODE)
        ENUM_CURRENT_SETTINGS = -1
        if not user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS,
                                           ctypes.byref(dm)):
            return False

        dm.dmPelsWidth = width
        dm.dmPelsHeight = height
        dm.dmFields = 0x00080000 | 0x00100000  # DM_PELSWIDTH | DM_PELSHEIGHT

        CDS_TEST = 0x00000002
        CDS_UPDATEREGISTRY = 0x00000001
        if user32.ChangeDisplaySettingsW(ctypes.byref(dm), CDS_TEST) != 0:
            return False
        result = user32.ChangeDisplaySettingsW(ctypes.byref(dm),
                                                CDS_UPDATEREGISTRY)
        return result in (0, 1)  # SUCCESSFUL 或 RESTART
    except Exception:
        return False
