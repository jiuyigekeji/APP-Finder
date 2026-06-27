"""GitHub 仓库搜索：按关键词找近期活跃、有一定 star 的项目。"""
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta, timezone

import config


def _headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "AppFinder/1.0"}
    if config.GITHUB_TOKEN:
        h["Authorization"] = "Bearer " + config.GITHUB_TOKEN
    return h


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _query(keyword):
    since = (datetime.now(timezone.utc) - timedelta(days=config.CREATED_WITHIN_DAYS)).strftime("%Y-%m-%d")
    q = "%s pushed:>%s stars:%d..%d" % (keyword, since, config.MIN_STARS, config.MAX_STARS)
    params = urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": config.PER_KEYWORD_REPOS})
    return config.GITHUB_SEARCH_API + "?" + params


def _pick(repo):
    return {
        "name": repo.get("full_name"),
        "url": repo.get("html_url"),
        "desc": repo.get("description") or "",
        "stars": repo.get("stargazers_count", 0),
        "language": repo.get("language") or "",
        "topics": repo.get("topics") or [],
        "created_at": repo.get("created_at", ""),
        "pushed_at": repo.get("pushed_at", ""),
        "homepage": repo.get("homepage") or "",
        "owner": repo.get("owner", {}).get("login", ""),
    }


def search(keywords):
    """搜索 GitHub。

    keywords 可为 [query] 或 [(query, origin)]。
    origin 是该 query 的来源（如原始中文需求词），用于报告追溯。
    """
    seen = set()
    results = []
    for entry in keywords:
        if isinstance(entry, tuple) and len(entry) == 2:
            kw, origin = entry
        else:
            kw, origin = entry, entry
        try:
            data = _get(_query(kw))
        except Exception as e:
            print("[github] '%s' 搜索失败: %s" % (kw, e))
            continue
        for repo in data.get("items", []):
            full = repo.get("full_name")
            if full in seen:
                continue
            seen.add(full)
            item = _pick(repo)
            item["search_keyword"] = kw       # 实际搜索词（英文技术词）
            item["search_origin"] = origin    # 来源需求词（中文需求/热搜词）
            results.append(item)
            if len(results) >= config.MAX_REPOS_TO_ANALYZE:
                return results
        if not config.GITHUB_TOKEN and len(results) >= config.PER_KEYWORD_REPOS * 3:
            break
    print("[github] 共收集 %d 个候选仓库" % len(results))
    return results


def fetch_rising_repos(max_results=15):
    """供给驱动反查：抓近期 star 暴涨的新项目，作为「需求被代码验证但未APP化」的蓝海候选。

    逻辑：近期创建 + star 较高 + 按 star 降序 = 痛点真实（有人 star）但可能未产品化为 APP。
    与 search(关键词) 互补：search 是「需求词→仓库」，这里是「仓库→反查供给」。
    返回 repo 列表（结构与 _pick 一致，额外标注 source=rising）。
    """
    since = (datetime.now(timezone.utc) - timedelta(days=config.CREATED_WITHIN_DAYS)).strftime("%Y-%m-%d")
    # 抓近期高 star 项目；不加关键词，纯按热度
    # created:>近期：只抓近期创建的新项目（老项目近期push不算新需求）
    # stars:>200：已积累一定 star = 痛点真实，但可能未产品化为 APP
    q = "created:>%s stars:>200" % since
    params = urllib.parse.urlencode({
        "q": q, "sort": "stars", "order": "desc",
        "per_page": min(max_results + 5, 30),
    })
    url = config.GITHUB_SEARCH_API + "?" + params
    try:
        data = _get(url)
    except Exception as e:
        print("[github] rising 搜索失败: %s" % e)
        return []
    out = []
    for repo in data.get("items", [])[:max_results]:
        item = _pick(repo)
        # 从描述派生英文查询词（供商店查重用），不要用中文说明串
        desc = (item.get("desc") or "").strip()
        # 取描述前半句，保留英文词
        q = desc.split(",")[0].split(".")[0].split(" - ")[0].split(":")[0]
        import re as _re
        q = _re.sub(r"[^A-Za-z0-9\s]", " ", q).strip()
        if not q:
            q = item.get("name", "").split("/")[-1].replace("-", " ").replace("_", " ")
        item["search_keyword"] = q[:40]  # 真实英文查询词
        item["search_origin"] = "GitHub 近期热门项目"
        item["source"] = "rising"
        out.append(item)
    print("[github] rising 抓取 %d 个近期热门项目" % len(out))
    return out


# 判断项目形态：是否为非APP形态（CLI/库/网页/服务），适合做成APP的候选
_NON_APP_HINTS = ["cli", "command-line", "library", "sdk", "framework", "api",
                  "server", "backend", "web", "docker", "self-host", "wrapper",
                  "terminal", "console", "daemon"]
# 资源合集类（awesome/list/roadmap/cheatsheet）：star 高但无具体功能，不适合产品化为 APP
_AGGREGATE_HINTS = ["awesome", "roadmap", "cheatsheet", "cheat sheet", "list of",
                    "collection of", "curated", "resource list", "学习路线", "资源汇总"]


def is_non_app_form(repo):
    """判断仓库是否为非APP形态（CLI/库/服务/网页），即「有需求但没APP化」的候选。

    APP 形态的仓库（已是 mobile app / flutter / android / ios）不算蓝海候选。
    """
    text = ((repo.get("desc") or "") + " " + " ".join(repo.get("topics") or [])).lower()
    # 已是 APP 形态 -> 不是蓝海候选
    app_hints = ["android app", "ios app", "mobile app", "flutter app", "react native app",
                 "kotlin app", "swift app", "小程序", "wechat"]
    for h in app_hints:
        if h in text:
            return False
    # 资源合集类排除（awesome/roadmap 等，无具体功能可产品化）
    for h in _AGGREGATE_HINTS:
        if h in text:
            return False
    # 非 APP 形态标记
    for h in _NON_APP_HINTS:
        if h in text:
            return True
    return False  # 无明确形态标记，保守不算


if __name__ == "__main__":
    print(search(["LLM", "RAG"])[:2])
