"""生成每日 Markdown 报告（中文）。"""
from datetime import datetime, timezone, timedelta

import config

STORE_NAMES_CN = {
    "apple": "Apple App Store",
    "google_play": "Google Play",
    "huawei": "华为应用市场",
    "xiaomi": "小米应用商店",
    "vivo": "vivo 应用商店",
}
STORE_ORDER = ["apple", "google_play", "huawei", "xiaomi", "vivo"]


def _kw_line(i, kw, zh):
    if zh and zh.lower() != kw.lower():
        return "%d. %s（%s）" % (i, kw, zh)
    return "%d. %s" % (i, kw)


def generate(date_str, translated_grouped, repos, ai_results=None):
    ai_results = ai_results or {}
    tz = timezone(timedelta(hours=8))
    lines = []
    lines.append("# APP 发现日报 - %s\n" % date_str)
    lines.append("> 自动生成时间: %s" % datetime.now(tz).strftime("%Y-%m-%d %H:%M CST"))
    lines.append("> 数据来源: 百度热搜 / Google Trends / GitHub Search API / 各应用商店\n")

    lines.append("## 一、今日热点关键词\n")
    baidu = translated_grouped.get("baidu", [])
    google = translated_grouped.get("google", [])
    if baidu:
        lines.append("**百度热搜**\n")
        for i, (kw, zh) in enumerate(baidu, 1):
            lines.append(_kw_line(i, kw, zh))
        lines.append("")
    if google:
        lines.append("**Google Trends**\n")
        for i, (kw, zh) in enumerate(google, 1):
            lines.append(_kw_line(i, kw, zh))
        lines.append("")

    candidates = [r for r in repos if r["score"] >= config.MIN_REPORT_SCORE]
    if not candidates:
        lines.append("## 二、可做的 APP 候选\n")
        lines.append("今日未发现满足阈值的候选。可调整 `config.py` 中的 `MIN_REPORT_SCORE` 或扩展种子词。\n")
        return "\n".join(lines)

    lines.append("## 二、可做的 APP 候选（按适配度评分排序）\n")
    for idx, r in enumerate(candidates, 1):
        lines.append("### %d. %s （评分 %d）\n" % (idx, r["name"], r["score"]))
        lines.append("- 仓库: %s" % r["url"])
        lines.append("- 描述: %s" % (r["desc"] or "(无)"))
        lines.append("- Star: %d | 语言: %s | Topics: %s" % (r["stars"], r["language"] or "未知", ", ".join(r["topics"]) or "无"))
        if r["homepage"]:
            lines.append("- 主页: %s" % r["homepage"])
        lines.append("")

        # 推荐分类 + 应用商店查重
        sc = r.get("store_check")
        if sc:
            lines.append("**推荐 APP 分类**: %s" % sc["category"])
            lines.append("**应用商店查重**（查询词: %s）" % sc["query"])
            lines.append("- 竞争程度: %s | 全平台同类约 %d 个" % (sc["competition"], sc["total_similar"]))
            for sname in STORE_ORDER:
                st = sc["stores"].get(sname, {})
                cnt = st.get("count", 0)
                label = STORE_NAMES_CN.get(sname, sname)
                if cnt > 0:
                    lines.append("- %s: %d 个同类" % (label, cnt))
                    for it in st.get("samples", [])[:2]:
                        extra = []
                        if it.get("genre"):
                            extra.append(it["genre"])
                        if it.get("installs"):
                            extra.append(it["installs"])
                        if it.get("price"):
                            extra.append(it["price"])
                        tail = "（%s）" % " · ".join(extra) if extra else ""
                        lines.append("  - %s%s" % (it.get("name", ""), tail))
                else:
                    lines.append("- %s: 未发现同类" % label)
            lines.append("")

        # 解决的问题 / 痛点
        ai = ai_results.get(r["name"])
        lines.append("**解决了什么问题 / 痛点**")
        if ai:
            lines.append("- 核心逻辑: %s" % ai.get("key_logic", ""))
            lines.append("- 解决的问题: %s" % ai.get("problem", ""))
            lines.append("- 用户痛点: %s" % ai.get("pain_point", ""))
        else:
            lines.append("- _（未启用 AI 代码分析，以下为启发式抽取，建议开启 AI 或人工复核 README）_")
            for p in r["pain_points"]:
                lines.append("- %s" % p)
            if not r["pain_points"]:
                lines.append("- (未抽取到明确痛点)")
        lines.append("")

        lines.append("**为什么适合做成 APP**")
        if ai and ai.get("why_app"):
            lines.append("- %s" % ai.get("why_app"))
        if ai and ai.get("app_idea"):
            lines.append("- APP 设想: %s" % ai.get("app_idea"))
        for rs in r["reasons"]:
            lines.append("- %s" % rs)
        lines.append("")

        lines.append("**实现方案建议**")
        lines.append("- 复用该仓库的核心能力作为后端/算法层")
        lines.append("- 用 Kotlin/Swift/Flutter 做移动端壳，调用其 API 或本地集成")
        lines.append("- 若仓库是 CLI/库，封装成轻量服务(如 FastAPI)供 APP 调用")
        lines.append("- 先做 MVP：聚焦 1 个核心场景，验证用户付费意愿\n")
        lines.append("---\n")

    lines.append("## 三、说明\n")
    lines.append("- 评分模型见 `src/config.py`，可调权重与阈值。")
    lines.append("- 关键词翻译优先用 AI API，回退 LibreTranslate，最终回退原文。")
    lines.append("- 商店查重：Apple 走官方 API、Google Play 走 scraper 库、国内商店抓取搜索页，失败回退为「未发现同类」。")
    lines.append("- 痛点分析：启用 AI 时会拉取仓库核心源码做深度分析；未启用时为启发式抽取。\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate("2026-06-26", [("LLM", "大语言模型")], []))
