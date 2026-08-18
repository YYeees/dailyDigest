"""
把RSS entry里的正文抽成入库用的纯文本。

2026-08-18实测latent.space/feed发现的事实(其他源同理，只是量级不同)：
- 一半的源RSS里压根没有`content`字段(Simon Willison/Craig Mod/Lex/Huberman/Andy Matuschak)，
  这些源永远只能靠WebFetch抓原文。
- 有`content`的源，RSS里给的**就是全文**——现在的流程却只记了个`has_full_text`标记就把正文
  扔了，精判时再去WebFetch同一个链接，等于把已经拿到的东西重新下载一遍，而且抓回来的网页
  比RSS正文还大(多了导航/推荐位/评论)。
- `summary`字段不是摘要，是**副标题**(latent.space只有16~183字符)，所以初筛基本等于只看标题。

两条压缩规则(实测20条latent.space内容，480K字符→96K，省80%)：
1. `[AINews]`那种每日新闻汇总，正文结构固定：编者按 → AI Twitter Recap → AI Reddit Recap →
   AI Discord Recap。后面三个Recap是机器聚合的社媒原文，占全文80~99%的字数，对"这条值不值得
   读"几乎零信息量(极端例子：Cursor收购那条全文41055字符，编者按只有478)。切到第一个Recap
   小标题为止。
2. 其余内容整篇留下，但设CONTENT_CHAR_CAP上限——播客集数偶尔带完整转录稿(实测有一条133K
   字符)，不截会把一条内容的成本抬到其他条目的十倍。

存纯文本而不是原始HTML：判断优先级不需要标记，去掉标签能省一半以上体积；但保留小标题(`## `)
和列表(`- `)这两层结构，正文的层次对判断有用。
"""

import re
from html import unescape

from config import CONTENT_CHAR_CAP

# Substack给每条RSS都追加的"Read more"页脚链接，不是正文
_SUBSTACK_FOOTER = re.compile(r"(?is)\s*<p>\s*<a[^>]*>\s*Read\s+more\s*</a>\s*</p>\s*$")

# AINews正文里三个机器聚合板块的小标题，实际长成 <h1><strong>AI Twitter Recap</strong></h1>
_RECAP_CUT = re.compile(r"(?is)<h[1-6][^>]*>\s*(?:<strong>\s*)?AI\s+(?:Twitter|Reddit|Discord)\s+Recap")

_AINEWS_PREFIX = "[AINews]"


def html_to_text(html):
    """去标签，但把小标题压成`## `、列表项压成`- `，保留正文的层次。"""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    s = re.sub(r"(?i)<h[1-6][^>]*>", "\n\n## ", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n- ", s)
    s = re.sub(r"(?i)<(?:br|/p|/div|/h[1-6]|/tr|/blockquote)[^>]*>", "\n", s)  # 不含</li>：<li>已经换过行了
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_body(title, entry, cap=CONTENT_CHAR_CAP):
    """RSS entry → 入库用的正文纯文本。源没给正文时返回None(这类只能靠WebFetch)。"""
    contents = entry.get("content") or []
    raw = contents[0].get("value") or "" if contents else ""
    if not raw.strip():
        return None
    raw = _SUBSTACK_FOOTER.sub("", raw)
    if title.startswith(_AINEWS_PREFIX):
        cut = _RECAP_CUT.search(raw)
        if cut:
            raw = raw[:cut.start()]
    return html_to_text(raw)[:cap] or None


def is_truncated(body):
    """RSS给的正文是不是被源截断了(付费墙/预览)——这类才真的需要去抓原文。

    实测latent.space 20条里只有1条是这样(正文223字符，以`…`收尾)。判据同时看长度和省略号：
    只看长度会把`[AINews] not much happened today`这种真的很短的误判成截断。
    """
    if not body:
        return True
    return body.rstrip().endswith(("…", "...")) or len(body) < 500
