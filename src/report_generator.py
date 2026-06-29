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


def _fmt_field(val, indent="  "):
    """格式化 AI 返回字段：list 展开成多行 bullet，string 直接返回。"""
    if isinstance(val, list):
        return "\n".join("%s- %s" % (indent, x) for x in val) if val else ""
    return str(val) if val else ""


def _difficulty_lines(item):
    """生成实现/推广难点展示行。item 可含 difficulty(dict) 或 ai_results 的 impl_/promo_ 字段。"""
    out = []
    diff = item.get("difficulty") or {}
    impl = diff.get("impl_difficulty") or item.get("impl_difficulty")
    promo = diff.get("promo_difficulty") or item.get("promo_difficulty")
    if impl or promo:
        out.append("**实现/推广难点**")
        if impl:
            if isinstance(impl, list):
                out.append("- 实现难点:")
                for x in impl:
                    out.append("  - %s" % x)
            else:
                out.append("- 实现难点: %s" % impl)
        if promo:
            if isinstance(promo, list):
                out.append("- 推广难点:")
                for x in promo:
                    out.append("  - %s" % x)
            else:
                out.append("- 推广难点: %s" % promo)
        out.append("")
    return out




def _supply_gap_flag(store_check):
    """供给缺口标记：商店同类少 = 洼地机会。"""
    if not store_check:
        return ""
    total = store_check.get("total_similar", 0)
    if total <= config.LOW_SUPPLY_THRESHOLD:
        return " 🟢供给缺口"
    return ""


def generate(date_str, translated_grouped, repos, ai_results=None, demands=None, blue_gaps=None, supply_blue=None, hypo_blue=None, review_blue=None, issues_blue=None):
    ai_results = ai_results or {}
    demands = demands or []
    supply_blue = supply_blue or []
    hypo_blue = hypo_blue or []
    review_blue = review_blue or []
    issues_blue = issues_blue or []
    tz = timezone(timedelta(hours=8))
    lines = []
    lines.append("# APP 机会发现日报 - %s\n" % date_str)
    lines.append("> 自动生成时间: %s" % datetime.now(tz).strftime("%Y-%m-%d %H:%M CST"))
    lines.append("> 需求信号: HN/Reddit + 差评挖掘 + GitHub Issues + 蓝海假设 + 百度联想词")
    lines.append("> 供给信号: Apple/Google Play/华为/小米/vivo 商店查重\n")
    # 展示本次过滤的付费推广 APP（来自 app_store_checker.finalize_promotion_filter）
    try:
        import app_store_checker as _asc
        _removed = getattr(_asc, "LAST_REMOVED_PROMOS", [])
    except Exception:
        _removed = []
    if _removed:
        lines.append("> 已过滤付费推广 APP %d 个: %s" % (len(_removed), "、".join(_removed[:8])))

    # ===== 今日重点：三个蓝海区各取 top，一眼看到当天最值得做的机会 =====
    lines.append("## 🔥 今日重点\n")
    has_highlight = False
    # 蓝海假设（最可能出真蓝海）
    if hypo_blue:
        top = hypo_blue[0]
        lines.append("- **[蓝海假设] %s**" % top.get("need", "")[:50])
        if top.get("audience"):
            lines.append("  - 人群: %s | %s" % (top["audience"], "AI已核对无真正同类"))
        has_highlight = True
    # 需求驱动蓝海
    if blue_gaps:
        top = blue_gaps[0]
        lines.append("- **[需求驱动] %s**" % top.get("need", "")[:50])
        has_highlight = True
    # 供给驱动蓝海
    if supply_blue:
        top = supply_blue[0]
        lines.append("- **[供给驱动] %s**（★%s）" % (top.get("name", "")[:40], top.get("stars", 0)))
        has_highlight = True
    if review_blue:
        top = review_blue[0]
        lines.append("- **[差评驱动] %s**" % top.get("need", "")[:50])
        has_highlight = True
    if issues_blue:
        top = issues_blue[0]
        lines.append("- **[Issue驱动] %s**" % top.get("need", "")[:50])
        has_highlight = True
    if not has_highlight:
        lines.append("（今日三个蓝海区均无候选，详见下方完整分析）")
    lines.append("")
    lines.append("---\n")

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

    # ===== 一B、供给驱动蓝海（GitHub 高 star 项目反查）=====
    lines.append("## 一B、供给驱动蓝海（GitHub 高 star 项目，需求被代码验证但未APP化）\n")
    lines.append("> 从 GitHub 近期 star 暴涨的非APP形态项目(CLI/库/服务)反查：star 证明需求真实，商店同类少证明供给不足。\n")
    if supply_blue:
        for i, r in enumerate(supply_blue, 1):
            gap = _supply_gap_flag(r.get("store_check"))
            lines.append("### 供给蓝海 %d. %s%s\n" % (i, r.get("name", ""), gap))
            lines.append("- 仓库: %s" % r.get("url", ""))
            lines.append("- 描述: %s" % (r.get("desc") or "(无)"))
            lines.append("- Star: %d | 语言: %s | 创建: %s" % (r.get("stars", 0), r.get("language") or "未知", (r.get("created_at") or "")[:10]))
            lines.append("- 来源: GitHub 近期热门项目（star 验证需求真实性）")
            sc = r.get("store_check")
            if sc:
                lines.append("- 商店查重: 全平台同类 %d 个 | %s" % (sc.get("total_similar", 0), sc.get("competition", "")))
                lines.append("- 分类: %s | 搜索词: %s" % (sc.get("category", ""), _sc_query_display(sc)))
            lines.append("")
            lines.append("**蓝海依据**")
            lines.append("- 该项目有真实 star（用户用脚投票证明痛点存在）")
            lines.append("- 但形态为 CLI/库/服务，普通用户无法直接使用")
            lines.append("- 商店同类少 = 移动端供给不足，适合封装成 APP")
            lines.extend(_difficulty_lines(r))
            lines.append("---\n")
    else:
        lines.append("（今日未发现供给驱动蓝海候选。可适当调高 rising 抓取量或放宽非APP形态判定。）\n")
        lines.append("---\n")

    # ===== 一C、蓝海假设（AI 推理小众人群痛点 + 双重验证）=====
    lines.append("## 一C、蓝海假设（小众人群痛点，需求验证 + 供给验证）\n")
    lines.append("> AI 推理小众人群(色弱/左撇子/多肉养护/夜班等)反复遇到但找不到好工具的痛点，\n")
    lines.append("> 用百度联想词验证「真有人在搜」+ 商店查重验证「同类少」，双重通过 = 蓝海。不依赖 GitHub。\n")
    if hypo_blue:
        for i, h in enumerate(hypo_blue, 1):
            gap = _supply_gap_flag(h.get("store_check"))
            lines.append("### 蓝海假设 %d. %s%s\n" % (i, h.get("need", "")[:80], gap))
            if h.get("audience"):
                lines.append("- 🎯 目标人群: %s" % h["audience"])
            if h.get("pain"):
                lines.append("- 💡 痛点: %s" % h["pain"])
            if h.get("why_no_tool"):
                lines.append("- ❓ 为何现有工具没解决: %s" % h["why_no_tool"])
            if h.get("store_query") and h.get("store_query") != h.get("search_verify_word"):
                lines.append("- 🔍 商店查重词(窄): %s" % h["store_query"])
            # 需求验证证据
            if h.get("related_searches"):
                lines.append("- ✅ 需求验证(百度联想词): %s" % "、".join(h["related_searches"][:5]))
            sc = h.get("store_check")
            if sc:
                lines.append("- 🏪 供给验证: 全平台同类 %d 个 | %s" % (sc.get("total_similar", 0), sc.get("competition", "")))
            if h.get("judge_reason"):
                lines.append("- ✅ AI 判断: %s" % h["judge_reason"])
                lines.append("- 分类: %s | 搜索词: %s" % (sc.get("category", ""), _sc_query_display(sc)))
            lines.append("")
            lines.append("**蓝海依据**")
            lines.append("- 人群小众(巨头不做)但痛点具体，会付费")
            lines.append("- 百度联想词证明真有人在找解决方案")
            sc2 = h.get("store_check") or {}
            if sc2.get("total_similar", 0) > config.LOW_SUPPLY_THRESHOLD:
                lines.append("- 名义同类多但经 AI 逐一核对，现有 APP 均未真正实现该细分功能（多为模糊匹配/付费推广）")
            else:
                lines.append("- 商店同类少 = 移动端供给不足")
            lines.extend(_difficulty_lines(h))
            lines.append("---\n")
    else:
        lines.append("（今日未发现双重验证通过的蓝海假设。可增大人群种子数或调宽供给阈值。）\n")
        lines.append("---\n")

    # ===== 一D、差评驱动蓝海（热门 APP 差评里「想要但没满足」的功能）=====
    lines.append("## 一D、🟢 差评驱动蓝海（热门APP差评挖掘）\n")
    lines.append("> 抓取热门 APP 的 1-2 星差评，AI 聚类「用户反复想要、但现有 APP 没做好」的功能。\n")
    lines.append("> 这类用户已证明会付费/会下载，只是现有 APP 没满足——是离真实蓝海最近的信号。\n")
    if review_blue:
        for i, d in enumerate(review_blue, 1):
            gap = _supply_gap_flag(d.get("store_check"))
            lines.append("### 差评蓝海 %d. %s%s\n" % (i, d.get("need", "")[:80], gap))
            if d.get("audience"):
                lines.append("- 🎯 目标人群: %s" % d["audience"])
            if d.get("pain"):
                lines.append("- 💔 痛点: %s" % d["pain"])
            if d.get("why_gap"):
                lines.append("- ❓ 为何现有APP没解决: %s" % d["why_gap"])
            sc = d.get("store_check")
            if sc:
                lines.append("- 🛒 供给验证: 全平台同类 %d 个 | %s" % (sc.get("total_similar", 0), sc.get("competition", "")))
                lines.append("- 分类: %s | 搜索词: %s" % (sc.get("category", ""), _sc_query_display(sc)))
            if d.get("judge_reason"):
                lines.append("- ✅ AI 判断: %s" % d["judge_reason"])
            if d.get("source_post"):
                lines.append("- 来源: %s" % d["source_post"])
            lines.append("")
            lines.append("**蓝海依据**")
            lines.append("- 用户已下载使用热门 APP 却打差评 = 痛点真实、有付费意愿")
            lines.append("- 多条差评指向同一未满足功能 = 需求共识强")
            lines.append("- 现有 APP 都没做好该细分功能 = 供给缺口")
            lines.extend(_difficulty_lines(d))
            lines.append("---\n")
    else:
        lines.append("（今日差评挖掘未发现通过验证的蓝海需求。热门 APP 差评多指向 bug/性能而非功能缺口。）\n")
        lines.append("---\n")

    # ===== 一E、GitHub Issues 驱动蓝海（feature request 高频诉求）=====
    lines.append("## 一E、🟢 Issue驱动蓝海（GitHub feature request 挖掘）\n")
    lines.append("> 抓取开源项目的 feature request issue，按评论数排序，AI 聚类高频诉求。\n")
    lines.append("> 评论多 = 需求共识强；项目方没做/没做好 = 供给缺口；适合封装成对普通用户友好的 APP。\n")
    if issues_blue:
        for i, d in enumerate(issues_blue, 1):
            gap = _supply_gap_flag(d.get("store_check"))
            lines.append("### Issue蓝海 %d. %s%s\n" % (i, d.get("need", "")[:80], gap))
            if d.get("audience"):
                lines.append("- 🎯 目标人群: %s" % d["audience"])
            if d.get("pain"):
                lines.append("- 💔 痛点: %s" % d["pain"])
            if d.get("why_gap"):
                lines.append("- ❓ 为何现有工具没解决: %s" % d["why_gap"])
            sc = d.get("store_check")
            if sc:
                lines.append("- 🛒 供给验证: 全平台同类 %d 个 | %s" % (sc.get("total_similar", 0), sc.get("competition", "")))
                lines.append("- 分类: %s | 搜索词: %s" % (sc.get("category", ""), _sc_query_display(sc)))
            if d.get("judge_reason"):
                lines.append("- ✅ AI 判断: %s" % d["judge_reason"])
            if d.get("source_post"):
                lines.append("- 来源: %s" % d["source_post"])
            lines.append("")
            lines.append("**蓝海依据**")
            lines.append("- 用户在开源项目主动提 feature request = 真实需求")
            lines.append("- 评论多 = 需求共识强，非个例")
            lines.append("- 开源工具多为开发者向，普通用户难用 = 移动端供给缺口")
            lines.extend(_difficulty_lines(d))
            lines.append("---\n")
    else:
        lines.append("（今日 Issue 挖掘未发现通过验证的蓝海需求。可调整搜索领域或增大抓取量。）\n")
        lines.append("---\n")

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
        ai_zh = ai_results.get(r["name"], {})
        if ai_zh.get("zh_summary"):
            lines.append("- 📝 中文说明: %s" % ai_zh["zh_summary"])
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

        # 实现/推广难点（来自 ai_analyzer 的 impl_difficulty/promo_difficulty）
        ai_full = ai_results.get(r["name"], {})
        if ai_full.get("impl_difficulty") or ai_full.get("promo_difficulty"):
            lines.append("**实现/推广难点**")
            if ai_full.get("impl_difficulty"):
                lines.append("- 实现难点: %s" % _fmt_field(ai_full["impl_difficulty"]))
            if ai_full.get("promo_difficulty"):
                lines.append("- 推广难点: %s" % _fmt_field(ai_full["promo_difficulty"]))
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
    lines.append("- 启用 AI（`ENABLE_AI_ANALYSIS`）可对仓库源码做深度痛点分析。")
    lines.append("- 蓝海来源：需求驱动(HN/Reddit) + 供给驱动(GitHub高star) + 蓝海假设(小众人群) + 差评挖掘(热门APP差评) + Issue挖掘(feature request)。\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate("2026-06-27", {"demands": [("翻译软件", "翻译软件")], "hot": {"baidu": [], "google": []}}, []))
