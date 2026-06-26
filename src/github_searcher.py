"""GitHub 仓库搜索：按关键词找近期活跃、有一定 star 的项目。"""
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta, timezone

import config


def _headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "AndroidAppFinder/1.0"}
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
    seen = set()
    results = []
    for kw in keywords:
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
            results.append(_pick(repo))
            if len(results) >= config.MAX_REPOS_TO_ANALYZE:
                return results
        if not config.GITHUB_TOKEN and len(results) >= config.PER_KEYWORD_REPOS * 3:
            break
    print("[github] 共收集 %d 个候选仓库" % len(results))
    return results


if __name__ == "__main__":
    print(search(["LLM", "RAG"])[:2])
