# GitHub Actions 使用 Codex CLI

每日 Digest 和每周 Trending 使用 Codex CLI，通过你自己的 ChatGPT 订阅登录运行。
不需要 OpenAI API Key；可用额度和限制由登录账号的 Codex 订阅决定。
这不是共享当前聊天的认证，也不能保证订阅凭据永久适用于无人值守任务。

## 首次配置

在你信任的电脑上安装 CLI 并使用独立目录登录，避免与日常 CLI 共用刷新凭据：

```bash
npm install -g @openai/codex@0.163.0
export CODEX_HOME="$HOME/.codex-daily-digest"
mkdir -p "$CODEX_HOME"
chmod 700 "$CODEX_HOME"
codex -c 'cli_auth_credentials_store="file"' login --device-auth
codex login status
gh secret set CODEX_AUTH_JSON --repo YYeees/dailyDigest < "$CODEX_HOME/auth.json"
```

登录时选择你有 Codex 使用权限的 ChatGPT 账号。设备登录如被账号设置禁用，
可在同一电脑用 `codex -c 'cli_auth_credentials_store="file"' login` 完成浏览器登录。
不要打印或提交 auth.json，不要把它贴到聊天里。也可在 GitHub 仓库的
Settings → Secrets and variables → Actions 中安全添加 `CODEX_AUTH_JSON`。

保留已有 `TWITTERAPI_IO_KEY` 和 `AIDAILYNEWS_DEPLOY_KEY`。
Claude 的账号限制不再影响迁移后的任务。

## 验证和补跑

工作流修改推送到 main 且 Secret 配置完成后：

```bash
gh workflow run digest.yml --repo YYeees/dailyDigest --ref main
gh run list --repo YYeees/dailyDigest --workflow digest.yml --limit 3
```

检查 Run skill、Health check 和 Publish public site 都通过，并确认网站数据更新时间。
不要对旧版失败任务点击 Re-run 来验证迁移，那会使用旧提交的 Claude 工作流。

CLI 在临时目录读取登录文件，结束后删除；不上传凭据或原始代理对话。
运行日志继续使用现有结构，订阅调用的美元费用显示为未知，不伪造 API 价格。
两个工作流共用写入队列，避免同时推送数据库造成冲突。

OAuth 刷新可能轮换凭据。GitHub Secret 不会自动接收 CLI 刷新后的文件，
因此此方案可能需要重新登录并重新执行 `gh secret set`；它不是永久免维护的认证。
遇到失效、账号验证或订阅额度耗尽，需处理对应账号问题后重新发起任务。

官方参考：https://developers.openai.com/codex/auth
