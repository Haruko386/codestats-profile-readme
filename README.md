# Code::Stats Profile README Action

这是一个可复用 GitHub Action，参考 [WEGFan/codestats-profile-readme](https://github.com/WEGFan/codestats-profile-readme) 的历史图布局生成静态 SVG，并使用 [GitHub Linguist](https://github.com/github-linguist/linguist) 官方语言颜色。

这个仓库只保存生成器，不在自身仓库中定时生成或提交图表。实际的历史数据和 SVG 会写入调用该 Action 的仓库。

## 行为

- 首次运行会获取截至昨天的完整 30 天。
- 后续运行只请求并替换昨天的数据。
- 默认时区为 `Asia/Shanghai`，图表大小为 `1000 × 300`。
- 历史数据写入 `data/codestats-history.json`。
- SVG 写入 `assets/codestats-history.svg`。
- Action 自动在调用方仓库提交发生变化的两个文件。

## 在个人资料仓库中使用

```yaml
name: Update Code::Stats profile graph

on:
  schedule:
    - cron: "0 0 * * *" # UTC 00:00 / UTC+8 08:00
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: Haruko386/codestats-profile-readme@master
```

然后在个人资料 `README.md` 中引用：

```html
<a href="https://codestats.net/users/Haruko386">
  <img src="./assets/codestats-history.svg" alt="Haruko386's Code::Stats history graph" width="100%" />
</a>
```

## 手动补跑

调用方工作流可以传递两个可选输入：

- `date`：只补指定日期，例如 `2026-09-26`。
- `bootstrap`：设为 `true` 时强制刷新完整 30 天窗口。

生成脚本只使用 Python 标准库。测试命令：

```bash
python -m unittest discover -s tests -v
```

本项目沿用原项目的 MIT License。
