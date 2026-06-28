# -*- coding: utf-8 -*-
"""蓝海需求挖掘：从 Hacker News + Reddit 抓「用户主动表达未满足需求」的帖子。

来源：
- Hacker News: Algolia API，按 "want an app that" 等模板搜 Ask HN 帖
- Reddit: r/somebodymakethis、r/AppIdeas 的 RSS feed（用户直接发帖求做某 APP）

这类需求不在搜索热词里（联想词只给高频红海），而是细分人群的真实痛点。
AI 从帖子抽取结构化需求，再用商店查重验证供给是否不足。
"""
import urllib.request
import urllib.parse
import json
import time

import config

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
HN_SEARCH = "https://hn.algolia.com/api/v1/search"

DEMAND_QUERIES = [
    "want an app that",
    "wish there was an app",
    "is there an app for",
    "need a tool that",
    "app that doesn t exist",
    "cannot find an app",
    "would pay for an app",
]
MIN_POINTS = 3
MAX_POSTS_PER_QUERY = 8
MAX_TOTAL_POSTS = 40


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _fetch_posts():
    posts = []
    seen = set()
    for q in DEMAND_QUERIES:
        params = urllib.parse.urlencode({
            "query": q, "tags": "story", "hitsPerPage": MAX_POSTS_PER_QUERY + 5,
        })
        try:
            data = _get(HN_SEARCH + "?" + params)
        except Exception as e:
            print("[blueocean] HN 搜索 '%s' 失败: %s" % (q, e))
            continue
        for h in data.get("hits", []):
            oid = h.get("objectID")
            if oid in seen:
                continue
            seen.add(oid)
            pts = h.get("points") or 0
            if pts < MIN_POINTS:
                continue
            posts.append({
                "title": h.get("title") or "",
                "url": h.get("url") or "https://news.ycombinator.com/item?id=" + oid,
                "points": pts,
                "objectID": oid,
            })
        if len(posts) >= MAX_TOTAL_POSTS:
            break
        time.sleep(0.5)
    posts.sort(key=lambda x: x["points"], reverse=True)
    print("[blueocean] HN 抓取 %d 条需求帖" % len(posts))
    return posts[:MAX_TOTAL_POSTS]


def _fetch_reddit_posts():
    """从 Reddit r/somebodymakethis、r/AppIdeas 抓需求帖（RSS/Atom feed，免费无 key）。

    这两个 subreddit 用户直接发帖表达「求做一个 APP」，质量高、非突发。
    Reddit JSON API 对服务器 IP 严格 403，RSS feed 更宽松。
    """
    import xml.etree.ElementTree as ET
    subs = ["somebodymakethis", "AppIdeas"]
    posts = []
    seen = set()
    for sub in subs:
        url = "https://www.reddit.com/r/%s/top/.rss?t=week&limit=12" % sub
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            root = ET.fromstring(raw)
        except Exception as e:
            print("[blueocean] Reddit r/%s 抓取失败: %s" % (sub, e))
            time.sleep(2)
            continue
        # Atom: entry > title, entry > link[href], entry > id
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            title_el = entry.find("a:title", ns)
            if title_el is None or not (title_el.text or "").strip():
                continue
            title = title_el.text.strip()
            link_el = entry.find("a:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            id_el = entry.find("a:id", ns)
            oid = (id_el.text if id_el is not None and id_el.text else link) or title
            if oid in seen:
                continue
            seen.add(oid)
            posts.append({
                "title": title,
                "url": link,
                "points": 0,  # RSS 不含 score，用 t=week top 隐含已过滤
                "objectID": "reddit_" + oid[-20:],
                "source": "reddit/%s" % sub,
            })
        time.sleep(2)  # 避免 429
        if len(posts) >= 20:
            break
    print("[blueocean] Reddit 抓取 %d 条需求帖" % len(posts))
    return posts


def _ai_extract_demands(posts):
    """用 AI 从帖子标题抽取结构化蓝海需求，并直接判断是否蓝海。"""
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return []
    titles = [p["title"] for p in posts]
    prompt = (
        "你是一名资深产品经理，专长发现蓝海 APP 机会。下面是用户在社区(Hacker News/Reddit)主动表达的未满足需求。\n"
        "请按以下标准筛选真正有蓝海潜力的需求：\n"
        "- 需求真实：有具体使用场景 + 明确细分人群（不是泛泛的点子）\n"
        "- 痛点具体：用户在找某个工具/能力但找不到，而非随便聊聊\n"
        "- 非红海：排除记账/计算器/天气/笔记/清理/输入法/壁纸/音乐播放器/文件管理器/翻译/录音转文字/PDF转换/背单词/截图/待办/番茄钟\n"
        "输出 JSON 对象：\n"
        '{"demands": [{"need":"具体需求(含场景,一句话)","audience":"细分人群",'
        '"why_gap":"为何现有方案不够","search_queries":["宽泛词2-3个","中等词4-6个","精准词6-10个"],'
        '"existing_apps":"现有最接近的APP及不足,若无写none","is_blue_ocean":true,"real_demand":true/false}]}\n'
        "要求：\n"
        "1. search_queries 给3个不同宽窄的英文短语，用于商店查重交叉验证（宽/中/窄各一）\n"
        "2. real_demand：该需求是否有明确场景+人群+找工具意图，纯点子/吐槽设为 false\n"
        "3. 只返回 is_blue_ocean=true 且 real_demand=true 的需求，最多 6 个\n"
        "4. 宁缺毋滥：宁可少给，不要给红海或伪需求\n"
        "5. 只输出 JSON，不要 markdown 代码块\n\n"
        "帖子标题列表：\n%s"
    ) % "\n".join(titles)
    body = json.dumps({
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": "你是产品经理，只输出合法 JSON，不要代码块。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    url = config.AI_API_BASE.rstrip("/") + "/chat/completions"
    try:
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + config.AI_API_KEY,
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        text = data["choices"][0]["message"]["content"]
        result = json.loads(text)
        if isinstance(result, dict):
            for k in ("demands", "data", "items", "list"):
                if k in result and isinstance(result[k], list):
                    result = result[k]
                    break
        if isinstance(result, list):
            print("[blueocean] AI 抽取 %d 条蓝海需求" % len(result))
            return result
    except Exception as e:
        print("[blueocean] AI 抽取失败: %s" % e)
    return []


def _rule_extract_demands(posts):
    out = []
    for p in posts:
        clean = p["title"].replace("Ask HN:", "").replace("Show HN:", "").strip()
        out.append({
            "need": clean, "audience": "", "why_gap": "",
            "search_query": clean[:40], "is_blue_ocean": False,
        })
    return out[:10]


def judge_blue_ocean(demand, store_check, force_ai=False):
    """二次判断：硬阈值前置 + AI 精判。

    force_ai=True 时跳过硬阈值前置（用于蓝海假设：商店模糊匹配常查到一堆无关APP，
    不能因「同类多+名字字符重合」就判红海，必须让 AI 看分类逐一判断）。
    返回 (is_blue_ocean, reason)。
    """
    threshold = config.LOW_SUPPLY_THRESHOLD
    total = store_check.get("total_similar", 0)
    need = demand.get("need", "")
    sqs = demand.get("search_queries") or []
    if isinstance(sqs, list) and sqs:
        en_sq = sqs[len(sqs) // 2]
    else:
        en_sq = (demand.get("store_query") or demand.get("search_query")
                 or demand.get("search_verify_word") or demand.get("need", ""))

    # 收集各商店样本（含分类，帮 AI 判断相关性）
    existing = []
    all_names = []
    for sname, st in store_check.get("stores", {}).items():
        for it in st.get("samples", [])[:3]:
            if it.get("name"):
                genre = it.get("genre") or ""
                extra = (" [%s]" % genre) if genre else ""
                existing.append("%s: %s%s" % (sname, it["name"], extra))
                all_names.append(it["name"])
    existing_str = "\n".join(existing[:12]) if existing else "（无）"

    # ---- 硬阈值前置（force_ai 时跳过）----
    if not force_ai and total > threshold and all_names:
        ref_chars = set((need + en_sq).lower())
        relevant = 0
        for nm in all_names:
            if len(ref_chars & set(nm.lower())) >= 2:
                relevant += 1
        if relevant >= max(2, len(all_names) // 2) and total > threshold * 2:
            return False, "全平台同类 %d 个（远超阈值 %d），且多数现有 APP 与需求相关，属红海" % (total, threshold)

    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return total <= threshold, ("同类 %d <= 阈值 %d" % (total, threshold) if total <= threshold else "同类偏多")

    # ---- AI 精判：逐一判断现有 APP 是否真正实现该功能 ----
    supply_hint = "全平台名义同类 APP 数: %d。" % total
    if force_ai:
        supply_hint += "注意：商店搜索是模糊匹配，这 %d 个里很多可能只是标题含相关字、实际功能完全不同（如查「骑手防撞单」可能匹配到「医院挂号」「提醒事项」）。请逐一判断每个 APP 是否真正实现了下述具体功能。" % total
    elif total > threshold * 2:
        supply_hint += "当前同类数远超阈值，除非现有 APP 都与该细分需求不相关，否则判红海。"

    prompt = (
        "需求: %s\n"
        "目标人群: %s\n"
        "为何现有方案不够: %s\n"
        "商店查重词: %s\n\n"
        "%s\n\n"
        "商店搜索返回的现有 APP（含分类）:\n%s\n\n"
        "请逐一判断：这些 APP 里，是否有任何一个真正实现了上述具体功能（不是名字沾边，而是核心功能匹配）？\n"
        "判定原则：\n"
        "- 只要有一个 APP 真正实现了该功能 -> is_blue_ocean=false（已有满足方案）\n"
        "- 全部都不实现（只是模糊匹配/付费推广/同类但功能不同）-> is_blue_ocean=true（真蓝海）\n"
        "输出 JSON: {\"is_blue_ocean\": true/false, \"reason\": \"逐个判断结论：哪些APP不相关，是否有APP真正满足\"}"
    ) % (need, demand.get("audience", ""), demand.get("why_gap", "") or demand.get("pain", ""), en_sq, supply_hint, existing_str)
    body = json.dumps({
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": "你是产品经理，逐一判断现有APP是否真正实现某具体功能，只输出JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    url = config.AI_API_BASE.rstrip("/") + "/chat/completions"
    try:
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + config.AI_API_KEY,
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        result = json.loads(data["choices"][0]["message"]["content"])
        return bool(result.get("is_blue_ocean")), result.get("reason", "")
    except Exception as e:
        print("[blueocean] 二次判断失败: %s" % e)
        return total <= threshold, ("AI 失败，回退硬阈值：同类 %d" % total)

def mine():
    # 合并两个来源：HN（按模板搜）+ Reddit（需求社区整帖）
    hn_posts = _fetch_posts()
    reddit_posts = _fetch_reddit_posts()
    posts = hn_posts + reddit_posts
    if not posts:
        return []
    demands = _ai_extract_demands(posts)
    if not demands:
        demands = _rule_extract_demands(posts)
    # 来源统一标注为「社区需求帖」（HN + Reddit）
    for d in demands:
        d["source_post"] = "社区需求帖 (HN/Reddit)"
        d["source_url"] = "https://news.ycombinator.com/ , https://www.reddit.com/r/somebodymakethis"
        d["source_points"] = 0
    return demands


if __name__ == "__main__":
    import pprint
    pprint.pprint(mine()[:3])
