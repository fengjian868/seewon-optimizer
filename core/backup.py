"""备份与还原点管理。

负责：
- 创建 Windows 系统还原点（命名 SeewonOptimizer_<时间戳>）
- 写入/读取本次优化的精确回滚记录 backup/<时间戳>.json
- 列举/删除历史备份记录
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Any

from core import paths


@dataclass
class BackupRecord:
    """一次优化的回滚记录。"""
    timestamp: str                         # 文件名时间戳 YYYYMMDD_HHMMSS
    created_at: str                        # 可读时间
    restore_point: str                     # 系统还原点描述名
    items: dict[str, Any] = field(default_factory=dict)
    # items 结构示例：
    # {
    #   "startup":  [{"hive":..., "key":..., "name":..., "value":...}, ...],
    #   "services": [{"name":..., "start_before":...}, ...],
    #   "registry": [{"hive":..., "key":..., "name":..., "old_value":...}, ...],
    #   "snap":     [{"key":..., "name":..., "old_value":...}, ...],
    # }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BackupRecord":
        return cls(
            timestamp=d["timestamp"],
            created_at=d["created_at"],
            restore_point=d["restore_point"],
            items=d.get("items", {}),
        )


def new_timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _record_path(timestamp: str) -> str:
    return os.path.join(paths.BACKUP_DIR, f"{timestamp}.json")


def create_restore_point(description: str) -> bool:
    """创建 Windows 系统还原点。

    使用 PowerShell 调用 WMI 的 SystemRestore::CreateRestorePoint。
    需要系统已开启系统保护；若未开启会返回 False，但不影响精确回滚。
    """
    # 先确保系统保护已开启（仅尝试，失败不报错）
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Enable-ComputerRestore -Drive $env:SystemDrive\\;"],
            capture_output=True, timeout=30,
        )
    except Exception:
        pass

    ps = (
        f'$desc = "{description}"; '
        'Checkpoint-Computer -Description $desc -RestorePointType '
        '"MODIFY_SETTINGS"; '
        'Write-Output "OK"'
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=120,
        )
        return r.returncode == 0 and "OK" in (r.stdout or "")
    except Exception:
        return False


def save_record(record: BackupRecord) -> str:
    """保存回滚记录到 backup/<时间戳>.json，返回文件路径。"""
    os.makedirs(paths.BACKUP_DIR, exist_ok=True)
    path = _record_path(record.timestamp)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
    return path


def load_record(timestamp: str) -> BackupRecord | None:
    path = _record_path(timestamp)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return BackupRecord.from_dict(json.load(f))


def list_records() -> list[BackupRecord]:
    """列出所有历史回滚记录，按时间倒序。"""
    if not os.path.isdir(paths.BACKUP_DIR):
        return []
    out: list[BackupRecord] = []
    for name in os.listdir(paths.BACKUP_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(paths.BACKUP_DIR, name),
                      "r", encoding="utf-8") as f:
                out.append(BackupRecord.from_dict(json.load(f)))
        except Exception:
            continue
    out.sort(key=lambda r: r.timestamp, reverse=True)
    return out


def delete_record(timestamp: str) -> None:
    path = _record_path(timestamp)
    if os.path.exists(path):
        os.remove(path)


def open_system_restore() -> None:
    """调起 Windows 官方系统还原界面 rstrui.exe（兜底用）。"""
    subprocess.Popen(["rstrui.exe"])
