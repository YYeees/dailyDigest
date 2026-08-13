"""
已核实的信息源清单(2026-08-13调研,见memory: project_daily_digest_agent)。
type: blog / youtube / podcast
X (Amanda Askell, Andrej Karpathy) 暂不在此文件中 —— 走单独的X抓取路径,v2再接。
"""

SOURCES = [
    {"person": "Naval Ravikant", "type": "podcast", "name": "Naval (官方播客 nav.al)",
     "url": "https://nav.al/feed"},

    {"person": "Ray Dalio", "type": "youtube", "name": "Principles by Ray Dalio",
     "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCqvaXJ1K3HheTPNjH-KpwXQ"},

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

    {"person": "Andrej Karpathy", "type": "blog", "name": "Andrej Karpathy (Bear Blog)",
     "url": "https://karpathy.bearblog.dev/feed/"},

    {"person": "Andrej Karpathy", "type": "youtube", "name": "Andrej Karpathy (YouTube)",
     "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCXUPKJO5MZQN11PqgIvyuvQ"},

    {"person": "Ethan Mollick", "type": "blog", "name": "Ethan Mollick (One Useful Thing)",
     "url": "https://www.oneusefulthing.org/feed"},

    {"person": "Simon Willison", "type": "blog", "name": "Simon Willison",
     "url": "https://simonwillison.net/atom/everything/"},
]

# AI实操track候选,难度更高/暂缓加入(2026-08-13讨论,坡度太陡先不上):
#   Latent Space     - https://www.latent.space/feed                偏难,默认工程师听众
#   Nathan Lambert(Interconnects) - https://www.interconnects.ai/feed  研究级别,最难
# Mollick+Willison这两条线跟得顺、觉得不够吃了,再考虑往上加。
