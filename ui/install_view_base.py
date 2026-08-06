"""软件/教学工具安装子页面公共基类。

子类只需指定 local_dir、meta_path、标题、说明。
"""
from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

from core import paths
from core.installer import Installer, detect_installed
from ui.widgets import SubPage, PrimaryButton


class InstallViewBase(SubPage):
    """软件安装类页面基类。"""

    # 子类覆盖
    local_dir: str = ""
    meta_path: str = ""

    def __init__(self, master, back_command, title, desc, **kw):
        super().__init__(
            master, title=title, desc=desc,
            back_command=back_command, **kw,
        )
        body = self.body()

        # 顶部按钮
        top = tk.Frame(body, bg=paths.COLORS["bg"])
        top.pack(fill="x", pady=(0, 8))
        self._start_btn = PrimaryButton(top, "开始安装", command=self._on_start)
        self._start_btn.pack(side="left")
        tk.Button(
            top, text="刷新列表", relief="flat", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text_sub"], cursor="hand2",
            font=("Microsoft YaHei UI", 10), command=self._refresh,
        ).pack(side="left", padx=12)
        tk.Button(
            top, text="全选", relief="flat", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text_sub"], cursor="hand2",
            font=("Microsoft YaHei UI", 10), command=self._select_all,
        ).pack(side="left", padx=4)

        # 软件列表（Treeview + 勾选列）
        list_frame = tk.Frame(body, bg=paths.COLORS["bg"])
        list_frame.pack(fill="both", expand=True)

        cols = ("name", "version", "status")
        self._tree = ttk.Treeview(
            list_frame, columns=cols, show="tree headings", height=12,
        )
        self._tree.heading("#0", text="选")
        self._tree.heading("name", text="名称")
        self._tree.heading("version", text="版本")
        self._tree.heading("status", text="状态")
        self._tree.column("#0", width=40, stretch=False)
        self._tree.column("name", width=240)
        self._tree.column("version", width=100, anchor="center")
        self._tree.column("status", width=140, anchor="center")
        self._tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, command=self._tree.yview)
        sb.pack(side="right", fill="y")
        self._tree.config(yscrollcommand=sb.set)
        self._tree.bind("<Button-1>", self._on_tree_click)

        # 日志区
        log_frame = tk.Frame(body, bg=paths.COLORS["card_bg"], height=140)
        log_frame.pack(fill="both", expand=False, pady=(8, 0))
        log_frame.pack_propagate(False)
        self._log = tk.Text(
            log_frame, wrap="word", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text"], font=("Consolas", 9), relief="flat", bd=0,
        )
        self._log.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        lsb = ttk.Scrollbar(log_frame, command=self._log.yview)
        lsb.pack(side="right", fill="y", pady=8)
        self._log.config(state="disabled", yscrollcommand=lsb.set)

        self._checked: set[str] = set()
        self._installer = Installer(self.local_dir, self.meta_path)
        self._metas = self._installer.metas
        self._refresh()

    def _refresh(self) -> None:
        for it in self._tree.get_children():
            self._tree.delete(it)
        if not self._metas:
            self._tree.insert(
                "", "end", iid="empty",
                text="", values=("请向文件夹放入安装包并配置元数据", "", ""),
            )
            return
        for m in self._metas:
            installed = detect_installed(m)
            status = "已安装" if installed else "未安装"
            mark = "☑" if m.id in self._checked else "☐"
            self._tree.insert(
                "", "end", iid=m.id, text=mark,
                values=(f"{m.icon} {m.name}", m.version, status),
            )

    def _select_all(self) -> None:
        if len(self._checked) == len(self._metas):
            self._checked.clear()
        else:
            self._checked = {m.id for m in self._metas}
        self._refresh_marks()

    def _refresh_marks(self) -> None:
        for m in self._metas:
            mark = "☑" if m.id in self._checked else "☐"
            self._tree.item(m.id, text=mark)

    def _on_tree_click(self, event) -> None:
        if self._tree.identify("region", event.x, event.y) != "tree":
            return
        iid = self._tree.focus()
        if not iid or iid == "empty":
            return
        if iid in self._checked:
            self._checked.discard(iid)
        else:
            self._checked.add(iid)
        self._refresh_marks()

    def _append_log(self, msg: str) -> None:
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")

    def _on_start(self) -> None:
        if not self._checked:
            messagebox.showwarning("提示", "请先勾选要安装的项。")
            return
        ids = list(self._checked)
        if not messagebox.askyesno(
            "确认", f"将安装 {len(ids)} 项。\n继续？"
        ):
            return
        self._start_btn.config(state="disabled", text="安装中…")
        self._append_log("=" * 50)
        self._append_log(f"开始安装 {len(ids)} 项")
        threading.Thread(
            target=self._run_install, args=(ids,), daemon=True,
        ).start()

    def _run_install(self, ids: list[str]) -> None:
        def log_cb(msg: str):
            self.after(0, lambda: self._append_log(msg))

        def status_cb(item_id: str, status_text: str):
            def upd():
                if self._tree.exists(item_id):
                    vals = list(self._tree.item(item_id, "values"))
                    if len(vals) >= 3:
                        vals[2] = status_text
                        self._tree.item(item_id, values=vals)
            self.after(0, upd)

        try:
            results = self._installer.install_batch(ids, log_cb, status_cb)
            self.after(0, lambda: self._on_done(results))
        except Exception as e:
            self.after(0, lambda: self._on_error(e))

    def _on_done(self, results) -> None:
        ok = sum(1 for r in results if r.success)
        fail = [r for r in results if not r.success]
        manual = [r for r in fail if r.manual_url]
        self._append_log("=" * 50)
        self._append_log(f"完成：成功 {ok}，失败 {len(fail)}")
        for r in fail:
            self._append_log(f"  ✗ {r.item_id}: {r.message}")
        if manual:
            names = ", ".join(r.item_id for r in manual)
            self._append_log(f"需手动下载：{names}")
            if messagebox.askyesno(
                "需手动下载",
                f"以下软件官网未提供直接下载链接，需要您手动下载安装包后"
                f"放入『{self.local_dir}』文件夹：\n\n{names}\n\n"
                f"是否现在打开它们的官网下载页？",
            ):
                for r in manual:
                    try:
                        webbrowser.open(r.manual_url)
                    except Exception:
                        pass
            self._start_btn.config(text="开始安装", command=self._on_start)
        elif fail:
            self._append_log("可点『重试失败项』重新安装失败的项")
            self._start_btn.config(text="重试失败项",
                                   command=self._on_retry_fail)
        else:
            self._start_btn.config(text="开始安装", command=self._on_start)
        self._start_btn.config(state="normal")
        self._refresh()

    def _on_retry_fail(self) -> None:
        # 简化：重新检测所有项，把仍失败的列入重试
        self._checked = {
            m.id for m in self._metas if not detect_installed(m)
        }
        self._refresh_marks()
        self._start_btn.config(command=self._on_start)
        self._on_start()

    def _on_error(self, e: Exception) -> None:
        self._append_log(f"✗ 出错：{e}")
        self._start_btn.config(state="normal", text="开始安装",
                                command=self._on_start)
