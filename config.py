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
HIGH_ONLY_PERSONS = {"Simon Willison"}
HIGH_ONLY_PERSON_LIMIT = 7

# GitHub Trending展示数量上限(2026-08-15定案)：不用展示太多，只要综合最值得推荐的。
TRENDING_DAILY_LIMIT = 6    # index.html"7日内关注"页Trending板块
TRENDING_MONTHLY_LIMIT = 6  # digest.html月度归档"GitHub高分项目"板块，每月上限

# daily_snapshots表的保留窗口(2026-08-16定案)：前端只读每个仓库最新一条快照，更早的
# 历史快照没有展示价值，超过这个天数就清理，避免表无限增长。
SNAPSHOT_RETENTION_DAYS = 180
