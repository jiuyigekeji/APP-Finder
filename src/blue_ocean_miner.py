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


def judge_blue_ocean(demand, store_check):
    """二次判断：硬阈值前置 + AI 精判。

    收紧逻辑：
    1) 硬阈值：全平台同类数 total_similar > LOW_SUPPLY_THRESHOLD 且各商店样本都
       与需求相关 -> 直接判非蓝海（红海，不浪费 AI 调用）。
    2) 同类数 <= 阈值 -> 交给 AI 精判（样本可能不相关，需 AI 区分）。
    3) 同类数 > 阈值但样本明显不相关（名字与需求关键词无字符交集）-> 仍交 AI 精判，
       但在 prompt 里强调「名义同类多但可能无关」。
    返回 (is_blue_ocean, reason)。
    """
    threshold = config.LOW_SUPPLY_THRESHOLD
    total = store_check.get("total_similar", 0)
    need = demand.get("need", "")
    # 兼容：新格式 search_queries(列表) 取中间词，旧格式 search_query(单字符串)
    sqs = demand.get("search_queries") or []
    if isinstance(sqs, list) and sqs:
        en_sq = sqs[len(sqs) // 2]  # 中间词（中等宽窄，最接近真实供给）
    else:
        en_sq = demand.get("search_query", "")

    # 收集各商店的样本 APP 名
    existing = []
    all_names = []
    for sname, st in store_check.get("stores", {}).items():
        for it in st.get("samples", [])[:3]:
            if it.get("name"):
                existing.append("%s: %s" % (sname, it["name"]))
                all_names.append(it["name"])
    existing_str = "\n".join(existing[:10]) if existing else "（无）"

    # ---- 硬阈值前置：同类明显过多时，先看样本相关性 ----
    if total > threshold and all_names:
        # 判断样本是否与需求相关（名字与需求/搜索词有字符交集）
        ref_chars = set((need + en_sq).lower())
        relevant = 0
        for nm in all_names:
            nm_chars = set(nm.lower())
            if len(ref_chars & nm_chars) >= 2:  # 至少 2 个字符重合视为相关
                relevant += 1
        # 多数样本相关且同类远超阈值 -> 红海，直接判否
        if relevant >= max(2, len(all_names) // 2) and total > threshold * 2:
            reason = "全平台同类 %d 个（远超阈值 %d），且多数现有 APP 与需求相关，属红海" % (total, threshold)
            return False, reason

    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        # 无 AI 时：纯靠硬阈值，同类 <= 阈值才算蓝海
        return total <= threshold, ("同类 %d <= 阈值 %d" % (total, threshold) if total <= threshold else "同类偏多")

    # ---- AI 精判 ----
    supply_hint = (
        "全平台同类 APP 数: %d（蓝海判定阈值: <= %d 视为供给不足）。" % (total, threshold)
    )
    if total > threshold * 2:
        supply_hint += "当前同类数远超阈值，除非现有 APP 都与该细分需求不相关，否则应判为红海。"
    elif total > threshold:
        supply_hint += "当前同类数略超阈值，需仔细判断现有 APP 是否真正满足该细分场景。"
    else:
        supply_hint += "当前同类数较低，重点判断现有 APP 是否已覆盖该细分需求。"

    prompt = (
        "需求: %s\n"
        "目标人群: %s\n"
        "为何现有方案不够: %s\n\n"
        "%s\n\n"
        "应用商店搜索该需求后返回的现有 APP:\n%s\n\n"
        "请判断: 这些现有 APP 是否真正满足上述细分需求（注意：搜索词可能匹配到不相关的付费推广 APP）？\n"
        "判定原则：同类数远超阈值时，除非能明确指出现有 APP 都不满足该细分场景，否则判 is_blue_ocean=false。\n"
        "输出 JSON: {\"is_blue_ocean\": true/false, \"reason\": \"为何现有APP不满足/已满足\"}"
    ) % (need, demand.get("audience", ""), demand.get("why_gap", ""), supply_hint, existing_str)
    body = json.dumps({
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": "你是产品经理，严格判断细分需求是否被现有APP满足，只输出JSON。"},
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
        # AI 失败时回退到硬阈值判定
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
