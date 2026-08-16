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
python3 fetch_x.py
```

按guid去重，只会新增之前没见过的条目。`fetch_x.py`抓`sources.py`里`X_SOURCES`那几个人的最新推文(目前Amanda Askell、Andrej Karpathy)，需要环境变量`TWITTERAPI_IO_KEY`(本地`.env`里有，CI在repo secrets里配)。

### 2. 读取待排序条目

```bash
python3 scripts/rank_items.py pending
```

输出JSON数组，每条含 `guid/person/source_name/source_type/title/link/published/summary`，外加两个路由标记(算好的，不用自己判断)：`deep_read_eligible`(要不要在medium/high时抓全文精判)、`always_summarize`(不管tier都要写摘要)。这个查询已经自动过滤了历史归档内容(`config.py`里的`DIGEST_START_DATE`之前的，永远不展示，不用排)和`ranked_at`不为空的(已经排过序的)。

如果返回空数组，说明没有新内容，直接跳到步骤5(仍建议跑一次export脚本，无害)。

如果条目很多(比如第一次跑或者积压了几周)，分批处理，每批30~50条，避免一次读入太多。

### 3. 两段式判断——读 `RANKING_CRITERIA.md` 获取判断标准，这里只列执行步骤

对每一条pending条目：

**初筛**(只用title+summary，不抓取任何东西)：按`RANKING_CRITERIA.md`里Track 1(AI实操/趋势)和Track 2(thought-lab锚点)的标准，给出初步`ai_tier`/`ai_reason`/`anchor_tier`/`anchor_reason`。Track 2判断前，先重新读一遍`/Users/taoye/claude/thought-lab/now/关注锚点清单.md`(这份清单用户自己维护，可能会变)。

**精判**(按pending输出里的路由标记执行，不用自己重新判断走哪条路径)：
- `deep_read_eligible == true` 且初筛任一track是`medium`或`high` → 用WebFetch工具抓一次`link`的全文，基于全文重新判断该track的tier(可以推翻初筛结果)，并写一段`digest_summary`(内容概要+核心观点，2~4句，不是摘录)。全文读完就丢，不要写入任何文件、不要存进结果JSON。
- `deep_read_eligible == false`(podcast/youtube/x)且初筛任一track是`medium`/`high` → 不追加抓取，基于已有的`summary`字段写一段轻提炼作为`digest_summary`。X的`summary`是英文推文原文，写成中文概要(1~2句)，不要照抄英文。
- `always_summarize == true`(X，或标题带`[RIDGELINE]`前缀的Craig Mod文章) → 不管`ai_tier`/`anchor_tier`判成什么，都要写中文`digest_summary`。X是"7日内关注"页"X动态"板块不管tier全展示；Ridgeline是用户明确说很喜欢、不想被判断结果筛掉，全部永久展示(见`config.ALWAYS_ARCHIVE_TITLE_PREFIXES`)。这类如果`deep_read_eligible`也是true(Ridgeline是blog类型，是)但初筛两个track都`low`，不用额外WebFetch全文，直接基于已有`summary`写轻提炼即可，跟podcast/youtube走同样的轻量路径。
- 其余情况(`deep_read_eligible == false`且两个track都`low`且`always_summarize == false`) → 维持low，`digest_summary`留空(null)。

### 4. 写回数据库

把每条的判断结果整理成JSON数组(格式见`scripts/rank_items.py`文件头注释)，写到一个临时文件(比如`/tmp`或scratchpad目录)，然后:

```bash
python3 scripts/rank_items.py write <临时文件路径>
```

### 5. 导出前端数据

```bash
python3 export_json.py
python3 export_recent.py
```

`export_json.py`导出月度归档(`docs/digest.html`用，只归档high档)，`export_recent.py`导出最近7天动态(`docs/index.html`"7日内关注"页的"AI实操/趋势"+"关注锚点"+"X动态"三个板块用)——**两个都要跑**，漏了`export_recent.py`该页面会拿不到数据。

### 6. 提交并推送

```bash
git add digest.db docs/data/
git commit -m "Daily digest: 排序N条新内容"
git push
```

**交互式session里手动跑这份skill时**：commit可以直接做，但push前照常按assistant的risky-action政策跟用户确认一句(哪怕这个仓库是digest专用、blast radius小)。
**`/schedule`云端routine执行时**：这一步就是自动化的意义所在，直接push，不需要暂停确认。

## 输出总结

跑完后用一两句话汇报：新抓到几条、排出了几个high/medium(分track)、有没有encountered需要人工看一眼的情况(比如某个源RSS挂了、某条链接WebFetch失败)。
