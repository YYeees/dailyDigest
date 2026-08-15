# GitHub Trending AI项目评估标准

这份文档给每次跑GitHub Trending评估的Claude Code参照用(交互式手动跑，或GitHub Actions里的headless claude)——**只讲"怎么判断项目质量高低"**，不讲怎么抓取README这类执行细节(那些在`.claude/skills/rank-github-trending/SKILL.md`里)。判断本身要靠细读README，不是靠star数或关键词匹配。

## 判断流程

### 第一步：是否AI相关(`ai_related`)

范围**不限于Agent项目**，只要实质上跟AI有关都算：

| 算AI相关 | 不算AI相关 |
|---|---|
| Agent框架/多智能体系统 | 跟AI完全无关但恰好也在trending榜单上的项目(前端框架、数据库工具等) |
| 好用的AI工具/Claude Skill/MCP server | |
| AI辅助设计类项目(生成式设计、AI辅助创作工具) | |
| 模型应用(基于LLM/多模态模型构建的产品或demo) | |
| RAG/向量检索/知识库相关 | |
| AI开发工具链(prompt管理、evals、fine-tuning工具、推理加速等) | |

不相关的仓库`ai_related=false`，其余字段留空，`recommend_reason`写一句排除理由即可，**不需要再细读**。

### 第二步：只对`ai_related=true`的仓库继续判断

**`difficulty`(上手难度)**——判断的是"用户看懂/用起来这个项目需要多少技术背景"，不是"这个项目技术含量高不高"：

| 难度 | 判断依据 |
|---|---|
| `beginner` | 贴近用户当前坡度(跟RANKING_CRITERIA.md里AI实操track的Mollick/Willison难度一致) |
| `intermediate` | 需要一定技术背景，但有清晰文档/示例降低门槛 |
| `advanced` | 需要较深的模型内部机制/研究背景才看得懂 |

**`worth_tier`(值得关注程度)**：

| Tier | 判断依据 |
|---|---|
| `high` | 项目扎实可用(不是纯demo/玩具)，代表某类AI工具/做法的优秀实践，或是学习"AI实操"路上有代表性的样本(工具/框架/案例三选一说得清楚"学了有什么用") |
| `medium` | 有一定价值但比较小众/工具依赖性强；或是某个知名项目的又一个同类实现(生态里已经有很多类似的了)；或项目不错但跟当前坡度不太匹配(太难/太简单) |
| `low` | **空壳/蹭热度类项目**——只有README没有实际代码实现、纯awesome-list链接汇总、fork了别人项目但没做实质修改、demo级别到无法真正使用。哪怕因为营销做得好而登上trending，也要如实标低 |

**`recommend_reason`**：2~4句话，必须基于细读README的内容，不能是简介的复制粘贴。说清楚项目是做什么的、核心亮点或局限在哪、为什么值得(或不值得)学习——如果是`low`，直接说明原因(比如"README里没有可运行的代码，只是一个概念性提案")。

## 判断提醒

**star数/trending排名不代表项目质量**，只代表"最近关注度高"——可能是营销做得好、蹭了热点话题、或者被某个大V转发。判断`worth_tier`时完全独立于这个仓库在trending榜单上的排名，只看README体现出的真实内容。
