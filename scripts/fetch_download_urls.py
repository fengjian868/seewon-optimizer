"""从各软件官方下载页抓取真实 exe 下载链接，更新 assets/*.json。

用法：
    python scripts/fetch_download_urls.py

注意：
- 仅抓取链接，不下载安装包
- 第三方页面结构可能变化，链接可能失效，需要定期重新运行
- 抓取结果写入 assets/software.json 和 assets/teaching_tools.json
"""
from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.request
from urllib.parse import urljoin, urlparse


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_text(url: str, timeout: int = 15) -> str:
    """获取页面文本，忽略证书验证。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read()
        # 简单处理编码
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("gbk", errors="ignore")


def find_exe_url(html: str, base_url: str, patterns: list[str] | None = None) -> str:
    """在 HTML 中查找 .exe 下载链接。"""
    candidates: list[str] = []

    # 1. 优先从 a 标签 href 里找
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>', html, re.I):
        href = m.group(1).strip()
        full = urljoin(base_url, href)
        if full.lower().endswith(".exe"):
            candidates.append(full)

    # 2. 从任意 URL 文本里找
    url_re = re.compile(r'https?://[^\s\"\'<>]+\\.exe', re.I)
    for m in url_re.finditer(html):
        candidates.append(m.group(0).replace("\\", ""))

    # 3. JS 里常见的 downloadUrl 变量
    js_re = re.compile(r'downloadUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.I)
    for m in js_re.finditer(html):
        full = urljoin(base_url, m.group(1))
        if ".exe" in full.lower():
            candidates.append(full)

    # 4. 过滤不符合的域名或路径
    def is_ok(url: str) -> bool:
        p = urlparse(url)
        if not p.scheme.startswith("http"):
            return False
        if ".exe" not in p.path.lower():
            return False
        # 排除明显的广告/第三方统计
        bad = ["google", "baidu", "umeng", "doubleclick", "googletagmanager"]
        if any(b in p.netloc.lower() for b in bad):
            return False
        return True

    candidates = [c for c in candidates if is_ok(c)]

    # 5. 按 patterns 排序（越匹配越靠前）
    if patterns:

        def score(url: str) -> int:
            low = url.lower()
            return sum(1 for p in patterns if p.lower() in low)

        candidates.sort(key=score, reverse=True)

    # 6. 去重并返回第一个
    seen = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            return c
    return ""


# 每个软件的下载页和过滤关键字
SOFTWARE_PAGES = {
    "wechat": ("https://weixin.qq.com/", ["wechat", "weixin", "windows"]),
    "qq": ("https://im.qq.com/index/", ["qq", "pc", "windows"]),
    "douyin": ("https://www.douyin.com/download/pc", ["douyin", "windows", "pc"]),
    "wps": ("https://www.wps.cn/", ["wps", "windows", "setup"]),
    "qqmusic": ("https://y.qq.com/download/index.html", ["qqmusic", "qqmusicpc", "windows"]),
    "kugou": ("https://download.kugou.com/pc.html", ["kugou", "pc", "windows"]),
    "qishui": ("https://www.qishui.com/download", ["qishui", "windows", "pc"]),
    "netease": ("https://music.163.com/#/download", ["netease", "cloudmusic", "windows"]),
}

TEACHING_PAGES = {
    "seewo_easinote": ("https://easinote.seewo.com/", ["easinote", "setup", "windows"]),
    "seewo_video_booth": ("https://www.seewo.com/", ["video", "booth", "setup"]),
    "seewo_yiketang": ("https://www.seewo.com/", ["classroom", "setup"]),
    "seewo_class_master": ("https://www.seewo.com/", ["classmaster", "setup"]),
    "seewo_manager": ("https://www.seewo.com/", ["manager", "setup"]),
    "seewo_browser": ("https://www.seewo.com/", ["browser", "setup"]),
    "seewo_screen_share": ("https://www.seewo.com/", ["screen", "setup"]),
    "seewo_central_control": ("https://www.seewo.com/", ["control", "setup"]),
    "seewo_preparation": ("https://www.seewo.com/", ["prepare", "setup"]),
    "seewo_cloud_classroom": ("https://www.seewo.com/", ["cloud", "setup"]),
}


def update_json(path: str, pages: dict[str, tuple[str, list[str]]]) -> None:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        sid = item.get("id")
        if sid not in pages:
            continue
        page_url, patterns = pages[sid]
        # 如果已经有直链（以 .exe 结尾），则跳过
        existing = item.get("download_url", "")
        if existing and existing.lower().endswith(".exe"):
            print(f"[skip] {sid}: already has direct link")
            continue

        try:
            print(f"[fetch] {sid}: {page_url}")
            html = fetch_text(page_url)
            url = find_exe_url(html, page_url, patterns)
            if url:
                item["download_url"] = url
                print(f"[ok]  {sid}: {url}")
            else:
                print(f"[warn] {sid}: no exe url found")
        except Exception as e:
            print(f"[err] {sid}: {e}")
        time.sleep(0.5)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(root, "assets")

    update_json(os.path.join(assets_dir, "software.json"), SOFTWARE_PAGES)
    update_json(os.path.join(assets_dir, "teaching_tools.json"), TEACHING_PAGES)

    print("Done.")


if __name__ == "__main__":
    main()
