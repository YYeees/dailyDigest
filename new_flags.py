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

"这次没新增"有两种情况，2026-08-21起分开处理(之前混在一起，导致用户看到"20号那批次没有
任何更新，界面还是把前一次的更新内容高亮着")：
- **手动重跑export脚本**(没跑抓取)——原样保留上一份的高亮。重跑一次导出不该让刚上站的
  内容失去高亮，这是`preserve_when_empty=True`(默认)。
- **完整跑了一次批，但确实没抓到新内容**——高亮全灭。"刚更新"的语义是"最近一次跑批带来的
  新东西"，这次跑批什么都没带来，就不该有任何东西亮着。走`preserve_when_empty=False`，
  由`export_recent.py --pipeline-run`传入(见run-digest skill第5步)。
"""

import json
from pathlib import Path


def load_prev_items(path, field="items"):
    """读上一份导出结果里的条目列表。文件不存在/损坏都当成空(首次导出)。"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get(field) or []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def mark_new(items, prev_items, key="link", preserve_when_empty=True):
    """给items逐条打上`is_new`。原地修改并返回items。

    preserve_when_empty: 这次一条都没新增时怎么办。True(默认,手动重跑export)=沿用上一份的
    高亮; False(完整跑了一次批)=全部灭掉。区别的理由见模块头注释。
    """
    prev = {i.get(key): i for i in prev_items}
    has_additions = any(i.get(key) not in prev for i in items)
    for item in items:
        if has_additions:
            item["is_new"] = item.get(key) not in prev
        elif preserve_when_empty:
            # 只是重跑了一遍导出脚本——沿用上一份的高亮，别把它清空
            item["is_new"] = bool(prev.get(item.get(key), {}).get("is_new"))
        else:
            # 完整跑了一次批却没带来任何新内容——上一批的高亮到此为止
            item["is_new"] = False
    return items
