# -*- coding: utf-8 -*-
"""蓝海需求挖掘：从 Hacker News 抓「用户主动表达未满足需求」的帖子。

HN 用户常发「Ask HN: I want an app that...」「Is there an app for...」类帖子，
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
MAX_TOTAL_POSTS = 30


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


def _ai_extract_demands(posts):
    """用 AI 从帖子标题抽取结构化蓝海需求，并直接判断是否蓝海。"""
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return []
    titles = [p["title"] for p in posts]
    prompt = (
        "你是一名资深产品经理，专长发现蓝海 APP 机会。下面是用户在 Hacker News 上主动表达的未满足需求。\n"
        "请从中识别真正有蓝海潜力的细分需求（排除已饱和红海：记账/计算器/天气/笔记/清理/输入法/壁纸/"
        "音乐播放器/文件管理器/翻译/录音转文字/PDF转换/背单词/截图），输出 JSON 对象：\n"
        '{"demands": [{"need":"具体需求(含场景,一句话)","audience":"细分人群",'
        '"why_gap":"为何现有方案不够","search_query":"4-8词的精准英文短语用于商店搜索",'
        '"existing_apps":"现有最接近的APP及不足,若无写none","is_blue_ocean":true}]}\n'
        "要求：\n"
        "1. search_query 必须具体精准(如 'search midi files by note pattern' 而非 'midi search')\n"
        "2. 只返回 is_blue_ocean=true 且真正细分小众的需求，最多 6 个\n"
        "3. 只输出 JSON，不要 markdown 代码块\n\n"
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
    """二次判断：把商店查重结果喂给 AI，判断现有 APP 是否真满足该细分需求。

    返回 (is_blue_ocean, reason)。AI 看到现有 APP 后能区分「名义上有同类」和「真正满足需求」。
    """
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return demand.get("is_blue_ocean", False), ""
    # 收集各商店的样本 APP 名
    existing = []
    for sname, st in store_check.get("stores", {}).items():
        for it in st.get("samples", [])[:3]:
            if it.get("name"):
                existing.append("%s: %s" % (sname, it["name"]))
    existing_str = "\n".join(existing[:10]) if existing else "（无）"

    prompt = (
        "需求: %s\n"
        "目标人群: %s\n"
        "为何现有方案不够: %s\n\n"
        "应用商店搜索该需求后返回的现有 APP:\n%s\n\n"
        "请判断: 这些现有 APP 是否真正满足上述细分需求（注意：搜索词可能匹配到不相关的 APP）？\n"
        "输出 JSON: {\"is_blue_ocean\": true/false, \"reason\": \"为何现有APP不满足/已满足\"}"
    ) % (demand.get("need", ""), demand.get("audience", ""),
         demand.get("why_gap", ""), existing_str)
    body = json.dumps({
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": "你是产品经理，判断细分需求是否被现有APP满足，只输出JSON。"},
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
        return demand.get("is_blue_ocean", False), ""


def mine():
    posts = _fetch_posts()
    if not posts:
        return []
    demands = _ai_extract_demands(posts)
    if not demands:
        demands = _rule_extract_demands(posts)
    # 不按索引附 source（AI 抽取顺序与原帖无关，强附会误导）
    # 来源统一标注为 Hacker News
    for d in demands:
        d["source_post"] = "Hacker News 需求帖"
        d["source_url"] = "https://news.ycombinator.com/"
        d["source_points"] = 0
    return demands


if __name__ == "__main__":
    import pprint
    pprint.pprint(mine()[:3])
