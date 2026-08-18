"""
跨脚本共享的常量和路由规则。

加/改规则改这里，不要去改RANKING_CRITERIA.md/GITHUB_TRENDING_CRITERIA.md里的散文描述——
那两份文档只负责"怎么判断内容质量高低"这种需要理解力、没法写成规则的标准；
"这条内容该走哪条处理路径"这种机械分支逻辑，维护在这里。
"""

DB_PATH = "digest.db"

# 月份选择器起始范围(2026-08-13定案)：更早的历史归档内容永远不展示，不需要排序。
DIGEST_START_DATE = "2026-07-01"

# index.html"最新"页面的滚动窗口天数：AI实操/关注锚点两个track展示这个窗口内的high+medium，
# X动态板块展示这个窗口内的全部内容(不限tier)。
RECENT_WINDOW_DAYS = 7

VALID_TIERS = {"high", "medium", "low"}
VALID_DIFFICULTY = {"beginner", "intermediate", "advanced"}
VALID_WORTH_TIER = {"high", "medium", "low"}

# 两段式判断的路由规则(原本是RANKING_CRITERIA.md里的散文段落，2026-08-15移进代码)。
# 初筛(标题+摘要)得到medium/high后，只有这些source_type才会再WebFetch全文做精判。
# 这些source_type在"库里没有正文"时**可以**去WebFetch原文抓一次(podcast/youtube/x没有原文
# 可抓，只能用summary轻提炼)。注意语义：不是"要不要抓"，是"抓不到正文时能不能抓"——
# RSS里已经带正文的条目不管什么type都不再抓，判定见rank_items.py的body_source。
DEEP_READ_ELIGIBLE_TYPES = {"blog"}

# 不管ai_tier/anchor_tier判成什么，这些source_type每条都要写digest_summary
# (X：用户要的是"知道更新了、大概聊了什么"，不是被tier过滤掉的精选)。
ALWAYS_SUMMARIZE_TYPES = {"x"}

# "最新"页面里，这些source_type不管tier全部展示(用紧凑样式，跟AI实操/锚点的大卡片分开)。
ALWAYS_DISPLAY_TYPES = {"x"}

# 内容归档/展示的统一规则(2026-08-15定案，替代之前的flow/feature分类)：
# - high档：不管来源，永久进月度归档
# - medium档：不管来源，只在RECENT_WINDOW_DAYS内的"最新"页面展示，不归档
# - 例外：HIGH_ONLY_PERSONS里的人，medium档也不在"最新"页面展示(更新太勤，medium量太大)，
#   且他们的展示条目数额外设上限(HIGH_ONLY_PERSON_LIMIT)，避免一个人占满整个板块。
# - 2026-08-16再加一层例外：HIGH_ONLY_PERSONS里的人，发布在HIGH_ONLY_RECENT_DAYS天以内的
#   内容不分tier全部展示(哪怕low)——用户想看到他最新的动态，不想被判断结果挡住；超过这个
#   窗口(但仍在RECENT_WINDOW_DAYS内)才收紧回"只看high档"。
HIGH_ONLY_PERSONS = {"Simon Willison"}
HIGH_ONLY_PERSON_LIMIT = 7
HIGH_ONLY_RECENT_DAYS = 1

# Craig Mod的Ridgeline newsletter——用户明确说很喜欢，不想被ai_tier/anchor_tier的判断结果
# 筛掉(2026-08-16定案)：不管判成什么档，都要写digest_summary，且不受"只有high档才永久归档"/
# "medium档只在7天窗口展示"这两条规则限制，全部永久展示。craigmod.com/index.xml这个feed本身没有
# 分类字段，只能靠标题前缀"[RIDGELINE]"识别——同一个feed里的Roden/Essays newsletter前缀不同，
# 不在这条例外范围内。
ALWAYS_ARCHIVE_TITLE_PREFIXES = {"[RIDGELINE]"}

# GitHub Trending展示数量上限(2026-08-15定案)：不用展示太多，只要综合最值得推荐的。
TRENDING_DAILY_LIMIT = 6    # index.html"7日内关注"页Trending板块
TRENDING_MONTHLY_LIMIT = 6  # digest.html月度归档"GitHub高分项目"板块，每月上限

# daily_snapshots表的保留窗口(2026-08-16定案)：前端只读每个仓库最新一条快照，更早的
# 历史快照没有展示价值，超过这个天数就清理，避免表无限增长。
SNAPSHOT_RETENTION_DAYS = 180
CONTENT_CHAR_CAP = 30000  # 单条正文入库上限，见content_extract.py文件头

# [AINews]切到第一个Recap小标题后，编者按短于这个长度就认为切过头了(实测最短的只有478字符)，
# 退回去取全文的前AINEWS_FLOOR_CHARS字符，保证初筛手里至少有判断依据。
AINEWS_MIN_CHARS = 1000
AINEWS_FLOOR_CHARS = 4000

# 一次`rank_items.py pending --with-content`最多吐这么多字符的正文。稳态下一天的正文才~11K，
# 这个预算用不到；但新增信源那天会一次回填几十条(实测22条×最多30K=660K)，超预算的条目退回
# body_source="fetch"走老路径,避免一次pending把上下文撑爆。想全量拿就配合--limit分批。
PENDING_CONTENT_BUDGET = 200000
