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

# 搜这类帖子：用户主动表达「想要/找不到」某工具
DEMAND_QUERIES = [
    "want an app that",
    "wish there was an app",
    "is there an app for",
    "need a tool that",
    "app that doesn t exist",
    "cannot find an app",
    "would pay for an app",
]
MIN_POINTS = 3         # 最低点赞，过滤噪声
MAX_POSTS_PER_QUERY = 8
MAX_TOTAL_POSTS = 30


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _fetch_posts():
    """从 HN 抓需求类帖子。返回 [{title, url, points, objectID}]。"""
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
    """用 AI 从帖子标题批量抽取结构化蓝海需求。

    返回 [{need, audience, why_gap, search_query}]。
    search_query 是用于商店查重的英文关键词。
    """
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return []
    titles = [p["title"] for p in posts]
    prompt = (
        "你是一名产品经理，专长发现蓝海 APP 机会。下面是用户在 Hacker News 上主动表达的未满足需求。"
        "请从中抽取真正有蓝海潜力的需求（排除已饱和的红海如记账/计算器/天气/笔记），输出 JSON 数组，每项：\n"
        "need: 需求是什么（一句话）\n"
        "audience: 目标细分人群\n"
        "why_gap: 为什么现有方案不够/缺失\n"
        "search_query: 用于在应用商店搜索同类 APP 的英文关键词（1-3个词）\n"
        "只返回真正细分、小众、供给不足的需求，最多 8 个。\n\n"
        "帖子标题列表：\n%s"
    ) % "\n".join(titles)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode("utf-8")
    url = "%s/models/%s:generateContent?key=%s" % (config.AI_API_BASE, config.AI_MODEL, config.AI_API_KEY)
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
        if isinstance(result, list):
            print("[blueocean] AI 抽取 %d 条蓝海需求" % len(result))
            return result
    except Exception as e:
        print("[blueocean] AI 抽取失败: %s" % e)
    return []


def _rule_extract_demands(posts):
    """无 AI 时，规则抽取：把标题作为需求，取关键词作搜索词。"""
    out = []
    for p in posts:
        title = p["title"]
        # 去掉 Ask HN: / Show HN: 前缀
        clean = title.replace("Ask HN:", "").replace("Show HN:", "").strip()
        out.append({
            "need": clean,
            "audience": "",
            "why_gap": "",
            "search_query": clean[:40],
        })
    return out[:10]


def mine():
    """主入口：抓 HN 帖子 → AI/规则抽取需求。返回 [需求 dict]。"""
    posts = _fetch_posts()
    if not posts:
        return []
    demands = _ai_extract_demands(posts)
    if not demands:
        demands = _rule_extract_demands(posts)
    # 附上来源帖
    for i, d in enumerate(demands):
        if i < len(posts):
            d["source_post"] = posts[i]["title"]
            d["source_url"] = posts[i]["url"]
            d["source_points"] = posts[i]["points"]
    return demands


if __name__ == "__main__":
    import pprint
    pprint.pprint(mine()[:3])
