# dailyDigest 项目背景

开工前先读一下之前的规划记录：

`/Users/taoye/.claude/projects/-Users-taoye-uxye-researchAgent/memory/project_daily_digest_agent.md`

那份文件里有：已经定下的方向（抓取用普通脚本，优先级排序用 Claude Code 本身而不是单独接 API）、跟 `/Users/taoye/claude/thought-lab` 的关系（代码隔离在这边，但输出内容和值得细读的东西要接到 thought-lab 里）、还没定的问题（具体信息源、X API 有没有 key、输出格式）。

读完直接接着聊，不用问用户"要不要我先了解一下背景"。

## 两个站点（2026-09-02 拆分，别搞混）

| | 地址 | 谁能看 | 内容 |
|---|---|---|---|
| **私有站** | `https://dailydigest.llty-truely-2014.workers.dev` | 只有用户（Cloudflare Access 挡着） | 全量：AI + 锚点双轨、X 动态、通向 Obsidian 的「记录」按钮 |
| **公开站** | `https://yyeees.github.io/AIDailyNews/` | 发给别人的就是这个 | 只有命中 AI track 的条目 |

两条发布管线互不干扰：

- **私有站** —— Cloudflare Worker 直接跟着私有仓 `YYeees/dailyDigest` 的推送走，`docs/` 就是站点根目录，不需要额外步骤。
- **公开站** —— 两个 workflow 末尾的 `scripts/publish_public.sh`，跑 `export_public.py` 过滤后推到 `YYeees/AIDailyNews`。

**改前端时注意**：`docs/index.html` 和 `docs/digest.html` 是**唯一**一份，两个站共用。公开站靠 `export_public.py` 注入 `window.PUBLIC_SITE`、由文件里的 `IS_PUBLIC` 分支收敛差异。不要为公开站复制第二份 HTML——复制必然漂开。

`export_public.py` 里有两道会让跑批直接中止的自检（产物含「锚点」字样、`<!--SITE-CONFIG-->` 标记不止一处），别为了让它跑过去而绕开它们。
