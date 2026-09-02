# dailyDigest 项目背景

开工前先读一下之前的规划记录：

`/Users/taoye/.claude/projects/-Users-taoye-uxye-researchAgent/memory/project_daily_digest_agent.md`

那份文件里有：已经定下的方向（抓取用普通脚本，优先级排序用 Claude Code 本身而不是单独接 API）、跟 `/Users/taoye/claude/thought-lab` 的关系（代码隔离在这边，但输出内容和值得细读的东西要接到 thought-lab 里）、还没定的问题（具体信息源、X API 有没有 key、输出格式）。

读完直接接着聊，不用问用户"要不要我先了解一下背景"。

## 两个站点（2026-09-02 拆分，同日改了托管方式，别搞混）

| | 地址 | 谁能看 | 内容 |
|---|---|---|---|
| **全量站** | `https://yyeees.github.io/dailyDigest/` | **没有任何访问控制**，只是地址不显眼 | 全量：AI + 锚点双轨、X 动态、通向 Obsidian 的「记录」按钮 |
| **公开站** | `https://aidailynews.yyeees.workers.dev` | 发给别人的就是这个 | 只有命中 AI track 的条目 |

**别把全量站当私有站。** 它原来在 Cloudflare Worker 后面挂着 Cloudflare Access 登录，
2026-09-02 用户拍板换掉了：`YYeees/dailyDigest` 转回公开仓，GitHub Pages 从 `main` 分支
的 `/docs` 发布。所以锚点判断、`digest.db`、`RANKING_CRITERIA.md` 的母题现在都是公开可搜的，
Actions 的运行日志也是。这是用户在知情后选的（图访问和修改方便），不用再提议加回访问控制。
`export_public.py` 那套过滤依然有意义——它决定的是**发给别人的那个地址**里有什么。

两条发布管线互不干扰：

- **全量站** —— GitHub Pages 直接跟着 `main` 的推送走，`docs/` 就是站点根目录，不需要额外步骤。
  `docs/.nojekyll` 别删，用来挡 Jekyll 插手静态产物。
- **公开站** —— 两个 workflow 末尾的 `scripts/publish_public.sh`，跑 `export_public.py` 过滤后推到
  `YYeees/AIDailyNews`；Cloudflare **Worker（静态资源）** 接在那个仓上，推一次自动部署一次。
  注意是 Worker 不是 Pages——`aidailynews.pages.dev` 这个域名不存在，别照着它调。
  `yyeees.github.io/AIDailyNews/` 那个 GitHub Pages 地址没关，留着当备份线路（大陆访问
  github.io 通常比 `*.workers.dev` 靠谱）。

**改前端时注意**：`docs/index.html` 和 `docs/digest.html` 是**唯一**一份，两个站共用。公开站靠 `export_public.py` 注入 `window.PUBLIC_SITE`、由文件里的 `IS_PUBLIC` 分支收敛差异。不要为公开站复制第二份 HTML——复制必然漂开。

`export_public.py` 里有两道会让跑批直接中止的自检（产物含「锚点」字样、`<!--SITE-CONFIG-->` 标记不止一处），别为了让它跑过去而绕开它们。
