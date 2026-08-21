---
name: run-digest
description: 跑一次完整的dailyDigest流程——抓取新内容、按RANKING_CRITERIA.md两段式判断优先级、生成摘要、导出前端JSON、提交推送。用户说"跑一下digest"、"更新digest"、"run the digest"时使用。也是/schedule云端routine应该执行的内容。
---

# Run Digest

这份skill串联dailyDigest的完整pipeline。判断本身(排优先级、写摘要)必须由执行这份skill的Claude Code现场推理完成——不能写死成代码规则，也不能改成调用单独的LLM API(见项目CLAUDE.md里的方向：排序用Claude Code本身)。

## 步骤

### 1. 抓取新内容

```bash
python3 fetch.py && python3 fetch_x.py
```

一次Bash调用把两条命令跑完，不要拆成两次调用。按guid去重，只会新增之前没见过的条目。`fetch_x.py`抓`sources.py`里`X_SOURCES`那几个人的最新推文(目前Amanda Askell、Andrej Karpathy)，需要环境变量`TWITTERAPI_IO_KEY`(本地`.env`里有，CI在repo secrets里配)。

### 2. 读取待排序条目

```bash
python3 scripts/rank_items.py pending --with-content
```

输出JSON数组，每条含 `guid/person/source_name/source_type/title/link/published/summary`，外加路由标记(算好的，不用自己判断)：

- **`body_source`** —— 这条内容的正文从哪来，直接决定走哪条路径，不用自己判断：
  - `"rss"` —— 正文已经在`content`字段里了(fetch时从RSS存的)。**不要再WebFetch这条的link**，那是把已经拿到的东西重新下载一遍，而且抓回来的网页比这个还大(多了导航/推荐位/评论)。
  - `"fetch"` —— 库里没有正文(这个源的RSS不给全文，比如Simon Willison/Craig Mod/Andy Matuschak)，初筛medium/high时去WebFetch。
  - `"none"` —— 没有全文可用(podcast/youtube/x)，只能基于`summary`轻提炼。
- `always_summarize` —— 不管tier判成什么都要写`digest_summary`。
- `content_chars` —— 库里存的正文长度，参考用。

`summary`字段对多数源来说只是**副标题**(latent.space只有16~183字符)，不是摘要——所以`body_source`是`"rss"`时以`content`为准判断，别被短得离谱的summary带偏。这个查询已经自动过滤了历史归档内容(`config.py`里的`DIGEST_START_DATE`之前的，永远不展示，不用排)和`ranked_at`不为空的(已经排过序的)。

如果返回空数组，说明没有新内容，直接跳到步骤5(仍建议跑一次export脚本，无害)。

如果条目很多(比如第一次跑，或者刚加了新信源、RSS一次回填几十条)，分批处理：`--limit 30`配合多跑几次。stderr里如果出现"正文预算不够"的警告，说明这一批里有条目明明库里有正文却被退回了`fetch`——减小`--limit`重跑，别让它白抓一遍。

### 3. 两段式判断——读 `RANKING_CRITERIA.md` 获取判断标准，这里只列执行步骤

判断锚点track需要的清单已经内联在`RANKING_CRITERIA.md`的Track 2里，**不要去读任何仓库外的文件**——尤其不要去找`/Users/taoye/claude/thought-lab/`下面的路径，那是用户本地Mac上的目录，定时任务跑在GitHub Actions上根本读不到。**读不到某个可选文件时绝不要停下来问用户**：这是无人值守的定时任务，没人会回答，停下来等于整次跑批白跑(2026-08-20踩过，那次已经抓到6条新内容，因为卡在提问上没走到commit，随runner容器一起丢了)。

**初筛**(不抓取任何东西)：**一轮里把所有pending条目一次性判完**，不要一条条分开处理——初筛不需要任何工具调用，凑一轮做完能省掉N-1轮的turn开销。手里有什么就用什么：`body_source == "rss"`的条目用`content`(正文)判，其余的只能用title+summary判。按`RANKING_CRITERIA.md`里Track 1(AI实操/趋势)和Track 2(thought-lab锚点)的标准，给每条条目出`ai_tier`/`ai_reason`/`anchor_tier`/`anchor_reason`。

**精判**(初筛做完之后，只针对需要精判的条目继续，按`body_source`执行，不用自己重新判断走哪条路径)：
- `body_source == "rss"` → **不要WebFetch**。初筛已经看过正文了，tier就是终值。任一track是`medium`/`high`时基于正文写一段`digest_summary`(内容概要+核心观点，2~4句，不是摘录)。
- `body_source == "fetch"` 且初筛任一track是`medium`或`high` → 用WebFetch工具抓一次`link`的全文，基于全文重新判断该track的tier(可以推翻初筛结果)，并写`digest_summary`。全文读完就丢，不要写入任何文件、不要存进结果JSON。
- `body_source == "none"` 且初筛任一track是`medium`/`high` → 不追加抓取，基于已有的`summary`字段写一段轻提炼作为`digest_summary`。X的`summary`是英文推文原文，写成中文概要(1~2句)，不要照抄英文。
- `always_summarize == true`(X，或标题带`[RIDGELINE]`前缀的Craig Mod文章) → 不管`ai_tier`/`anchor_tier`判成什么，都要写中文`digest_summary`。X是"7日内关注"页"X动态"板块不管tier全展示；Ridgeline是用户明确说很喜欢、不想被判断结果筛掉，全部永久展示(见`config.ALWAYS_ARCHIVE_TITLE_PREFIXES`)。这类如果`body_source`是`"fetch"`但初筛两个track都`low`，不用额外WebFetch全文，直接基于已有`summary`写轻提炼即可，跟`"none"`走同样的轻量路径。
- 其余情况(两个track都`low`且`always_summarize == false`) → 维持low，`digest_summary`留空(null)。

`ai_tier`/`anchor_tier`判完后，再对照`RANKING_CRITERIA.md`最后的"内容排除"一节检查一遍——目前只对Ray Dalio的X内容生效，命中就在结果里加`excluded_reason`(一句话理由)，其余字段照常写，导出时会被过滤掉。

### 4. 写回数据库

把每条的判断结果整理成JSON数组(格式见`scripts/rank_items.py`文件头注释)，写到一个临时文件(比如`/tmp`或scratchpad目录)，然后:

```bash
python3 scripts/rank_items.py write <临时文件路径>
```

### 5. 导出前端数据

```bash
python3 export_json.py && python3 export_recent.py --pipeline-run
```

一次Bash调用跑完，不要拆成两次。**`--pipeline-run`这个参数不能漏**——它告诉导出脚本"这次是完整跑了一遍管线"，这样当这次一条新内容都没抓到时，会把上一批残留的"刚更新"高亮灭掉(不带这个参数是手动重跑导出的语义，会原样保留上一份高亮，见`new_flags.py`模块头)。`export_json.py`导出月度归档(`docs/digest.html`用，只归档high档)，`export_recent.py`导出最近7天动态(`docs/index.html`"7日内关注"页的"AI实操/趋势"+"关注锚点"+"X动态"三个板块用)——**两个都要跑**，漏了`export_recent.py`该页面会拿不到数据。

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
