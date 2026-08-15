# GitHub Trending AI项目评估标准

这份文档给每次跑GitHub Trending评估的Claude Code参照用(交互式手动跑，或GitHub Actions里的headless claude)，不是代码规则。判断本身要靠细读README，不是靠star数或关键词匹配。

## 输入

从`digest.db`的`repos`表里，读还没评估过的仓库(`evaluated_at IS NULL`)：`full_name`、`description`、`primary_language`、`url`、`first_seen_date`。

**必须WebFetch该仓库的README全文再判断**，不能只看trending页面上的一行description——description经常太短或者过度营销化，判断不出项目的真实深度和适用场景。直接WebFetch `https://github.com/{full_name}`（GitHub会把README渲染到仓库主页上）。**不要用`raw.githubusercontent.com`**——这个域名在部分网络环境下WebFetch会报证书错误，仓库主页更稳妥。

## 判断流程

### 第一步：是否AI相关(`ai_related`)

范围**不限于Agent项目**，只要实质上跟AI有关都算，包括但不限于：
- Agent框架/多智能体系统
- 好用的AI工具/Claude Skill/MCP server
- AI辅助设计类项目(生成式设计、AI辅助创作工具)
- 模型应用(基于LLM/多模态模型构建的产品或demo)
- RAG/向量检索/知识库相关
- AI开发工具链(prompt管理、evals、fine-tuning工具、推理加速等)

**不算AI相关**：跟AI完全无关但恰好也在trending榜单上的项目(前端框架、数据库工具等，除非它本身是"给AI用的数据库/工具链"这种)。

如果判断为不相关，`ai_related=false`，其余字段留空，`recommend_reason`简单写一句排除理由即可，不需要再细读。

### 第二步：只对`ai_related=true`的仓库做以下判断

**`difficulty`(上手难度)**：`beginner` / `intermediate` / `advanced`。判断的是"用户看懂/用起来这个项目需要多少技术背景"，不是"这个项目技术含量高不高"。参照点：跟RANKING_CRITERIA.md里AI实操track的坡度概念一致——用户目前水平是"一般，跟着Mollick/Willison这个难度爬坡"，越贴近这个难度越算beginner/intermediate，需要较深的模型内部机制/研究背景才看得懂的算advanced。

**`worth_tier`(值得关注程度)**：`high` / `medium` / `low`。

- `high`：项目本身扎实可用(不是纯demo/玩具)，代表某类AI工具/做法的优秀实践，或者是学习"AI实操"路上有代表性的样本(工具、框架、案例三选一说得清楚"学了有什么用")。
- `medium`：有一定价值但比较小众/工具依赖性强，或者是某个知名项目的又一个同类实现(生态里已经有很多类似的了)，或者项目本身不错但跟用户当前坡度不太匹配(太难/太简单)。
- `low`：**空壳/蹭热度类项目**——只有README没有实际代码实现、纯awesome-list链接汇总、fork了别人项目但没做实质修改、demo级别到无法真正使用。这类项目哪怕因为营销做得好而登上trending，也要如实标低。

**`recommend_reason`**：2~4句话，必须基于细读README的内容，不能是简介的复制粘贴。说清楚：这个项目是做什么的、核心亮点或者局限在哪、为什么值得(或不值得)学习——如果是`low`，直接说明原因(比如"README里没有可运行的代码，只是一个概念性提案")。

## 一个具体的判断提醒

**star数/trending排名不代表项目质量**，只代表"最近关注度高"——可能是营销做得好、蹭了热点话题、或者被某个大V转发。判断`worth_tier`时完全独立于这个仓库在trending榜单上的排名，只看README体现出的真实内容。

## 去重逻辑(不需要在判断时操心，脚本层已处理)

`trending_repos.py pending`只会给出`evaluated_at IS NULL`的仓库——一个repo一旦被评估过，就算它连续多天出现在trending榜单上，也不会被重复拿来评估(每天的star数变化记录在`daily_snapshots`表，跟AI评估结果分开存)。
