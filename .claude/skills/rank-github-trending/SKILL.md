---
name: rank-github-trending
description: 抓一次GitHub Trending周榜(全语言+Python/Jupyter Notebook/TypeScript)，对新出现的仓库读README做AI相关性/难度/推荐理由评估，写回数据库并导出前端JSON。用户说"跑一下trending"、"更新GitHub趋势"时使用。也是GitHub Actions每周routine应该执行的内容(headless claude调用)。
---

# Rank GitHub Trending

这份skill串联GitHub Trending发现流程的完整pipeline。AI评估(是否AI相关、难度、值得学习程度、推荐理由)必须由执行这份skill的Claude Code现场读README推理完成——不能写死成代码规则，也不能改成调用单独的LLM API(跟run-digest skill遵循同一条项目原则)。这份skill既可以在交互式session里手动跑，也是GitHub Actions每周定时任务里headless claude要执行的内容。

## 步骤

### 1. 抓取本周trending

```bash
python3 scripts/fetch_trending.py
```

爬全语言榜(`since=weekly`) + Python/Jupyter Notebook/TypeScript语言榜(2026-08-15从每日改成每周，日榜量太大、评估成本跟展示上限不匹配)。新仓库写入`repos`表(`evaluated_at`留空)，所有仓库(不管新旧)每次抓取都会新增一条`daily_snapshots`记录(表名是历史遗留，实际按周跑)。已评估过的仓库不会被重复评估。

### 2. 读取待评估仓库

```bash
python3 scripts/trending_repos.py pending
```

输出JSON数组，每条含`full_name/url/description/primary_language/first_seen_date`。

如果条目较多，分批处理，每批10~15个(README全文比blog文章长很多，一次读太多容易信息过载)。

### 3. 逐个评估——完整标准见 `GITHUB_TRENDING_CRITERIA.md`

对每个仓库：

1. **WebFetch README**：直接WebFetch `https://github.com/{full_name}`(GitHub会渲染README到仓库主页)。不要用`raw.githubusercontent.com`，部分网络环境下证书校验会失败。
2. **判断`ai_related`**(true/false)：范围不限于Agent项目，AI工具/Skill/RAG/AI辅助设计/模型应用/AI开发工具链等广泛AI相关内容都算。不相关的仓库`ai_related=false`，其余字段留空，`recommend_reason`写一句排除理由。
3. **只对`ai_related=true`的仓库继续判断**：
   - `difficulty`(beginner/intermediate/advanced)——呼应RANKING_CRITERIA.md里AI实操track的坡度概念。
   - `worth_tier`(high/medium/low)——警惕空壳/纯awesome-list/蹭热度项目，star数高不代表质量高，只看README体现出的真实内容。
   - `recommend_reason`(2~4句话)——必须基于细读README，说清楚项目是做什么的、为什么值得(或不值得)学习。

### 4. 写回数据库

把结果整理成JSON数组(格式见`scripts/trending_repos.py`文件头注释)，写到临时文件，然后:

```bash
python3 scripts/trending_repos.py write <临时文件路径>
```

### 5. 导出前端数据

```bash
python3 scripts/export_trending.py
python3 export_json.py
```

`export_trending.py`导出`trending.json`("7日内关注"页Trending板块用，最新发现的高分仓库，上限6个)，`export_json.py`导出月度归档(`digest.html`的"GitHub高分项目"板块用，按`first_seen_date`月份聚合，每月上限10个)——**两个都要跑**，漏了`export_json.py`月度归档不会更新。

### 6. 提交并推送

```bash
git add digest.db docs/data/
git commit -m "GitHub Trending: 评估N个新仓库"
git push
```

**交互式session里手动跑这份skill时**：commit可以直接做，push前照常按assistant的risky-action政策跟用户确认一句。
**GitHub Actions每周routine执行时(headless claude)**：这一步就是自动化的意义所在，直接push——GitHub Actions原生有`GITHUB_TOKEN`权限，不需要额外配置认证。

## 输出总结

跑完后用一两句话汇报：本周抓到几个仓库(去重后)、新评估了几个、其中AI相关的有几个(分high/medium/low)、有没有encountered需要人工看一眼的情况(比如trending页面结构变了导致解析失败、某个仓库README读取失败)。
