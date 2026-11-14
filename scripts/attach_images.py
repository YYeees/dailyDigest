"""
给 docs/data/recent.json 的每一条补一张配图(image 字段)，Recent 页卡片右侧用。

2026-11-14 加：Recent 页改成跟「大公司」页同一种卡片后，用户觉得没有图"看着干枯"。
- 只给等级为 HIGH 的条目配图(页面上也只有 HIGH 显示图)
- YouTube：直接用视频缩略图(i.ytimg.com)，不用请求
- 其他：抓文章页的 og:image(复用 export_companies.py 的抓取函数，openai.com 那种拒绝脚本的站跳过)
- 抓到的按 link 缓存在 docs/data/image_cache.json，每篇只抓一次；没抓到的下次再试

跑在 export_recent.py 之后(它会整份重写 recent.json)：每日跑批里放在 Claude 那步后面的导出步骤。
公开站按白名单导出，不带 image 字段，不受影响。
"""

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from export_companies import fetch_og_image  # noqa: E402

RECENT = ROOT / "docs" / "data" / "recent.json"
CACHE = ROOT / "docs" / "data" / "image_cache.json"
YT_ID = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})")


def image_for(link):
    m = YT_ID.search(link or "")
    if m:
        return f"https://i.ytimg.com/vi/{m.group(1)}/hqdefault.jpg"
    return fetch_og_image(link)


def main():
    data = json.loads(RECENT.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    fetched = found = 0
    for item in data.get("items", []):
        link = item.get("link")
        if not link:
            continue
        # 页面只给 HIGH 放配图(2026-11-14)，别的不用抓。等级取三条轨道里最高的那个，跟页面一致
        if "high" not in (item.get("tiers") or {}).values():
            item.pop("image", None)
            continue
        if link not in cache:
            img = image_for(link)
            fetched += 1
            if img:
                cache[link] = img
            if "youtube" not in link and "youtu.be" not in link:
                time.sleep(0.3)   # 别一口气打太密
        if cache.get(link):
            item["image"] = cache[link]
            found += 1
    RECENT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # 缓存只留最近还在用的，免得无限变大
    live = {i.get("link") for i in data.get("items", [])}
    CACHE.write_text(json.dumps({k: v for k, v in cache.items() if k in live}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"[OK] recent.json 配图 — {found}/{len(data.get('items', []))} 条有图，这次新抓 {fetched} 次")


if __name__ == "__main__":
    main()
