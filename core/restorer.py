"""还原执行引擎：精确回滚 + 系统还原点兜底。

精确回滚按 backup/<时间戳>.json 记录逐项恢复：
- startup：把 DisabledBySeewon 子键里的项移回原 Run 位置
- services：恢复原 Start 值
- registry：把备份的值写回
- snap：恢复原贴靠设置值
- 希沃缓存清理：不可回滚，仅提示
"""
from __future__ import annotations

import winreg
from dataclasses import dataclass, field

from core import backup as backup_mod
from core.optimizer import HIVE_BY_NAME

LogCB = backup_mod  # 仅用于类型提示占位


@dataclass
class RestoreResult:
    restored: int = 0
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


class Restorer:
    """精确回滚执行器。"""

    def run(self, timestamp: str, log=print) -> RestoreResult:
        record = backup_mod.load_record(timestamp)
        if record is None:
            log(f"✗ 未找到备份记录：{timestamp}")
            return RestoreResult()

        result = RestoreResult()
        items = record.items

        # 1. 启动项：从 DisabledBySeewon 移回原位置
        for entry in items.get("startup", []):
            try:
                hive = HIVE_BY_NAME[entry["hive"]]
                key_path = entry["key"]
                name = entry["name"]
                value = entry["value"]
                vtype = entry.get("type", winreg.REG_SZ)
                access = winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY

                # 从 DisabledBySeewon 读取并删除
                disabled_path = (r"Software\Microsoft\Windows\CurrentVersion\Run"
                                 r"\DisabledBySeewon")
                # 优先尝试与原 hive 一致的子键
                try:
                    with winreg.OpenKey(hive, disabled_path, 0, access) as dk:
                        winreg.DeleteValue(dk, name)
                except FileNotFoundError:
                    pass

                # 写回原 Run 位置
                with winreg.OpenKey(hive, key_path, 0, access) as k:
                    winreg.SetValueEx(k, name, 0, vtype, value)
                result.restored += 1
                log(f"  ✓ 恢复启动项：{name}")
            except Exception as e:
                result.failed.append(f"启动项 {entry.get('name')}: {e}")
                log(f"  ✗ 启动项 {entry.get('name')} 恢复失败：{e}")

        # 2. 服务：恢复原 Start 值
        for entry in items.get("services", []):
            try:
                svc = entry["name"]
                before = entry["start_before"]
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    rf"SYSTEM\CurrentControlSet\Services\{svc}",
                    0, winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY,
                ) as k:
                    winreg.SetValueEx(k, "Start", 0, winreg.REG_DWORD, before)
                result.restored += 1
                log(f"  ✓ 恢复服务：{svc}")
            except Exception as e:
                result.failed.append(f"服务 {entry.get('name')}: {e}")
                log(f"  ✗ 服务 {entry.get('name')} 恢复失败：{e}")

        # 3. 注册表清理项：写回原值
        for entry in items.get("registry", []):
            try:
                hive = HIVE_BY_NAME[entry["hive"]]
                key_path = entry["key"]
                name = entry["name"]
                old_value = entry["old_value"]
                access = winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
                with winreg.OpenKey(hive, key_path, 0, access) as k:
                    if old_value is None:
                        try:
                            winreg.DeleteValue(k, name)
                        except FileNotFoundError:
                            pass
                    else:
                        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, old_value)
                result.restored += 1
                log(f"  ✓ 恢复注册表项：{name}")
            except Exception as e:
                result.failed.append(f"注册表 {entry.get('name')}: {e}")
                log(f"  ✗ 注册表 {entry.get('name')} 恢复失败：{e}")

        # 4. 贴靠设置：恢复原值
        for entry in items.get("snap", []):
            try:
                hive = HIVE_BY_NAME[entry["hive"]]
                key_path = entry["key"]
                name = entry["name"]
                old_value = entry["old_value"]
                access = winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
                with winreg.OpenKey(hive, key_path, 0, access) as k:
                    if old_value is None:
                        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, "1")
                    else:
                        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, old_value)
                result.restored += 1
                log(f"  ✓ 恢复贴靠设置：{name}")
            except Exception as e:
                result.failed.append(f"贴靠 {entry.get('name')}: {e}")
                log(f"  ✗ 贴靠 {entry.get('name')} 恢复失败：{e}")

        # 5. 触摸手势：恢复 DWORD 原值
        for entry in items.get("touchpad", []):
            try:
                hive = HIVE_BY_NAME[entry["hive"]]
                key_path = entry["key"]
                name = entry["name"]
                old_value = entry["old_value"]
                access = winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY
                with winreg.OpenKey(hive, key_path, 0, access) as k:
                    if old_value is None:
                        try:
                            winreg.DeleteValue(k, name)
                        except FileNotFoundError:
                            pass
                    else:
                        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, old_value)
                result.restored += 1
                log(f"  ✓ 恢复触摸手势设置：{name}")
            except Exception as e:
                result.failed.append(f"触摸手势 {entry.get('name')}: {e}")
                log(f"  ✗ 触摸手势 {entry.get('name')} 恢复失败：{e}")

        # 6. 希沃缓存：不可回滚
        if items.get("seewo_cache_cleaned"):
            result.skipped.append("希沃缓存（已清理，无法恢复）")
            log("  ⊘ 希沃缓存已清理，无法恢复（跳过）")

        # 还原成功后删除该记录
        backup_mod.delete_record(timestamp)
        log(f"【完成】共恢复 {result.restored} 项"
            f"，失败 {len(result.failed)} 项，跳过 {len(result.skipped)} 项")
        return result
