---
name: run-digest
description: 跑一次完整的dailyDigest流程——抓取新内容、按RANKING_CRITERIA.md两段式判断优先级、生成摘要、导出前端JSON、提交推送。用户说"跑一下digest"、"更新digest"、"run the digest"时使用。也是/schedule云端routine应该执行的内容。
---

# Run Digest

这份skill串联dailyDigest的完整pipeline。判断本身(排优先级、写摘要)必须由执行这份skill的Claude Code现场推理完成——不能写死成代码规则，也不能改成调用单独的LLM API(见项目CLAUDE.md里的方向：排序用Claude Code本身)。

## 步骤

### 1. 抓取新内容

```bash
python3 fetch.py
```

按guid去重，只会新增之前没见过的条目。

### 2. 读取待排序条目

```bash
python3 scripts/rank_items.py pending
```

输出JSON数组，每条含 `guid/person/source_name/source_type/title/link/published/summary`。这个查询已经自动过滤了`published < 2026-07-01`的历史归档内容(永远不展示，不用排)和`ranked_at`不为空的(已经排过序的)。

如果返回空数组，说明没有新内容，直接跳到步骤5(仍建议跑一次export_json.py，无害)。

如果条目很多(比如第一次跑或者积压了几周)，分批处理，每批30~50条，避免一次读入太多。

### 3. 两段式判断——读 `RANKING_CRITERIA.md` 获取完整标准，这里只列步骤

对每一条pending条目：

**初筛**(只用title+summary，不抓取任何东西)：按`RANKING_CRITERIA.md`里Track 1(AI实操/趋势)和Track 2(thought-lab锚点)的标准，给出初步`ai_tier`/`ai_reason`/`anchor_tier`/`anchor_reason`。

**精判**(只针对满足条件的条目)：
- `source_type == "blog"` 且初筛任一track是`medium`或`high` → 用WebFetch工具抓一次`link`的全文，基于全文重新判断该track的tier(可以推翻初筛结果)，并写一段`digest_summary`(内容概要+核心观点，2~4句，不是摘录)。全文读完就丢，不要写入任何文件、不要存进结果JSON。
- `source_type` 是 `podcast`/`youtube` → 不追加抓取，直接用初筛tier定档；如果任一track是`medium`/`high`，基于已有的`summary`字段写一段轻提炼作为`digest_summary`(不用WebFetch)。
- `source_type == "blog"`且初筛两个track都是`low` → 维持low，`digest_summary`留空(null)。

Track 2判断前，先重新读一遍`/Users/taoye/claude/thought-lab/now/关注锚点清单.md`(这份清单用户自己维护，可能会变)。

### 4. 写回数据库

把每条的判断结果整理成JSON数组(格式见`scripts/rank_items.py`文件头注释)，写到一个临时文件(比如`/tmp`或scratchpad目录)，然后:

```bash
python3 scripts/rank_items.py write <临时文件路径>
```

### 5. 导出前端数据

```bash
python3 export_json.py
```

### 6. 提交并推送

```bash
git add digest.db docs/data/
git commit -m "Weekly digest: 排序N条新内容"
git push
```

**交互式session里手动跑这份skill时**：commit可以直接做，但push前照常按assistant的risky-action政策跟用户确认一句(哪怕这个仓库是digest专用、blast radius小)。
**`/schedule`云端routine执行时**：这一步就是自动化的意义所在，直接push，不需要暂停确认。

## 输出总结

跑完后用一两句话汇报：新抓到几条、排出了几个high/medium(分track)、有没有encountered需要人工看一眼的情况(比如某个源RSS挂了、某条链接WebFetch失败)。
