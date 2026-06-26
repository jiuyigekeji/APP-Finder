# APP-Finder

每天自动从热点关键词出发，在 GitHub 上发现有 star 验证、近期活跃、且适合做成 APP / 小程序的工程项目，并产出一份包含「痛点 / 解决的问题 / 为什么适合做 APP / 实现方案」的 Markdown 报告。

## 设计目标

- **免费**：全部跑在 GitHub Actions 上，只用 Python 标准库，无需任何付费 API。
- **定时触发**：GitHub Actions 的 `cron` 每天 09:00（北京时间）自动运行。
- **零运维**：报告以 Markdown 自动 commit 回仓库 `reports/` 目录，可历史追溯。

## 工作流程

```
百度热搜 + Google Trends RSS  →  关键词
        ↓
GitHub Search API（近期活跃 + 一定 star）
        ↓
读取 README + 评分模型（APP 适配度）
        ↓
应用商店查重（Apple 官方 API + 分类推断）
        ↓
（可选）AI 深度解读
        ↓
Markdown 报告 → commit 到 reports/YYYY-MM-DD.md
```

## 目录结构

```
src/
  config.py              # 关键词来源、阈值、评分权重（核心可调项）
  keyword_collector.py   # 百度热搜 + Google Trends 采集
  github_searcher.py     # GitHub 搜索与过滤
  repo_analyzer.py       # README 解析 + APP 适配度评分
  ai_analyzer.py         # 可选：接 Gemini 等 OpenAI 兼容接口
  report_generator.py    # Markdown 报告生成
  main.py                # 主入口
reports/                 # 每日报告输出
.github/workflows/daily-finder.yml  # 定时任务
```

## 本地运行

```bash
python src/main.py
```

输出：`reports/YYYY-MM-DD.md`

## 部署到 GitHub（免费 + 定时）

1. 把本仓库 push 到 GitHub。
2. 默认 `GITHUB_TOKEN` 由 Actions 自动注入（无需配置），用于提升 GitHub API 配额到 5000/小时。
3. 工作流已设置 `permissions: contents: write`，可直接 commit 报告回仓库。
4. 默认每天 09:00 自动运行；也可在仓库 `Actions` 页面手动触发（`workflow_dispatch`）。

## 评分模型说明

候选仓库按「APP 适配度」打分，主要维度：

- star 适中（100–5000）：有验证但未被巨头覆盖
- 主语言适合移动端/客户端（Kotlin/Swift/Dart/JS/Python 等）
- topics 命中 APP 友好领域（ai/llm/翻译/笔记/记账…）
- README 出现移动/用户向关键词
- 命中基础设施特征（k8s/microservice 等）则扣分
- 近期活跃、描述聚焦明确加分

得分 ≥ `MIN_REPORT_SCORE`（默认 40）才进入报告。

## 可选：开启 AI 深度解读

评分模型是规则化的，零成本但偏粗。如需更高质量的问题/痛点/方案分析，可接入 Gemini 免费 API：

1. 在仓库 `Settings → Secrets and variables → Actions` 添加：
   - `ENABLE_AI_ANALYSIS` = `true`
   - `AI_API_KEY` = 你的 Gemini API key（免费额度）
   - （可选）`AI_MODEL` = `gemini-1.5-flash`
2. 之后每日报告的 Top 5 候选会附带 AI 深度解读。

## 应用商店查重与分类

每个进入报告的候选会自动做应用商店查重，输出：

- **推荐 APP 分类**：优先用 Apple 真实分类（出现最多的 `primaryGenreName`），无结果时按关键词映射推断（映射表见 `src/config.py` 的 `CATEGORY_KEYWORD_MAP`）。
- **Apple App Store**：用官方 iTunes Search API（免费、无需 key），返回同类数量与示例（名称/开发者/分类/价格）。
- **Google Play / 华为 / 小米 / VIVO / OPPO**：无官方免费搜索 API，默认标注「未开启，建议人工复查」。
- **竞争程度**：根据 Apple 同类数量判定（0=蓝海，≤3 低竞争，≤8 中等，>8 红海）。

开启其他商店的站内搜索（不稳定且慢，谨慎使用）：在 Actions Secrets 设 `ENABLE_GOOGLE_SITE_SEARCH=true`。

## 调优

所有阈值与权重集中在 `src/config.py`：
- `MIN_STARS` / `MAX_STARS`：star 区间
- `CREATED_WITHIN_DAYS`：活跃窗口
- `MIN_REPORT_SCORE`：报告入选阈值
- `SEED_KEYWORDS`：热榜失败时的回退词
- `W_*`：各评分维度权重
- `CATEGORY_KEYWORD_MAP`：APP 分类关键词映射
- `ENABLE_GOOGLE_SITE_SEARCH`：是否开启非 Apple 商店站内搜索

## 注意事项

- 百度热搜为非官方接口，可能变动；失败会自动回退种子词，保证每天仍出报告。
- GitHub Search API 未认证限速 60 次/小时，已配置 token 时为 5000/小时。
- 本工具输出的是「候选思路与实现方向」，是否真正可做仍需人工判断。
