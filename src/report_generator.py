# -*- coding: utf-8 -*-
"""生成每日 Markdown 报告（中文）。

报告结构：
一、用户真实需求（百度联想词扩展，主信号）
二、热搜趋势（辅助参考）
三、可做的 APP 候选（含供给缺口分析）
"""
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


def _sc_query_display(sc):
    """统一处理商店查重的查询词显示（兼容 check 和 check_dual）。"""
    q = sc.get("query", "") or sc.get("query_en", "")
    zh = sc.get("query_zh", "")
    if zh:
        return "%s / %s" % (q, zh)
    return q


def _supply_gap_flag(store_check):
    """供给缺口标记：商店同类少 = 洼地机会。"""
    if not store_check:
        return ""
    total = store_check.get("total_similar", 0)
    if total <= config.LOW_SUPPLY_THRESHOLD:
        return " 🟢供给缺口"
    return ""


def generate(date_str, translated_grouped, repos, ai_results=None, demands=None, blue_gaps=None):
    ai_results = ai_results or {}
    demands = demands or []
    tz = timezone(timedelta(hours=8))
    lines = []
    lines.append("# APP 机会发现日报 - %s\n" % date_str)
    lines.append("> 自动生成时间: %s" % datetime.now(tz).strftime("%Y-%m-%d %H:%M CST"))
    lines.append("> 需求信号: Hacker News(蓝海) / 百度联想词(持续搜索) / 热搜(趋势参考)")
    lines.append("> 供给信号: Apple/Google Play/华为/小米/vivo 商店查重\n")
    # 展示本次过滤的付费推广 APP（来自 app_store_checker.finalize_promotion_filter）
    try:
        import app_store_checker as _asc
        _removed = getattr(_asc, "LAST_REMOVED_PROMOS", [])
    except Exception:
        _removed = []
    if _removed:
        lines.append("> 已过滤付费推广 APP %d 个: %s" % (len(_removed), "、".join(_removed[:8])))

    # ===== 一、蓝海机会（最高优先）=====
    blue_gaps = blue_gaps or []
    lines.append("## 一、🟢 蓝海机会（供给缺口 + 真实需求）\n")
    lines.append("> 来自 Hacker News 用户主动表达的未满足需求，由 AI 判断现有 APP 是否满足该细分场景。\n")
    if blue_gaps:
        for i, bd in enumerate(blue_gaps, 1):
            lines.append("### 蓝海 %d. %s\n" % (i, bd.get("need", "")[:80]))
            if bd.get("audience"):
                lines.append("- 🎯 目标人群: %s" % bd["audience"])
            if bd.get("why_gap"):
                lines.append("- 💡 供给缺口: %s" % bd["why_gap"])
            if bd.get("existing_apps") and bd.get("existing_apps") != "none":
                lines.append("- 📱 现有方案不足: %s" % bd["existing_apps"])
            if bd.get("judge_reason"):
                lines.append("- ✅ AI 判断: %s" % bd["judge_reason"])
            sc = bd.get("store_check")
            if sc:
                lines.append("- 商店查重: 全平台同类 %d 个 | %s" % (sc.get("total_similar", 0), sc.get("competition", "")))
                lines.append("- 分类: %s | 搜索词: %s" % (sc.get("category", ""), _sc_query_display(sc)))
            if bd.get("source_post"):
                lines.append("- 来源帖子: %s（%s 分）" % (bd["source_post"][:60], bd.get("source_points", 0)))
            if bd.get("source_url"):
                lines.append("- 链接: %s" % bd["source_url"])
            lines.append("")
            lines.append("---\n")
    else:
        lines.append("（今日未发现供给缺口的蓝海需求。启用 AI 可显著提升蓝海发现质量。）\n")

    # ===== 二、用户真实需求 =====
    lines.append("## 二、用户真实需求（百度联想词扩展）\n")
    lines.append("> 以下为用户持续搜索的「解决方案型」需求，非突发事件，适合 APP 长周期开发。\n")
    demand_translated = translated_grouped.get("demands", [])
    if demand_translated:
        for i, (kw, zh) in enumerate(demand_translated, 1):
            src = demands[i - 1][1] if i - 1 < len(demands) else ""
            line = _kw_line(i, kw, zh)
            if src:
                line += "  _← %s_" % src
            lines.append(line)
        lines.append("")
    else:
        lines.append("（未挖掘到需求词）\n")

    # ===== 二、热搜趋势（辅助）=====
    lines.append("## 三、热搜趋势（辅助参考）\n")
    hot = translated_grouped.get("hot", {})
    baidu = hot.get("baidu", [])
    google = hot.get("google", [])
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

    # ===== 三、可做的 APP 候选 =====
    candidates = [r for r in repos if r["score"] >= config.MIN_REPORT_SCORE]
    if not candidates:
        lines.append("## 四、可做的 APP 候选\n")
        lines.append("今日未发现满足阈值的候选。可调整 `config.py` 中的 `MIN_REPORT_SCORE`。\n")
        return "\n".join(lines)

    # 优先展示供给缺口的候选
    candidates.sort(key=lambda r: (
        0 if r.get("store_check", {}).get("total_similar", 99) <= config.LOW_SUPPLY_THRESHOLD else 1,
        -r["score"]))
    lines.append("## 四、可做的 APP 候选（🟢供给缺口优先，按评分排序）\n")
    for idx, r in enumerate(candidates, 1):
        gap = _supply_gap_flag(r.get("store_check"))
        lines.append("### %d. %s （评分 %d%s）\n" % (idx, r["name"], r["score"], gap))
        lines.append("- 仓库: %s" % r["url"])
        src_kw = r.get("search_keyword", "")
        src_origin = r.get("search_origin", "")
        if src_origin and src_origin != src_kw:
            lines.append("- 🔑 来源需求: %s → GitHub 搜索: %s" % (src_origin, src_kw))
        elif src_kw:
            lines.append("- 🔑 来源关键词: %s" % src_kw)
        lines.append("- 描述: %s" % (r["desc"] or "(无)"))
        lines.append("- Star: %d | 语言: %s | Topics: %s" % (r["stars"], r["language"] or "未知", ", ".join(r["topics"]) or "无"))
        if r["homepage"]:
            lines.append("- 主页: %s" % r["homepage"])
        lines.append("")

        sc = r.get("store_check")
        if sc:
            lines.append("**推荐 APP 分类**: %s" % sc["category"])
            lines.append("**应用商店查重**（查询词: %s）" % _sc_query_display(sc))
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
                            extra.append(str(it["genre"]))
                        if it.get("installs"):
                            extra.append(str(it["installs"]))
                        if it.get("price"):
                            extra.append(str(it["price"]))
                        tail = "（%s）" % " · ".join(extra) if extra else ""
                        lines.append("  - %s%s" % (it.get("name", ""), tail))
                else:
                    lines.append("- %s: 未发现同类" % label)
            lines.append("")

        ai = ai_results.get(r["name"])
        lines.append("**解决了什么问题 / 痛点**")
        if ai:
            lines.append("- 核心逻辑: %s" % ai.get("key_logic", ""))
            lines.append("- 解决的问题: %s" % ai.get("problem", ""))
            lines.append("- 用户痛点: %s" % ai.get("pain_point", ""))
        else:
            lines.append("- _（AI 代码分析未返回结果，可能因 GitHub 限速拉不到源码；以下为启发式抽取）_")
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

    lines.append("## 五、说明\n")
    lines.append("- 需求信号来自百度联想词（用户持续搜索的解决方案），区别于热搜突发事件。")
    lines.append("- 🟢供给缺口 = 全平台同类 APP ≤ %d 个，是值得优先验证的洼地。" % config.LOW_SUPPLY_THRESHOLD)
    lines.append("- 候选来自 GitHub 近期活跃且有 star 验证的项目，已做商店查重评估竞争。")
    lines.append("- 启用 AI（`ENABLE_AI_ANALYSIS`）可对仓库源码做深度痛点分析。\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate("2026-06-27", {"demands": [("翻译软件", "翻译软件")], "hot": {"baidu": [], "google": []}}, []))
