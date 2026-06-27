# -*- coding: utf-8 -*-
"""应用商店查重：检查候选 APP 思路在各主流商店是否已有同类，并给出推荐分类。

数据源策略（全部免费、无需 key）：
- Apple App Store：官方 iTunes Search API，最稳，必查。
- Google Play：google-play-scraper 库（免费无 key），拿到同类数/分类/评分/下载量。
- 华为/小米/vivo/oppo：无官方免费 API，抓取各商店搜索页解析结果数，失败回退为"未知"。
"""
import urllib.request
import urllib.parse
import json
import re

import config
import cn_store_searcher

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def _get(url, headers=None, timeout=None):
    timeout = timeout or config.STORE_CHECK_TIMEOUT
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _build_query(repo):
    """提取商店查重用的查询词。优先用 search_keyword(英文技术词)，其次描述前半句，最后仓库名。"""
    # 1. 优先用 github 搜索时记录的英文技术词（最精准）
    sk = (repo.get("search_keyword") or "").strip()
    if sk and len(sk) <= 40:
        return sk
    # 2. 描述：取前半句，去噪，限长
    desc = (repo.get("desc") or "").strip()
    name = (repo.get("name") or "").split("/")[-1]
    q = desc.split(",")[0].split(".")[0].split(" - ")[0].split(":")[0]
    q = re.sub(r"[^\w\s\u4e00-\u9fa5]", " ", q).strip()
    if not q:
        q = name.replace("-", " ").replace("_", " ")
    return q[:40]


# ---------- Apple ----------
def _apple_search(query):
    params = urllib.parse.urlencode({
        "term": query, "country": config.SEARCH_COUNTRY,
        "media": "software", "limit": 10,
    })
    url = config.APPLE_SEARCH_API + "?" + params
    try:
        data = json.loads(_get(url))
        items = [{
            "name": r.get("trackName"), "developer": r.get("artistName"),
            "genre": r.get("primaryGenreName"), "url": r.get("trackViewUrl"),
            "price": r.get("formattedPrice"),
        } for r in data.get("results", []) if r.get("trackName")]
        return len(items), items
    except Exception as e:
        print("[store] apple 失败: %s" % e)
        return 0, []


# ---------- Google Play ----------
def _google_play_search(query):
    """用 google-play-scraper 库。失败返回 (0, [])。"""
    if not getattr(config, "ENABLE_GOOGLE_PLAY", True):
        return 0, []
    try:
        from google_play_scraper import search as gp_search
    except ImportError:
        print("[store] google_play: 未安装 google-play-scraper，跳过")
        return 0, []
    try:
        results = gp_search(query, n_hits=10, lang="zh", country="cn")
        items = []
        for r in results:
            if not r or not isinstance(r, dict):
                continue
            app_id = r.get("appId") or ""
            items.append({
                "name": r.get("title"),
                "developer": r.get("developer"),
                "genre": r.get("genre"),
                "score": r.get("score"),
                "installs": r.get("installs"),
                "url": "https://play.google.com/store/apps/details?id=" + app_id,
            })
        return len(items), items
    except Exception as e:
        print("[store] google_play 失败: %s" % e)
        return 0, []


# ---------- 国内商店搜索（华为/小米/vivo，移植自 SEO 项目逆向成果）----------
_CN_STORE_FN = {
    "huawei": cn_store_searcher.huawei_search,
    "xiaomi": cn_store_searcher.xiaomi_search,
    "vivo": cn_store_searcher.vivo_search,
}


def _cn_store_search(store_name, query):
    """调用国内商店搜索。失败返回 (0, [])。"""
    if not getattr(config, "ENABLE_CN_STORE_SCRAPE", True):
        return 0, []
    fn = _CN_STORE_FN.get(store_name)
    if not fn:
        return 0, []
    try:
        return fn(query)
    except Exception as e:
        print("[store] %s 搜索失败: %s" % (store_name, e))
        return 0, []


# ---------- 付费推广 APP 过滤 ----------
# 国内商店搜索结果常混入与关键词无关的付费推广位 APP，会虚高同类数。
# 过滤策略：静态黑名单 + 单查询相关性兜底 + 跨查询去重（见 finalize_promotion_filter）
# _promotion_seen: app_name(小写) -> set(查询词)，用于跨查询去重
_promotion_seen = {}
LAST_REMOVED_PROMOS = []  # ?? finalize_promotion_filter ????? APP


def _name_hit_blacklist(name):
    if not name:
        return False
    low = name.lower()
    for bad in getattr(config, "PROMOTION_BLACKLIST", []):
        if bad.lower() in low:
            return True
    return False


def _relevance(name, query):
    """APP 名与查询词的字符交集比例（0~1）。用于兜底识别无关推广。"""
    if not name or not query:
        return 0.0
    low_name = name.lower()
    low_query = query.lower()
    common = sum(1 for ch in low_query if ch in low_name)
    return common / max(1, len(low_query))


def _is_promoted_item(name, query, store_name):
    """判断单个 APP 是否为付费推广（应剔除）。"""
    if _name_hit_blacklist(name):
        return True
    # 相关性兜底：仅对国内商店启用（海外商店结果相关性通常较好）
    if store_name in ("huawei", "xiaomi", "vivo"):
        min_rel = getattr(config, "PROMOTION_RELEVANCE_MIN", 0.0)
        if min_rel > 0 and query:
            if _relevance(name, query) < min_rel:
                return True
    return False


def _filter_items(items, query, store_name):
    """过滤推广 APP，并记录跨查询出现情况。返回过滤后的 items。"""
    filtered = []
    for it in items:
        name = (it.get("name") or "").strip()
        if _is_promoted_item(name, query, store_name):
            continue
        filtered.append(it)
        # 记录跨查询出现（仅用名字做 key，子串归一）
        if name:
            key = name.lower()
            _promotion_seen.setdefault(key, set()).add(query)
    return filtered


def finalize_promotion_filter(store_checks):
    """运行末尾回扫：把跨查询重复 >= 阈值的 APP 从所有结果剔除并重算 total。

    store_checks: list of dict（check/check_dual 的返回，会就地修改）。
    返回被剔除的推广 APP 名列表（供报告参考）。
    """
    threshold = getattr(config, "PROMOTION_REPEAT_THRESHOLD", 3)
    promoted_names = {name for name, qs in _promotion_seen.items() if len(qs) >= threshold}
    if not promoted_names:
        return []
    for sc in store_checks:
        if not sc or not sc.get("stores"):
            continue
        new_total = 0
        for sname, st in sc["stores"].items():
            kept = [it for it in st.get("samples", [])
                    if (it.get("name") or "").strip().lower() not in promoted_names]
            st["samples"] = kept
            st["count"] = len(kept)
            new_total += len(kept)
        sc["total_similar"] = new_total
    globals()["LAST_REMOVED_PROMOS"] = sorted(promoted_names)
    return sorted(promoted_names)

# ---------- 分类 ----------
APPLE_GENRE_MAP = {
    "Productivity": "效率", "Utilities": "工具", "Social Networking": "社交",
    "Communication": "通讯", "Education": "教育", "Book": "图书", "News": "新闻",
    "Lifestyle": "生活", "Health & Fitness": "健康健美", "Finance": "财务",
    "Photo & Video": "摄影与录像", "Music": "音乐", "Entertainment": "娱乐",
    "Medical": "医疗", "Travel": "旅游", "Navigation": "导航",
    "Food & Drink": "美食佳饮", "Business": "商务", "Graphics & Design": "图形和设计",
    "Reference": "工具", "Shopping": "购物",
}
PLAY_GENRE_KEYWORDS = {
    "Productivity": "效率", "Tools": "工具", "Social": "社交", "Communication": "通讯",
    "Education": "教育", "Books": "图书", "News": "新闻", "Lifestyle": "生活",
    "Health": "健康健美", "Finance": "财务", "Photography": "摄影与录像",
    "Music": "音乐", "Entertainment": "娱乐", "Medical": "医疗", "Travel": "旅游",
    "Maps": "导航", "Food": "美食佳饮", "Business": "商务", "Design": "图形和设计",
    "Shopping": "购物",
}


def _classify(repo, apple_items=None, play_items=None):
    """优先用商店真实分类，否则关键词推断。"""
    genres = []
    for it in (apple_items or []):
        if it.get("genre"):
            genres.append(APPLE_GENRE_MAP.get(it["genre"], it["genre"]))
    for it in (play_items or []):
        g = it.get("genre") or ""
        for k, v in PLAY_GENRE_KEYWORDS.items():
            if k.lower() in g.lower():
                genres.append(v)
                break
    if genres:
        return max(set(genres), key=genres.count)
    text = ((repo.get("desc") or "") + " " + " ".join(repo.get("topics") or [])).lower()
    best, best_score = "工具", 0
    for cat, kws in config.CATEGORY_KEYWORD_MAP.items():
        score = sum(1 for k in kws if k in text)
        if score > best_score:
            best, best_score = cat, score
    return best


def _competition_level(apple_count, play_count, cn_total):
    total_real = apple_count + play_count
    if total_real == 0 and cn_total == 0:
        return "蓝海（各商店均未发现同类，建议重点验证）"
    if total_real == 0:
        return "低竞争（国内有零星同类，海外未见）"
    if total_real <= 3:
        return "低竞争"
    if total_real <= 8:
        return "中等竞争"
    return "红海（同类众多，需差异化）"


def check(repo):
    query = _build_query(repo)
    apple_count, apple_items = _apple_search(query)
    play_count, play_items = _google_play_search(query)
    category = _classify(repo, apple_items, play_items)

    apple_items = [it for it in apple_items if not _name_hit_blacklist((it.get("name") or ""))]
    apple_count = len(apple_items)
    play_items = [it for it in play_items if not _name_hit_blacklist((it.get("name") or ""))]
    play_count = len(play_items)
    stores = {
        "apple": {"count": apple_count, "samples": apple_items},
        "google_play": {"count": play_count, "samples": play_items},
    }
    cn_total = 0
    for sname in config.STORE_SEARCH_URLS:
        c, items = _cn_store_search(sname, query)
        items = _filter_items(items, query, sname)
        c = len(items)
        stores[sname] = {"count": c, "samples": items}
        if c > 0:
            cn_total += c

    total = apple_count + play_count + cn_total
    return {
        "query": query,
        "category": category,
        "stores": stores,
        "total_similar": total,
        "competition": _competition_level(apple_count, play_count, cn_total),
    }


def check_dual(en_query, zh_query):
    """海外商店用英文查，国内商店用中文查。

    en_query: Apple/Google Play 的英文搜索词
    zh_query: 华为/小米/vivo 的中文搜索词
    """
    apple_count, apple_items = _apple_search(en_query)
    play_count, play_items = _google_play_search(en_query)
    category = _classify({"desc": en_query, "topics": []}, apple_items, play_items)

    apple_items = [it for it in apple_items if not _name_hit_blacklist((it.get("name") or ""))]
    apple_count = len(apple_items)
    play_items = [it for it in play_items if not _name_hit_blacklist((it.get("name") or ""))]
    play_count = len(play_items)
    stores = {
        "apple": {"count": apple_count, "samples": apple_items},
        "google_play": {"count": play_count, "samples": play_items},
    }
    cn_total = 0
    for sname in config.STORE_SEARCH_URLS:
        c, items = _cn_store_search(sname, zh_query)
        items = _filter_items(items, zh_query, sname)
        c = len(items)
        stores[sname] = {"count": c, "samples": items}
        if c > 0:
            cn_total += c

    total = apple_count + play_count + cn_total
    return {
        "query_en": en_query,
        "query_zh": zh_query,
        "category": category,
        "stores": stores,
        "total_similar": total,
        "competition": _competition_level(apple_count, play_count, cn_total),
    }


if __name__ == "__main__":
    import pprint
    pprint.pprint(check({"desc": "A habit tracker app", "name": "x/habit", "topics": ["habit"]}))
