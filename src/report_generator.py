"""生成每日 Markdown 报告。"""
from datetime import datetime, timezone, timedelta

import config


def generate(date_str, keywords, repos, ai_results=None):
    ai_results = ai_results or {}
    tz = timezone(timedelta(hours=8))
    lines = []
    lines.append("# Android APP 发现日报 - %s\n" % date_str)
    lines.append("> 自动生成时间: %s\n" % datetime.now(tz).strftime("%Y-%m-%d %H:%M CST"))
    lines.append("> 数据来源: 百度热搜 / Google Trends / GitHub Search API\n")

    lines.append("## 一、今日热点关键词\n")
    for i, kw in enumerate(keywords, 1):
        lines.append("%d. %s" % (i, kw))
    lines.append("")

    candidates = [r for r in repos if r["score"] >= config.MIN_REPORT_SCORE]
    if not candidates:
        lines.append("## 二、可做的 APP 候选\n")
        lines.append("今日未发现满足阈值的候选。可调整 config.py 中的 MIN_REPORT_SCORE 或扩展种子词。\n")
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
            lines.append("**应用商店查重** (查询词: %s)" % sc["query"])
            lines.append("- 竞争程度: %s | 同类约 %d 个" % (sc["competition"], sc["total_similar"]))
            apple = sc["stores"].get("apple", {})
            if apple.get("count", 0) > 0:
                lines.append("- Apple App Store: %d 个同类" % apple["count"])
                for it in apple["samples"][:3]:
                    lines.append("  - %s (%s) [%s] %s" % (it["name"], it["developer"], it["genre"], it["price"]))
            else:
                lines.append("- Apple App Store: 未发现同类（蓝海机会）")
            for sname in ["google_play", "huawei", "xiaomi", "vivo", "oppo"]:
                st = sc["stores"].get(sname, {})
                if st.get("count", 0) > 0:
                    lines.append("- %s: 约 %d 个同类" % (sname, st["count"]))
                elif st.get("count", 0) == -1:
                    lines.append("- %s: %s" % (sname, st.get("note", "未查询")))
            lines.append("")
        lines.append("**解决了什么问题 / 痛点**")
        for p in r["pain_points"]:
            lines.append("- %s" % p)
        if not r["pain_points"]:
            lines.append("- (未抽取到明确痛点，建议人工查看 README)")
        lines.append("")
        lines.append("**为什么适合做成 APP**")
        for rs in r["reasons"]:
            lines.append("- %s" % rs)
        lines.append("")
        ai = ai_results.get(r["name"])
        if ai:
            lines.append("**AI 深度解读**")
            lines.append("- 问题: %s" % ai.get("problem", ""))
            lines.append("- 痛点: %s" % ai.get("pain_point", ""))
            lines.append("- APP 设想: %s" % ai.get("app_idea", ""))
            lines.append("- 为何适合: %s" % ai.get("why_app", ""))
            lines.append("")
        lines.append("**实现方案建议**")
        lines.append("- 复用该仓库的核心能力作为后端/算法层")
        lines.append("- 用 Kotlin/Swift/Flutter 做移动端壳，调用其 API 或本地集成")
        lines.append("- 若仓库是 CLI/库，封装成轻量服务(如 FastAPI)供 APP 调用")
        lines.append("- 先做 MVP：聚焦 1 个核心场景，验证用户付费意愿\n")
        lines.append("---\n")

    lines.append("## 三、说明\n")
    lines.append("- 评分模型见 `src/config.py`，可调权重与阈值。")
    lines.append("- 未启用 AI 深度解读时，痛点/方案为启发式抽取；启用方式见 README。")
    lines.append("- 所有候选均来自近期活跃且有 star 验证的 GitHub 项目。\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate("2026-06-26", ["LLM"], []))
