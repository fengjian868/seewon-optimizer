"""一键优化系统子页面。

布局：
- 上方：优化项清单（带勾选，默认全选）+ "开始优化"按钮
- 中部：进度条
- 下方：滚动日志区
- 完成后：显示汇总报告
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from core import paths
from core.optimizer import OPTIMIZE_ITEMS, Optimizer
from ui.widgets import SubPage, PrimaryButton


class OptimizeView(SubPage):
    def __init__(self, master, back_command, **kw):
        super().__init__(
            master,
            title="一键优化系统",
            desc="清理临时文件/启动项/服务/注册表，释放内存，关闭贴靠布局与三指/四指触摸手势。优化前自动创建还原点。",
            back_command=back_command, **kw,
        )
        body = self.body()

        # ---- 上方：优化项清单 + 开始按钮 ----
        top = tk.Frame(body, bg=paths.COLORS["bg"])
        top.pack(fill="x", pady=(0, 8))

        self._vars: dict[str, tk.BooleanVar] = {}
        for i, (key, name) in enumerate(OPTIMIZE_ITEMS):
            v = tk.BooleanVar(value=True)
            self._vars[key] = v
            cb = tk.Checkbutton(
                top, text=name, variable=v, bg=paths.COLORS["bg"],
                activebackground=paths.COLORS["bg"],
                font=("Microsoft YaHei UI", 10), fg=paths.COLORS["text"],
                selectcolor="#FFFFFF",
            )
            cb.grid(row=i // 4, column=i % 4, sticky="w", padx=8, pady=4)

        btns = tk.Frame(body, bg=paths.COLORS["bg"])
        btns.pack(fill="x", pady=(0, 8))
        self._start_btn = PrimaryButton(btns, "开始优化", command=self._on_start)
        self._start_btn.pack(side="left")
        self._select_all_btn = tk.Button(
            btns, text="全选/取消", relief="flat", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text_sub"], cursor="hand2",
            font=("Microsoft YaHei UI", 10), command=self._toggle_all,
        )
        self._select_all_btn.pack(side="left", padx=12)

        # ---- 进度条 ----
        self._prog = ttk.Progressbar(body, mode="determinate")
        self._prog.pack(fill="x", pady=(0, 8))

        # ---- 日志区 ----
        log_frame = tk.Frame(body, bg=paths.COLORS["card_bg"])
        log_frame.pack(fill="both", expand=True)

        self._log = tk.Text(
            log_frame, wrap="word", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text"], insertbackground=paths.COLORS["text"],
            font=("Consolas", 9), relief="flat", bd=0,
        )
        self._log.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb = ttk.Scrollbar(log_frame, command=self._log.yview)
        sb.pack(side="right", fill="y", pady=8)
        self._log.config(state="disabled", yscrollcommand=sb.set)

    # ---- 交互 ----
    def _toggle_all(self) -> None:
        all_true = all(v.get() for v in self._vars.values())
        for v in self._vars.values():
            v.set(not all_true)

    def _append_log(self, msg: str) -> None:
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")

    def _on_start(self) -> None:
        selected = [k for k, v in self._vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个优化项。")
            return
        if not messagebox.askyesno(
            "确认", "将开始系统优化，期间会创建还原点。\n是否继续？"
        ):
            return

        self._start_btn.config(state="disabled", text="优化中…")
        self._prog["value"] = 0
        self._append_log("=" * 50)
        self._append_log(f"开始优化，选中 {len(selected)} 项")

        t = threading.Thread(
            target=self._run_optimize, args=(selected,), daemon=True,
        )
        t.start()

    def _run_optimize(self, selected: list[str]) -> None:
        opt = Optimizer()

        def log_cb(msg: str) -> None:
            self.after(0, lambda: self._append_log(msg))

        def prog_cb(cur: int, total: int) -> None:
            def upd():
                self._prog["maximum"] = total
                self._prog["value"] = cur
            self.after(0, upd)

        try:
            result = opt.run(selected, log_cb, prog_cb)
            self.after(0, lambda: self._on_done(result))
        except Exception as e:
            self.after(0, lambda: self._on_error(e))

    def _on_done(self, result) -> None:
        self._append_log("=" * 50)
        self._append_log("优化完成")
        self._append_log(f"  清理空间：{result.cleaned_bytes / 1024 / 1024:.1f} MB")
        self._append_log(f"  禁用启动项：{result.disabled_startup}")
        self._append_log(f"  禁用服务：{result.disabled_services}")
        self._append_log(f"  清理注册表项：{result.reg_cleaned}")
        if result.mem_before_mb and result.mem_after_mb:
            delta = result.mem_before_mb - result.mem_after_mb
            self._append_log(
                f"  内存占用：{result.mem_before_mb} MB → {result.mem_after_mb} MB"
                f"（{'释放' if delta > 0 else '增加'} {abs(delta)} MB）"
            )
        if result.errors:
            self._append_log(f"  出错项：{len(result.errors)}")
            for e in result.errors:
                self._append_log(f"    - {e}")
        self._start_btn.config(state="normal", text="再次优化")

    def _on_error(self, e: Exception) -> None:
        self._append_log(f"✗ 优化失败：{e}")
        self._start_btn.config(state="normal", text="开始优化")
