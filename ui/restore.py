"""一键还原系统子页面。

布局：
- 顶部："打开 Windows 系统还原"按钮（兜底）
- 中部：历史回滚记录列表（Treeview），显示优化时间/还原点/改了哪些项
- 下方：日志区 + "开始还原"按钮
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from core import paths, backup as backup_mod
from core.restorer import Restorer
from ui.widgets import SubPage, PrimaryButton


class RestoreView(SubPage):
    def __init__(self, master, back_command, **kw):
        super().__init__(
            master,
            title="一键还原系统",
            desc="精确回滚本次优化改过的项；或调起 Windows 系统还原点整体回退。",
            back_command=back_command, **kw,
        )
        body = self.body()

        # 顶部：兜底按钮 + 刷新
        top = tk.Frame(body, bg=paths.COLORS["bg"])
        top.pack(fill="x", pady=(0, 8))
        PrimaryButton(
            top, "打开 Windows 系统还原", command=self._on_sys_restore,
        ).pack(side="left")
        tk.Button(
            top, text="刷新列表", relief="flat", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text_sub"], cursor="hand2",
            font=("Microsoft YaHei UI", 10), command=self._refresh,
        ).pack(side="left", padx=12)

        # 记录列表
        list_frame = tk.Frame(body, bg=paths.COLORS["bg"])
        list_frame.pack(fill="both", expand=True)

        cols = ("time", "items", "rp")
        self._tree = ttk.Treeview(
            list_frame, columns=cols, show="headings", height=8,
        )
        self._tree.heading("time", text="优化时间")
        self._tree.heading("items", text="改动项数")
        self._tree.heading("rp", text="还原点")
        self._tree.column("time", width=180)
        self._tree.column("items", width=80, anchor="center")
        self._tree.column("rp", width=260)
        self._tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, command=self._tree.yview)
        sb.pack(side="right", fill="y")
        self._tree.config(yscrollcommand=sb.set)

        # 操作 + 日志
        ops = tk.Frame(body, bg=paths.COLORS["bg"])
        ops.pack(fill="x", pady=(8, 4))
        self._restore_btn = PrimaryButton(
            ops, "开始还原（精确回滚）", command=self._on_restore,
        )
        self._restore_btn.pack(side="left")

        log_frame = tk.Frame(body, bg=paths.COLORS["card_bg"], height=160)
        log_frame.pack(fill="both", expand=False, pady=(4, 0))
        log_frame.pack_propagate(False)
        self._log = tk.Text(
            log_frame, wrap="word", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text"], font=("Consolas", 9), relief="flat", bd=0,
        )
        self._log.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        lsb = ttk.Scrollbar(log_frame, command=self._log.yview)
        lsb.pack(side="right", fill="y", pady=8)
        self._log.config(state="disabled", yscrollcommand=lsb.set)

        self._records: list[backup_mod.BackupRecord] = []
        self._refresh()

    def _refresh(self) -> None:
        for it in self._tree.get_children():
            self._tree.delete(it)
        self._records = backup_mod.list_records()
        if not self._records:
            self._tree.insert("", "end", iid="empty", values=("暂无记录", "", ""))
            return
        for r in self._records:
            item_count = sum(
                len(v) if isinstance(v, list) else 1
                for v in r.items.values()
            )
            self._tree.insert(
                "", "end", iid=r.timestamp,
                values=(r.created_at, item_count, r.restore_point),
            )

    def _append_log(self, msg: str) -> None:
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")

    def _selected_timestamp(self) -> str | None:
        sel = self._tree.selection()
        if not sel or sel[0] == "empty":
            return None
        return sel[0]

    def _on_sys_restore(self) -> None:
        if messagebox.askyesno(
            "确认",
            "将打开 Windows 官方系统还原界面。\n"
            "你可在其中选择 SeewonOptimizer_ 开头的还原点进行整体回退。\n继续？",
        ):
            backup_mod.open_system_restore()

    def _on_restore(self) -> None:
        ts = self._selected_timestamp()
        if not ts:
            messagebox.showwarning("提示", "请先选择一条要还原的记录。")
            return
        if not messagebox.askyesno(
            "确认",
            f"将精确回滚记录 {ts} 中改过的项。\n还原后该记录将被删除。\n继续？",
        ):
            return
        self._restore_btn.config(state="disabled", text="还原中…")
        self._append_log("=" * 50)
        self._append_log(f"开始精确回滚：{ts}")
        threading.Thread(
            target=self._run_restore, args=(ts,), daemon=True,
        ).start()

    def _run_restore(self, ts: str) -> None:
        restorer = Restorer()
        try:
            result = restorer.run(
                ts, log=lambda m: self.after(0, lambda: self._append_log(m))
            )
            self.after(0, lambda: self._on_done(result))
        except Exception as e:
            self.after(0, lambda: self._on_error(e))

    def _on_done(self, result) -> None:
        self._append_log("=" * 50)
        self._append_log(f"还原完成：恢复 {result.restored} 项"
                         f"，失败 {len(result.failed)} 项")
        self._restore_btn.config(state="normal", text="开始还原（精确回滚）")
        self._refresh()

    def _on_error(self, e: Exception) -> None:
        self._append_log(f"✗ 还原失败：{e}")
        self._restore_btn.config(state="normal", text="开始还原（精确回滚）")
