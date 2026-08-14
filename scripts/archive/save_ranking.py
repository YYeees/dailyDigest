"""
[归档] 2026-08-13的一次性人工校准记录,不是pipeline的一部分,不会被日常流程调用。
把这次人工校准的排序结果写回digest.db。
JUDGMENTS里没提到的guid，默认按 low/low 处理（且都算已排序，ranked_at写当前时间）。
这不是最终的自动化排序脚本 —— 这是"人工跑一遍、验证校准方向"的记录，
体现出的判断标准已经固化进RANKING_CRITERIA.md。真正的日常流程见
scripts/rank_items.py + .claude/skills/run-digest/。
"""

import sqlite3
from datetime import datetime, timezone

JUDGMENTS = {
    # ai_tier, ai_reason, anchor_tier, anchor_reason
    "Andrew Huberman (YouTube)::yt:video:N5AQFYtqx8Q": (
        "high", "AI科学家（Fei-Fei Li）访谈，内容扎实且不需要技术背景", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/12/deepseek-v4-pro-0813/": (
        "high", "前沿模型新发布，趋势追踪", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/8/auto-mode/": (
        "high", "直接影响日常用Claude Code的方式，实操性强", "low", ""),
    "Ethan Mollick (One Useful Thing)::https://www.oneusefulthing.org/p/an-opinionated-guide-to-which-ai-b22": (
        "high", "最贴合当前水平的AI工具选型实操指南", "low", ""),

    "Simon Willison::https://simonwillison.net/2026/Aug/9/claude-opus-5-system-prompt/": (
        "medium", "前沿模型行为细节，略技术但有启发", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/7/pdfs-are-terrible/": (
        "medium", "行业趋势：企业AI支出降温", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/4/new-release-of-llm/": (
        "medium", "他自己的LLM命令行工具重大更新，实用但工具依赖性强", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/5/incident-report/": (
        "medium", "AI agent安全事故系列报道之一，趋势性强略专业", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/5/third-party-cyber-evaluations/": (
        "medium", "AI agent安全事故系列报道之一", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/5/an-ai-model-from-meta/": (
        "medium", "AI agent安全事故系列报道之一", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/8/now-we-have-a-timeline-of-the-openai-accidental-attack-against-h/": (
        "medium", "AI agent安全事故系列报道，与8/7那条重复，择一看即可", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/10/introducing-muse-glimmer/": (
        "medium", "Meta开源模型动态", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/5/muse-code-and-muse-spark-12/": (
        "medium", "Meta开源模型动态", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/5/raccoon-heist/": (
        "medium", "编程agent实战小案例，直观好懂", "low", ""),
    "Simon Willison::https://simonwillison.net/2026/Aug/7/moonlight-mayhem/": (
        "medium", "编程agent实战小案例，跟上一条同系列", "low", ""),
    "Principles by Ray Dalio::yt:video:2MEmlCl87QQ": (
        "medium", "他自己做AI数字分身，轻量但有趣", "low", ""),
    "Naval (官方播客 nav.al)::https://nav.al/?p=28497007": (
        "medium", "创业者视角聊AI／未来，偏宏观不算实操", "low", ""),

    "Craig Mod::https://craigmod.com/essays/robot_blood/": (
        "medium", "用LLM做基因谱系寻亲，真实创造性应用案例",
        "high", "AI作为认知方式加深度自我认识（身份／收养）双命中，一手经历"),
    "Craig Mod::https://craigmod.com/roden/117/": (
        "low", "", "high", "上一篇的后续，同一脉络"),
    "Maggie Appleton::https://maggieappleton.com/in-memoriam/": (
        "low", "", "high", "透过历史追问人如何承受苦难，一手反思写作"),
    "Jason Fried (HEY World)::tag:world.hey.com,2005:World::Post/48607": (
        "low", "", "high", "质朴中正、护城河在harness不在模型，同派构建者视角"),

    "Craig Mod::https://craigmod.com/roden/116/": (
        "low", "", "medium", "质朴慢生活反思"),
    "Craig Mod::https://craigmod.com/ridgeline/231/": (
        "low", "", "medium", "匠人活法，周边主题"),
    "Andrew Huberman (YouTube)::yt:video:LQI8tl8S2PE": (
        "low", "", "medium", "冥想／意识话题，沾自我认识的边"),
    "Lex Fridman Podcast::https://lexfridman.com/?p=6474": (
        "low", "", "medium", "历史学家对话，历史镜头看人如何自处"),

    "Simon Willison::https://simonwillison.net/2026/Aug/11/stealing-reasoning-traces/": (
        "low", "研究级别技术细节，当前坡度先不推", "low", ""),
    "Lex Fridman Podcast::https://lexfridman.com/?p=6494": (
        "low", "主题（格斗／体育）跟AI和锚点都不沾边", "low", ""),
}

# Simon Willison的个人工具changelog类，批量标注低优先级（不逐条写理由）
WILLISON_CHANGELOG_NOISE = [
    "Simon Willison::https://simonwillison.net/2026/Aug/12/alchemy-utils/",
    "Simon Willison::https://simonwillison.net/2026/Aug/6/datasette-auth-tokens/",
    "Simon Willison::https://simonwillison.net/2026/Aug/6/datasette/",
    "Simon Willison::https://simonwillison.net/2026/Aug/6/datasette-2/",
    "Simon Willison::https://simonwillison.net/2026/Aug/11/datasette-upload-dbs/",
    "Simon Willison::https://simonwillison.net/2026/Aug/4/llm-anthropic/",
    "Simon Willison::https://simonwillison.net/2026/Aug/4/llm/",
    "Simon Willison::https://simonwillison.net/2026/Aug/9/sqlite-text-history-prototype/",
    "Simon Willison::https://simonwillison.net/2026/Aug/4/minimax-h3-mlx/",
    "Simon Willison::https://simonwillison.net/2026/Aug/8/john-gruber/",
    "Simon Willison::https://simonwillison.net/2026/Aug/6/simon-willison-on-technical-blogging/",
    "Simon Willison::https://simonwillison.net/2026/Aug/12/florian-herrengt/",
    "Simon Willison::https://simonwillison.net/2026/Aug/11/there-are-no-lossless-transformations-of-natural-language-text/",
    "Simon Willison::https://simonwillison.net/2026/Aug/7/openai-timeline/",
]
for g in WILLISON_CHANGELOG_NOISE:
    JUDGMENTS[g] = ("low", "个人工具changelog，对学AI实操无普适价值", "low", "")


def main():
    conn = sqlite3.connect("digest.db")
    now = datetime.now(timezone.utc).isoformat()

    # 先把明确判断过的写进去
    for guid, (ai_tier, ai_reason, anchor_tier, anchor_reason) in JUDGMENTS.items():
        conn.execute(
            """UPDATE items SET ai_tier=?, ai_reason=?, anchor_tier=?, anchor_reason=?, ranked_at=?
               WHERE guid=?""",
            (ai_tier, ai_reason, anchor_tier, anchor_reason, now, guid),
        )

    # 剩下7月以来、还没排过序的，一律按low/low处理（没被单独挑出来，说明双track都不沾）
    conn.execute(
        """UPDATE items SET ai_tier='low', anchor_tier='low', ranked_at=?
           WHERE published >= '2026-07-01' AND ranked_at IS NULL""",
        (now,),
    )
    conn.commit()

    cur = conn.execute("SELECT COUNT(*) FROM items WHERE ranked_at = ?", (now,))
    print(f"本次共标注 {cur.fetchone()[0]} 条")
    conn.close()


if __name__ == "__main__":
    main()
