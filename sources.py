"""
已核实的信息源清单(2026-08-13调研,见memory: project_daily_digest_agent；2026-08-15调整过
Naval/Karpathy/Dalio三人的具体渠道，见各条目日期备注)。
type: blog / youtube / podcast
X源(Amanda Askell, Andrej Karpathy, Ray Dalio)见下面的X_SOURCES，走单独的抓取路径
(fetch_x.py，用TwitterAPI.io)，不跟feedparser混在一起处理。

加新信源前必须核实一手账号身份，不能只测RSS/URL技术上能不能用——踩过的真坑：
`navalsarchive.substack.com`域名看着像本人，实际是第三方粉丝解读账号("Naval's writings,
explained")，内容是对纳瓦尔的分析转述，不是他本人写的。已经改用他真正的官方渠道`nav.al`。
核实方法：查目标网站/账号的"About"页面，查有没有本人在其他已验证渠道(比如X)自认这个账号/网站。
"""

SOURCES = [
    {"person": "Naval Ravikant", "type": "blog", "name": "Naval (官网文章 nav.al)",
     "url": "https://nav.al/feed?cat=-6"},

    {"person": "Naval Ravikant", "type": "podcast", "name": "Naval (官方播客 nav.al)",
     "url": "https://nav.al/feed?cat=6"},

    {"person": "Lex Fridman", "type": "podcast", "name": "Lex Fridman Podcast",
     "url": "https://lexfridman.com/feed/podcast/"},

    {"person": "Andrew Huberman", "type": "youtube", "name": "Andrew Huberman (YouTube)",
     "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC2D2CMWXMOVWx7giW1n3LIg"},

    {"person": "Maggie Appleton", "type": "blog", "name": "Maggie Appleton",
     "url": "https://maggieappleton.com/rss.xml"},

    {"person": "Craig Mod", "type": "blog", "name": "Craig Mod",
     "url": "https://craigmod.com/index.xml"},

    {"person": "Andy Matuschak", "type": "blog", "name": "Andy Matuschak",
     "url": "https://andymatuschak.org/feed.xml"},

    {"person": "Jason Fried", "type": "blog", "name": "Jason Fried (HEY World)",
     "url": "https://world.hey.com/jason/feed.atom"},

    {"person": "kepano", "type": "blog", "name": "kepano (Steph Ango)",
     "url": "https://stephango.com/feed.xml"},

    {"person": "Ethan Mollick", "type": "blog", "name": "Ethan Mollick (One Useful Thing)",
     "url": "https://www.oneusefulthing.org/feed"},

    {"person": "Simon Willison", "type": "blog", "name": "Simon Willison",
     "url": "https://simonwillison.net/atom/everything/"},
]

# AI实操track候选,难度更高/暂缓加入(2026-08-13讨论,坡度太陡先不上):
#   Latent Space     - https://www.latent.space/feed                偏难,默认工程师听众
#   Nathan Lambert(Interconnects) - https://www.interconnects.ai/feed  研究级别,最难
# Mollick+Willison这两条线跟得顺、觉得不够吃了,再考虑往上加。

# X源(2026-08-15新增，2026-08-15追加Karpathy改为仅X、Dalio切到X)。
# 用TwitterAPI.io抓，后面可能继续扩大——扩大时直接往这个list加条目就行。
X_SOURCES = [
    {"person": "Amanda Askell", "x_username": "AmandaAskell"},
    {"person": "Andrej Karpathy", "x_username": "karpathy"},
    {"person": "Ray Dalio", "x_username": "RayDalio"},
    {"person": "Andy Matuschak", "x_username": "andy_matuschak"},
]
