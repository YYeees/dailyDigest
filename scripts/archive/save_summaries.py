"""
[归档] 2026-08-13的一次性人工校准记录,不是pipeline的一部分,不会被日常流程调用。
把high档条目的digest_summary写回digest.db。
全文只在生成这些摘要的过程中被临时读取（WebFetch），不落盘——本文件里只有生成好的摘要文本。
真正的日常流程见scripts/rank_items.py + .claude/skills/run-digest/。
"""

import sqlite3

SUMMARIES = {
    "Craig Mod::https://craigmod.com/essays/robot_blood/":
        "Craig Mod分享用LLM做的一系列创新应用，核心是这次用Claude做家谱寻根——从零散线索追出自己的身世。他认为LLM最大价值在于"
        "把复杂信息检索转化为人性化的结果呈现，这类工具正处于应用爆发初期，价值被低估，关键是亲身体验而非跟风议论。",

    "Craig Mod::https://craigmod.com/roden/117/":
        "这期newsletter介绍了上面那篇四千字长文的写作过程与后续：他用Claude追踪到一篇尘封旧报纸，发现自己出生证明上的中间名"
        "竟源于一位几十年前意外身亡的陌生人。另外还提到摄影集《事物变成其他事物》精装第二版开放预订。",

    "Jason Fried (HEY World)::tag:world.hey.com,2005:World::Post/48607":
        "Jason Fried用厨房与餐食、蓝图与建筑作比喻，论证一个核心观点：开发速度、commit数量这些生产过程指标，说不出产品本身的"
        "质量和体验好不好。不要把「怎么做出来的」和「做出来的东西好不好」混为一谈。",

    "Maggie Appleton::https://maggieappleton.com/in-memoriam/":
        "作者读小说《In Memoriam》补上了对一战的认知空白——基于大量一手史料的历史虚构，呈现堑壕战里士兵在泥浆、尸体与机枪"
        "火力中大规模死亡的真实图景。她用约九千五百朵罂粟花对应九百五十万军人死亡，并由此联想到气候变化、AI风险这类当代的「工业规模威胁」。",

    "Ethan Mollick (One Useful Thing)::https://www.oneusefulthing.org/p/an-opinionated-guide-to-which-ai-b22":
        "二〇二六夏季版AI工具选型指南。核心判断：AI已经从聊天工具进化成能自主干几个小时活的「代理系统」。日常需求用免费模型就够，"
        "医疗、法律这类高风险决策要上Claude Opus／Fable或GPT-5.6 Sol这类最强模型。最实用建议：每月二十美元订阅一个，把AI当团队"
        "成员管，给它权限、设安全检查点，像带新人一样持续调教。",

    "Simon Willison::https://simonwillison.net/2026/Aug/12/deepseek-v4-pro-0813/":
        "DeepSeek发布V4 Pro 0813，目前只开放API访问。一个有意思的细节：这个模型在低／中／高不同推理强度下生成的图像差异很明显，"
        "这在其他模型里比较少见。",

    "Simon Willison::https://simonwillison.net/2026/Aug/8/auto-mode/":
        "Anthropic把Claude Code的auto mode设成Pro、Max、Team计划的默认选项。第三方评估显示auto mode拦截有害操作的表现很强——"
        "七百二十次针对性攻击尝试全部被挡下，远超人工审核。作者仍提醒提示注入这类风险需要独立验证，别照单全收。",

    "Andrew Huberman (YouTube)::yt:video:N5AQFYtqx8Q":
        "Huberman对话斯坦福AI学者Fei-Fei Li，聊AI怎么安全地增强人类智力和创造力，而不只是搜索信息。两人讨论了AI与人类认知"
        "的本质区别、直觉和个人经验为什么难以被AI复制，以及AI加人机协作对健康和科研的正向可能性。",
}


def main():
    conn = sqlite3.connect("digest.db")
    for guid, summary in SUMMARIES.items():
        cur = conn.execute(
            "UPDATE items SET digest_summary=? WHERE guid=?", (summary, guid)
        )
        if cur.rowcount == 0:
            print(f"[WARN] 没匹配到: {guid}")
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM items WHERE digest_summary IS NOT NULL"
    ).fetchone()[0]
    print(f"digest_summary 已写入 {n} 条")
    conn.close()


if __name__ == "__main__":
    main()
