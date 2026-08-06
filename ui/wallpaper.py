"""希沃壁纸更换子页面。

布局：
- 顶部：当前壁纸预览 + "刷新"按钮
- 中部：壁纸网格缩略图（可滚动），点选高亮
- 底部："同时设为锁屏壁纸"勾选 + "设为桌面壁纸"按钮 + 大图预览
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from core import paths
from core import wallpaper as wp
from ui.widgets import SubPage, PrimaryButton

THUMB_SIZE = (160, 100)


class WallpaperView(SubPage):
    def __init__(self, master, back_command, **kw):
        super().__init__(
            master,
            title="希沃壁纸更换",
            desc="从『壁纸』文件夹选择图片设为桌面壁纸，可选同时设为锁屏壁纸。",
            back_command=back_command, **kw,
        )
        body = self.body()

        # 顶部：当前壁纸 + 刷新
        top = tk.Frame(body, bg=paths.COLORS["bg"])
        top.pack(fill="x", pady=(0, 8))

        tk.Label(
            top, text="当前壁纸：", bg=paths.COLORS["bg"],
            font=("Microsoft YaHei UI", 10), fg=paths.COLORS["text_sub"],
        ).pack(side="left")
        cur = wp.get_current_wallpaper()
        self._cur_label = tk.Label(
            top, text=(os.path.basename(cur) if cur else "（未读取到）"),
            bg=paths.COLORS["bg"], font=("Microsoft YaHei UI", 10),
            fg=paths.COLORS["text"], anchor="w",
        )
        self._cur_label.pack(side="left", fill="x", expand=True)
        tk.Button(
            top, text="刷新", relief="flat", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text_sub"], cursor="hand2",
            font=("Microsoft YaHei UI", 10), command=self._refresh,
        ).pack(side="right")

        # 缩略图网格（可滚动）
        canvas_frame = tk.Frame(body, bg=paths.COLORS["bg"])
        canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(
            canvas_frame, bg=paths.COLORS["bg"], highlightthickness=0,
        )
        self._canvas.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(canvas_frame, command=self._canvas.yview)
        sb.pack(side="right", fill="y")
        self._canvas.config(yscrollcommand=sb.set)
        self._canvas.bind(
            "<Configure>", lambda e: self._layout_thumbs()
        )
        self._canvas.bind(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(
                int(-e.delta / 120), "units"),
        )

        self._inner = tk.Frame(self._canvas, bg=paths.COLORS["bg"])
        self._inner_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw",
        )
        self._inner.bind(
            "<Configure>",
            lambda e: self._canvas.config(scrollregion=self._canvas.bbox("all")),
        )

        # 空提示
        self._empty_label = tk.Label(
            self._inner, text="请将壁纸图片放入程序同级的『壁纸』文件夹",
            bg=paths.COLORS["bg"], fg=paths.COLORS["text_sub"],
            font=("Microsoft YaHei UI", 11),
        )

        # 底部操作
        ops = tk.Frame(body, bg=paths.COLORS["bg"])
        ops.pack(fill="x", pady=(8, 0))
        self._lock_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ops, text="同时设为锁屏壁纸", variable=self._lock_var,
            bg=paths.COLORS["bg"], activebackground=paths.COLORS["bg"],
            font=("Microsoft YaHei UI", 10), fg=paths.COLORS["text"],
            selectcolor="#FFFFFF",
        ).pack(side="left")
        self._apply_btn = PrimaryButton(
            ops, "设为桌面壁纸", command=self._on_apply,
        )
        self._apply_btn.pack(side="right")
        self._preview_btn = tk.Button(
            ops, text="预览大图", relief="flat", bg=paths.COLORS["card_bg"],
            fg=paths.COLORS["text_sub"], cursor="hand2",
            font=("Microsoft YaHei UI", 10), command=self._on_preview,
        )
        self._preview_btn.pack(side="right", padx=12)

        self._wallpapers: list[str] = []
        self._thumbs: list[ImageTk.PhotoImage] = []  # 防止 GC
        self._thumb_widgets: dict[str, tk.Label] = {}
        self._selected: str | None = None
        self._refresh()

    def _refresh(self) -> None:
        cur = wp.get_current_wallpaper()
        self._cur_label.config(
            text=os.path.basename(cur) if cur else "（未读取到）"
        )
        # 清空旧缩略图
        for w in self._inner.winfo_children():
            w.destroy()
        self._thumbs.clear()
        self._thumb_widgets.clear()
        self._selected = None

        self._wallpapers = wp.list_wallpapers()
        if not self._wallpapers:
            self._empty_label = tk.Label(
                self._inner, text="请将壁纸图片放入程序同级的『壁纸』文件夹",
                bg=paths.COLORS["bg"], fg=paths.COLORS["text_sub"],
                font=("Microsoft YaHei UI", 11),
            )
            self._empty_label.grid(row=0, column=0, pady=40)
            return

        self._load_thumbs()
        self._layout_thumbs()

    def _load_thumbs(self) -> None:
        cols = max(1, (self._canvas.winfo_width() or 600) // (THUMB_SIZE[0] + 24))
        for i, path in enumerate(self._wallpapers):
            try:
                img = Image.open(path)
                img.thumbnail(THUMB_SIZE)
                photo = ImageTk.PhotoImage(img)
                self._thumbs.append(photo)
            except Exception:
                # 损坏图片用占位
                photo = None
                self._thumbs.append(None)

            r, c = divmod(i, cols)
            cell = tk.Frame(
                self._inner, bg=paths.COLORS["card_bg"], bd=2,
                relief="flat",
            )
            cell.grid(row=r, column=c, padx=8, pady=8)

            if photo:
                lbl = tk.Label(
                    cell, image=photo, bg=paths.COLORS["card_bg"],
                    cursor="hand2",
                )
            else:
                lbl = tk.Label(
                    cell, text="[损坏]", bg=paths.COLORS["card_bg"],
                    width=20, height=8, fg=paths.COLORS["error"],
                )
            lbl.pack(padx=4, pady=(4, 2))
            name = os.path.basename(path)
            if len(name) > 22:
                name = name[:19] + "…"
            tk.Label(
                cell, text=name, bg=paths.COLORS["card_bg"],
                font=("Microsoft YaHei UI", 8), fg=paths.COLORS["text_sub"],
            ).pack(pady=(0, 4))

            lbl.bind("<Button-1>", lambda e, p=path: self._select(p))
            self._thumb_widgets[path] = cell

    def _layout_thumbs(self) -> None:
        # 重新按当前画布宽度排布列数
        if not self._wallpapers:
            return
        # 简化：已加载时不动，刷新时重排
        pass

    def _select(self, path: str) -> None:
        self._selected = path
        for p, cell in self._thumb_widgets.items():
            if p == path:
                cell.config(relief="solid",
                            bg=paths.COLORS["primary"])
                for child in cell.winfo_children():
                    try:
                        child.config(bg=paths.COLORS["primary"])
                    except Exception:
                        pass
            else:
                cell.config(relief="flat", bg=paths.COLORS["card_bg"])
                for child in cell.winfo_children():
                    try:
                        child.config(bg=paths.COLORS["card_bg"])
                    except Exception:
                        pass

    def _on_preview(self) -> None:
        if not self._selected:
            messagebox.showinfo("提示", "请先选择一张壁纸。")
            return
        win = tk.Toplevel(self)
        win.title(os.path.basename(self._selected))
        win.geometry("900x600")
        try:
            img = Image.open(self._selected)
            img.thumbnail((900, 600))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(win, image=photo, bg="#000000")
            lbl.image = photo
            lbl.pack(fill="both", expand=True)
        except Exception as e:
            tk.Label(win, text=f"无法预览：{e}").pack(pady=40)

    def _on_apply(self) -> None:
        if not self._selected:
            messagebox.showinfo("提示", "请先选择一张壁纸。")
            return
        ok = wp.set_desktop_wallpaper(self._selected)
        lock_ok = True
        if self._lock_var.get():
            lock_ok = wp.set_lockscreen_wallpaper(self._selected)
        if ok and lock_ok:
            msg = "已设为桌面壁纸"
            if self._lock_var.get():
                msg += " 及锁屏壁纸"
            messagebox.showinfo("成功", msg)
            self._cur_label.config(text=os.path.basename(self._selected))
        else:
            err = []
            if not ok:
                err.append("桌面壁纸设置失败")
            if self._lock_var.get() and not lock_ok:
                err.append("锁屏壁纸设置失败")
            messagebox.showerror("失败", "；".join(err))
