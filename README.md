# Code::Stats Profile README（每日快照版）

这个版本参考 [WEGFan/codestats-profile-readme](https://github.com/WEGFan/codestats-profile-readme) 的历史图布局，但不再运行实时图片服务。首次运行会一次性初始化截至昨天的 30 天数据；之后 GitHub Actions 每天在东八区 08:00 只请求前一天的数据，并重新生成静态 SVG。

### 🕰️ Recently I'm coding in...

<a href="https://codestats.net/users/Haruko386">
  <img src="./assets/codestats-history.svg" alt="Haruko386's Code::Stats history graph" width="1000" />
</a>

## 与原项目的区别

- 原项目在图片请求到达时实时查询；本项目每天生成一次静态文件，不依赖常驻服务器。
- 首次运行（或更换用户名）拉取截至昨天的完整 30 天；初始化完成后，每次正常运行只请求东八区“昨天”这一天。
- Code::Stats 接口没有结束日期参数，所以脚本会主动丢弃响应中今天及请求窗口外的数据。
- 历史数据保存在 `data/codestats-history.json`，自动只保留最近 30 天。
- 颜色按语言名称绑定，不按排名绑定。标准语言来自 [GitHub Linguist `languages.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml)，所以柱体排序变化时不会串色。
- `ChatInput`、`Log` 等不属于 GitHub Linguist 的 Code::Stats 伪语言，可在配置中指定颜色；未识别语言使用灰色。

## 启用

1. 在 [`config/history-graph.json`](./config/history-graph.json) 中修改 `username`。默认已设为 `Haruko386`，时区为 `Asia/Shanghai`，画布为 `1000 × 300`，显示 30 天和最多 12 种语言。
2. 将仓库推送到 GitHub。工作流 [`.github/workflows/update-code-stats.yml`](./.github/workflows/update-code-stats.yml) 使用 `0 0 * * *`，即 UTC 00:00 / 东八区 08:00。GitHub 的计划任务可能因平台负载稍晚开始。
3. 在仓库的 **Actions → Update Code::Stats history graph → Run workflow** 手动运行一次，或等待下一次计划任务。
4. 如果组织或仓库策略限制了 `GITHUB_TOKEN`，请在 **Settings → Actions → General → Workflow permissions** 允许工作流写入仓库内容。

不需要 Code::Stats token；公开用户数据直接从 Code::Stats API 获取。脚本只使用 Python 标准库，无需安装依赖。

## 在个人 README 中引用

如果图片和 README 在同一个仓库：

```html
<a href="https://codestats.net/users/Haruko386">
  <img src="./assets/codestats-history.svg" alt="Haruko386's Code::Stats history graph" />
</a>
```

如果从另一个仓库引用，请换成原始文件地址，并替换所有占位值：

```html
<a href="https://codestats.net/users/Haruko386">
  <img src="https://raw.githubusercontent.com/OWNER/REPOSITORY/BRANCH/assets/codestats-history.svg" alt="Haruko386's Code::Stats history graph" />
</a>
```

## 配置颜色

[`config/history-graph.json`](./config/history-graph.json) 中有两种映射：

- `language_aliases`：把 Code::Stats 名称映射到 GitHub Linguist 名称，例如 `C/C++ → C++`、`Shell Script → Shell`。
- `color_overrides`：为 GitHub 没有收录的名称指定颜色。它的优先级高于官方色。

颜色解析顺序为：`color_overrides` → `language_aliases` → GitHub Linguist → `unknown_color`。

## 失败补跑和本地运行

计划任务失败后，可以手动运行工作流，并在 `date` 输入框填写漏掉的日期，例如 `2026-09-26`。接口仍会只保存所填日期的数据。勾选 `bootstrap` 可以强制刷新截至指定日期的完整 30 天。

```bash
# 获取东八区昨天的数据并生成图片
python scripts/generate_history_graph.py

# 补指定日期
python scripts/generate_history_graph.py --date 2026-09-26

# 强制重新拉取完整 30 天
python scripts/generate_history_graph.py --bootstrap

# 不联网，仅用仓库中的数据重画
python scripts/generate_history_graph.py --offline

# 测试
python -m unittest discover -s tests -v
```

首次运行会直接得到 30 天完整窗口；之后每天只更新昨天，并持续滚动保留最近 30 天。

## 数据流

```text
每天 08:00（UTC+8）
        │
        ▼
首次：读取截至昨天的 30 天
之后：只读取昨天的数据
        │  严格按日期过滤
        ▼
更新最近 30 天 JSON ──► 按累计 XP 选择前 12 种语言
                              │
GitHub Linguist 官方色 ──────┤
                              ▼
                    assets/codestats-history.svg
                              │
                              ▼
                  github-actions[bot] 提交
```

## 致谢与许可

图表行为与布局参考原项目 [WEGFan/codestats-profile-readme](https://github.com/WEGFan/codestats-profile-readme)。本仓库沿用其 MIT License。
