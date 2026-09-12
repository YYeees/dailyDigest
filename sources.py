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

    {"person": "Latent Space", "type": "blog", "name": "Latent Space (swyx & Alessio)",
     "url": "https://www.latent.space/feed"},

    {"person": "Hamel Husain", "type": "blog", "name": "Hamel Husain (hamel.dev)",
     "url": "https://hamel.dev/index.xml"},

    {"person": "Martin Fowler", "type": "blog", "name": "Martin Fowler",
     "url": "https://martinfowler.com/feed.atom"},

    {"person": "NN/g", "type": "blog", "name": "NN/g (Nielsen Norman Group)",
     "url": "https://www.nngroup.com/feed/rss/"},

    {"person": "Amelia Wattenberger", "type": "blog", "name": "Amelia Wattenberger",
     "url": "https://wattenberger.com/rss.xml"},

    {"person": "Maaret Pyhäjärvi", "type": "blog", "name": "Maaret Pyhäjärvi (Visible Quality)",
     "url": "https://visible-quality.blogspot.com/feeds/posts/default"},

    {"person": "Antithesis", "type": "blog", "name": "Antithesis (自主测试/确定性仿真)",
     "url": "https://antithesis.com/blog/rss.xml"},

    {"person": "Ministry of Testing", "type": "blog", "name": "Ministry of Testing Club(论坛)",
     "url": "https://club.ministryoftesting.com/latest.rss"},
]
# 2026-09-12第二批，全部服务eval track(AI怎么改造测试这门手艺)，同样实测过再选：
#   Maaret Pyhäjärvi 8条/90天。芬兰的一线测试员，她在真拿自己的工作做实验而不是评论AI
#     ("Why would I even want to generate test cases with AI?""Benchmarking results -
#     Human, Human with AI, AI with Human")。标题AI密度只有12%，别用关键词密度误判。
#   Antithesis 5条/90天。做确定性仿真测试(deterministic simulation testing)/自主找bug，
#     跟"让LLM帮我写测试用例"是完全不同的创新轴，更底层。标题AI密度3%是误判——
#     "Breaking the WAL""Finding bugs in Raft implementations"讲的就是自动化找bug本身。
#     这是厂商博客但技术含量高，不是营销稿。
#   Ministry of Testing 30条/90天，AI密度33%("Is agentic AI testing real?""AI assisted
#     testing""What are the signs that a QA manager is AI pilled")。
#     **注意这是Discourse论坛的latest feed，不是文章**：每条是个帖子，主楼往往很短、
#     精华在回帖里(管线抓全文只拿得到主楼)，而且混着"个人求职困惑"这类跟主题无关的帖。
#     它给的是行业脉搏不是分析，预期是"淘"不是"读"——判tier时别因为它来自测试社区就抬手。
#     哪天觉得噪音受不了，第一个撤它。
#
# 实测拒掉的(留个记录，免得以后重复调研)：
#   Software Testing Weekly —— 周刊还活着(12条/90天)，但标题全是"Issue #326"，初筛只看
#     title+summary必然判low，永远触发不了全文精判，结构上跟这套管线冲突。
#   Kent Beck(tidyfirst.substack.com) —— 15条/90天但AI密度只有5%，内容飘到经济学隐喻
#     ("Busy is Short Volatility")，不再是当年那个讲TDD的他。
#   Dave Farley博客停更1372天(转YouTube了)、Alan Page停更547天、Google Testing Blog
#     1条/90天且完全不碰AI、Qodo/Diffblue没有可用feed、Meta Engineering全是基建不碰测试。
#   Applitools —— 11条/90天、密度33%，但一半是"How Customer Success Keeps Quality..."
#     这类营销稿，含金量不够，暂不加。
# 2026-09-12加这四个，分两个方向(用户本职是软件测试，另外对艺术设计感兴趣但没有美术功底、
# 强在审美和眼力)。全部按文件头的规矩核实过一手身份，并且实测了更新量和主题密度——机构feed
# 最容易混公关稿，光看名气会踩坑(实测拒掉的：OpenAI Blog 153条/90天全是产品公关和客户案例；
# Thoughtworks Insights 68%密度但一半是招聘和AWS联合营销；Vercel 329条/90天纯changelog)。
#
# 测试方向：
#   Hamel Husain  3条/90天，标题AI密度55%，全是evals("Do Automated Evals Work?"
#     "Evals Skills for Coding Agents")。身份核实：hamel.dev首页本人自述"machine learning
#     engineer with 20+ years"、Airbnb和GitHub出身。注意他卖evals课程、首页就挂着招生，
#     会有自我推广内容，参照Peter Steinberger那条宣发规则的思路判断。量少是优点，不刷屏。
#   Martin Fowler 27条/90天，AI密度只有12%但命中的正是交叉点("TDD inside the agent loop -
#     theater or actual value?")。身份核实：martinfowler.com/aboutMe.html本人自述，站上
#     Topics明确列着Testing。噪音是Fragments/社交媒体流水账，靠逐条判tier过滤——跟Latent
#     Space的[AINews]一个处理方式，不是抓取出错。
#
# 设计方向(选的都是"讲判断力和证据"而不是"教画工"的，用户没有美术功底)：
#   NN/g 20条/90天，AI密度45%("Using AI for UX Work: Study Guide""The Custodial Era of
#     UX: Cleaning Up After AI")。做可用性研究的机构，域名本身即身份。噪音只有UX Conference
#     的会议广告，好滤。
#   Amelia Wattenberger 1条/90天，极慢但每篇都值("Our interfaces have lost their senses"
#     "Fish eye for text")。身份核实：wattenberger.com首页本人自述"Principal Research
#     Engineer exploring novel UIs + playing with ML"、GitHub的研发小组。她标题里基本不出现
#     AI字样，别用关键词密度误判成不相关。
#
# 注意：测试类内容按RANKING_CRITERIA.md的例外要判ai_tier=low走锚点track(用户暂时不想对外
# 展示)，设计类内容天然接锚点的"人机交互/思维工具/动态媒介"这条周边领域。
# 2026-08-17加入Latent Space：Mollick的内容用户已经不觉得够吃了(基本都是已知的东西)，触发了
# 2026-08-13就定好的"往上加难度"计划。feed里summary字段很短(teaser，十几到一百多字符)，
# 归类成blog(而不是podcast)是为了让medium/high档触发WebFetch抓全文精判——按podcast
# 走轻量摘要的话，摘要质量会因为summary太短而很差。注意这个feed里混了一批[AINews]开头
# 的自动日报条目，更新频率比之前的信源明显高，属于这个feed本来的构成，不是抓取出错。

# AI实操track候选,难度更高/暂缓加入(2026-08-13讨论,坡度太陡先不上):
#   Nathan Lambert(Interconnects) - https://www.interconnects.ai/feed  研究级别,最难
# 如果Latent Space也跟得顺了,再考虑往上加。

# X源(2026-08-15新增，2026-08-15追加Karpathy改为仅X、Dalio切到X；2026-09-12加Boris Cherny、
# Peter Steinberger)。
# 用TwitterAPI.io抓，后面可能继续扩大——扩大时直接往这个list加条目就行。
#
# 2026-09-12两位按文件头的规矩核实过一手身份(查TwitterAPI.io的user/info读本人bio自认)：
#   - @bcherny  bio="Claude Code @anthropicai"，即Claude Code的作者Boris Cherny
#   - @steipete bio="Polyagentmorous ClawFather...@OpenClaw🦞 + @OpenAI"，即OpenClaw的作者
#     Peter Steinberger("ClawFather"是他自称)
X_SOURCES = [
    {"person": "Amanda Askell", "x_username": "AmandaAskell"},
    {"person": "Andrej Karpathy", "x_username": "karpathy"},
    {"person": "Boris Cherny", "x_username": "bcherny"},
    {"person": "Peter Steinberger", "x_username": "steipete"},
]
# 2026-09-12撤掉Ray Dalio(@RayDalio)和Andy Matuschak(@andy_matuschak)的X源——用户说
# "我发现我不咋点开"，是读者行为的反馈，不是这两个账号抓取有问题。
# 两点注意：
#   1. Andy Matuschak**只撤X**，他的博客(andymatuschak.org，在上面SOURCES里)照旧保留。
#      用户说的是"X里面的andy内容"，不是这个人整个不要了。
#   2. Ray Dalio撤掉后就彻底没有来源了——他2026-08-15从RSS切到过X，这是他唯一的渠道。
#      所以RANKING_CRITERIA.md里那条"Ray Dalio的X内容"排除规则也一并删了(规则针对的源
#      都没了，留着只会白占每次跑批的判断上下文)。哪天想加回来，从git history捞。
