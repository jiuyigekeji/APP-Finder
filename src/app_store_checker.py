# -*- coding: utf-8 -*-
"""应用商店查重：检查候选 APP 思路在主流商店是否已有同类，并给出推荐分类。

数据源策略（全部免费、无需 key）：
- Apple App Store：官方 iTunes Search API（免费、无 key），最稳，必查。
- Google Play / 华为 / 小米 / VIVO / OPPO：无官方免费搜索 API，
  默认用 Google 站内搜索（site:domain query）间接取证，受 ENABLE_GOOGLE_SITE_SEARCH 开关控制，
  默认关闭（不稳定且慢），关闭时标注「未开启，建议人工复查」。
"""
import urllib.request
import urllib.parse
import json
import re

import config

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def _get(url, headers=None, timeout=None):
    timeout = timeout or config.STORE_CHECK_TIMEOUT
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _build_query(repo):
    desc = (repo.get("desc") or "").strip()
    name = (repo.get("name") or "").split("/")[-1]
    q = desc.split(",")[0].split(".")[0].split(" - ")[0]
    q = re.sub(r"[^\w\s\u4e00-\u9fa5]", " ", q).strip()
    if not q:
        q = name.replace("-", " ").replace("_", " ")
    return q[:60]


def _apple_search(query):
    """官方 iTunes Search API。返回 (已有同类数, 示例列表)。"""
    params = urllib.parse.urlencode({
        "term": query, "country": config.SEARCH_COUNTRY,
        "media": "software", "limit": 10,
    })
    url = config.APPLE_SEARCH_API + "?" + params
    try:
        data = json.loads(_get(url))
        results = data.get("results", [])
        items = [{
            "name": r.get("trackName"),
            "developer": r.get("artistName"),
            "genre": r.get("primaryGenreName"),
            "url": r.get("trackViewUrl"),
            "price": r.get("formattedPrice"),
        } for r in results if r.get("trackName")]
        return len(items), items
    except Exception as e:
        print("[store] apple 搜索失败: %s" % e)
        return 0, []


def _google_site_search(site_domain, query):
    q = "site:%s %s" % (site_domain, query)
    url = config.GOOGLE_SEARCH_URL + "?" + urllib.parse.urlencode({"q": q, "hl": "zh-CN", "num": 10})
    try:
        html = _get(url)
        m = re.search(r"约\s*([\d,]+)\s*条结果", html) or re.search(r"id=\"result-stats\">.*?([\d,]+)\s*条", html)
        count = int(m.group(1).replace(",", "")) if m else len(re.findall(r"<h3", html))
        titles = re.findall(r"<h3[^>]*>(.*?)</h3>", html)
        titles = [re.sub(r"<[^>]+>", "", t).strip() for t in titles if t.strip()][:3]
        return max(count, 1 if titles else 0), titles
    except Exception as e:
        print("[store] %s 站内搜索失败: %s" % (site_domain, e))
        return 0, []


# Apple 真实分类 -> 我们的分类体系归一化
APPLE_GENRE_MAP = {
    "Productivity": "效率", "Utilities": "工具", "Social Networking": "社交",
    "Communication": "通讯", "Education": "教育", "Book": "图书", "News": "新闻",
    "Lifestyle": "生活", "Health & Fitness": "健康健美", "Finance": "财务",
    "Photo & Video": "摄影与录像", "Music": "音乐", "Entertainment": "娱乐",
    "Medical": "医疗", "Travel": "旅游", "Navigation": "导航",
    "Food & Drink": "美食佳饮", "Business": "商务", "Graphics & Design": "图形和设计",
    "Reference": "工具", "Shopping": "购物",
}


def _classify(repo, apple_items=None):
    """优先用 Apple 真实分类（出现次数最多），否则关键词推断。"""
    if apple_items:
        genres = [it["genre"] for it in apple_items if it.get("genre")]
        if genres:
            top = max(set(genres), key=genres.count)
            return APPLE_GENRE_MAP.get(top, top)
    text = ((repo.get("desc") or "") + " " + " ".join(repo.get("topics") or [])).lower()
    best, best_score = "工具", 0
    for cat, kws in config.CATEGORY_KEYWORD_MAP.items():
        score = sum(1 for k in kws if k in text)
        if score > best_score:
            best, best_score = cat, score
    return best


def _competition_level(total, apple_count):
    # 以 Apple 为主判断（最可靠），其他商店只作参考
    if apple_count == 0:
        return "蓝海（Apple 未发现同类，建议重点验证）"
    if apple_count <= 3:
        return "低竞争"
    if apple_count <= 8:
        return "中等竞争"
    return "红海（同类众多，需差异化）"


def check(repo):
    query = _build_query(repo)
    apple_count, apple_items = _apple_search(query)
    category = _classify(repo, apple_items)
    stores = {"apple": {"count": apple_count, "samples": apple_items}}

    if config.ENABLE_GOOGLE_SITE_SEARCH:
        for store_name, domain in list(config.STORE_SITE_DOMAINS.items()):
            count, titles = _google_site_search(domain, query)
            stores[store_name] = {"count": count, "samples": titles}
    else:
        for store_name in config.STORE_SITE_DOMAINS:
            stores[store_name] = {"count": -1, "samples": [], "note": "未开启站内搜索，建议人工复查"}

    total = apple_count + sum(v["count"] for v in stores.values() if v.get("count", 0) > 0)
    return {
        "query": query,
        "category": category,
        "stores": stores,
        "total_similar": total,
        "competition": _competition_level(total, apple_count),
    }


if __name__ == "__main__":
    r = {"desc": "A habit tracker app", "name": "x/habit", "topics": ["habit", "productivity"]}
    import pprint
    pprint.pprint(check(r))
