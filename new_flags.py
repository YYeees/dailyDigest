"""
"刚更新"高亮的判定：一条内容是不是**这次导出**才第一次出现在网站上。

时间戳比较这条路已经走到头了，三种都试过、三种都有问题：
- 按日历日比对(UTC/北京/美国时区都试过)——日历日边界一过，前一天还亮着的高亮突然消失。
- 按first_seen的滚动小时窗口(26小时)——窗口横跨了两次抓取，昨天早上见过的内容第二天
  早上还亮着(2026-08-18踩到：8-16晚上收录的Qwen那条，8-17、8-18连着两个早上都是高亮，
  到了8-18中午窗口过期又自己灭了)。
- 而且first_seen根本不等于"上站时间"：8-17中午本地抓到的22条一直到8-18早上那次run才排完
  序上站，对用户来说它们就是8-18的新内容，跟抓到的时刻是哪天无关。

所以不比时间，直接跟上一份导出结果比：这次有、上次没有的，就是新的。判断在导出时算死，
写进JSON的`is_new`字段，前端只读这个字段、不做任何时间运算——页面什么时候打开高亮都一样，
一次更新到下一次更新之间不会自己变。

例外：这次导出如果一条都没新增(抓取没抓到东西，或者只是手动重跑一遍export脚本)，原样保留
上一份的高亮——重跑一次导出脚本不该让刚上站的内容失去高亮。
"""

import json
from pathlib import Path


def load_prev_items(path, field="items"):
    """读上一份导出结果里的条目列表。文件不存在/损坏都当成空(首次导出)。"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get(field) or []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def mark_new(items, prev_items, key="link"):
    """给items逐条打上`is_new`。原地修改并返回items。"""
    prev = {i.get(key): i for i in prev_items}
    has_additions = any(i.get(key) not in prev for i in items)
    for item in items:
        if has_additions:
            item["is_new"] = item.get(key) not in prev
        else:
            # 这次没新增任何条目——沿用上一份的高亮，别把它清空
            item["is_new"] = bool(prev.get(item.get(key), {}).get("is_new"))
    return items
