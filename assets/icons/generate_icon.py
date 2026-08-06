"""构建时生成希沃蓝主题应用图标。

仓库不存二进制 ico，由 GitHub Actions 构建前调用本脚本生成。
本地打包时也可运行：python assets/icons/generate_icon.py
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, "app.ico")
    os.makedirs(out_dir, exist_ok=True)

    sizes = [16, 32, 48, 64, 128, 256]
    imgs = []
    for s in sizes:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # 圆角希沃蓝底
        margin = max(1, s // 16)
        d.rounded_rectangle(
            [margin, margin, s - margin, s - margin],
            radius=max(2, s // 6), fill=(0, 97, 255, 255),
        )
        # 中央字母 S
        try:
            font = ImageFont.truetype("arial.ttf", int(s * 0.6))
        except Exception:
            font = ImageFont.load_default()
        text = "S"
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(
            ((s - tw) / 2 - bbox[0], (s - th) / 2 - bbox[1]),
            text, fill=(255, 255, 255, 255), font=font,
        )
        imgs.append(img)

    imgs[0].save(
        out_path, format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=imgs[1:],
    )
    print(f"icon generated: {out_path}")


if __name__ == "__main__":
    main()
