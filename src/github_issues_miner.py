# -*- coding: utf-8 -*-
"""蓝海来源五：GitHub Issues 高频 feature request 挖掘。

核心思想：开源项目的 Issue 区里，用户主动提的 feature request = 真实需求。
当一个功能被多人反复请求（issue 多、评论多），但项目方没做/没做好，
说明存在「需求被验证、但供给不足」的缺口——尤其适合封装成对普通用户友好的 APP。

数据源：GitHub Search Issues API（免费、有 token 提额、稳定，已验证可用）。
策略：在几个「需求旺、APP 化空间大」的领域仓库里，搜高频 feature request。
"""
import urllib.request
import urllib.parse
import json
import time

import config

UA = "APP-Finder"

# 搜索领域：每个领域给一组关键词，在 GitHub 全局搜 feature/enhancement issue。
# 刻意选「有真实工具需求、且移动端有空间」的领域，避开纯基建/纯 AI 风口。
ISSUE_TOPICS = [
    # (英文搜索词, 中文领域)
    ("habit tracker", "习惯打卡"),
    ("expense manager", "记账理财"),
    ("note taking", "笔记"),
    ("pomodoro timer", "番茄钟"),
    ("meditation", "冥想"),
    ("language learning", "语言学习"),
    ("recipe manager", "食谱"),
    ("plant care", "植物养护"),
    ("sleep tracker", "睡眠"),
    ("reading list", "阅读清单"),
    ("wifi analyzer", "网络工具"),
    ("file sync", "文件同步"),
]


def _gh_get(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
    })
    tok = config.GITHUB_TOKEN
    if tok:
        req.add_header("Authorization", "token " + tok)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _fetch_feature_issues(topic_en, per_topic=8):
    """搜某领域高频 feature request issue（按评论数排序）。"""
    q = '%s label:enhancement state:open' % topic_en
    params = urllib.parse.urlencode({"q": q, "sort": "comments", "order": "desc", "per_page": per_topic})
    url = config.GITHUB_SEARCH_API.replace("/repositories", "/issues") + "?" + params
    try:
        data = _gh_get(url)
    except Exception as e:
        print("[issues] 搜索 '%s' 失败: %s" % (topic_en, e))
        return []
    items = data.get("items", [])
    out = []
    for it in items:
        title = (it.get("title") or "").strip()
        if not title or len(title) < 6:
            continue
        out.append({
            "title": title,
            "repo": it.get("repository_url", "").replace("https://api.github.com/repos/", ""),
            "comments": it.get("comments", 0),
            "url": it.get("html_url", ""),
            "topic": topic_en,
        })
    print("[issues] %s -> %d 条 feature request" % (topic_en, len(out)))
    return out


def _ai_extract_demands(all_issues):
    """AI 从 feature request issue 里聚类出蓝海需求。"""
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return []
    if not all_issues:
        return []
    # 只取评论数较高的（评论多 = 需求共识强），并截断标题
    all_issues = sorted(all_issues, key=lambda x: x.get("comments", 0), reverse=True)[:40]
    lines = []
    for i, it in enumerate(all_issues, 1):
        lines.append("%d. [%s/评论%d] %s" % (i, it["topic"], it.get("comments", 0), it["title"][:100]))
    blob = "\n".join(lines)
    prompt = (
        "你是一名资深产品经理，专长从开源项目的 feature request 里发现蓝海 APP 机会。\n"
        "下面是多个开源工具项目的用户 feature request（功能请求）issue，按评论数排序，评论越多说明需求共识越强。\n\n"
        "%s\n\n"
        "请从中挖掘「被多个项目用户反复请求、但现有开源工具/APP 都没满足好」的功能缺口，形成可做成独立 APP 的蓝海机会。\n"
        "挖掘原则：\n"
        "1. 聚类同类请求：多个 issue 指向同一未满足需求才提取\n"
        "2. 必须是面向普通用户的功能（不是开发者/部署/性能优化类请求）\n"
        "3. 排除红海：记账/计算器/天气/笔记/清理/输入法/壁纸/播放器/翻译/背单词\n"
        "4. 宁缺毋滥，最多 4 个最有蓝海潜力的需求\n"
        "5. search_queries 给 2-3 个英文搜索词，store_query 给 6-12 字中文场景词\n\n"
        "输出 JSON: {\"demands\":[{\"need\":\"具体需求(含场景)\",\"audience\":\"人群\","
        "\"pain\":\"痛点(用户issue里反复出现的请求)\","
        "\"why_gap\":\"为何现有工具没解决\",\"search_queries\":[\"英文词\"],\"store_query\":\"中文查重词\"}]}\n"
        "只输出 JSON，不要 markdown。"
    ) % blob
    body = json.dumps({
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": "你是产品经理，从feature request里挖蓝海机会，只输出合法JSON。"},
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
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        text = data["choices"][0]["message"]["content"]
        result = json.loads(text)
        if isinstance(result, dict):
            for k in ("demands", "data", "items", "list"):
                if k in result and isinstance(result[k], list):
                    result = result[k]
                    break
        if isinstance(result, list):
            return result
    except Exception as e:
        print("[issues] AI 抽取失败: %s" % e)
    return []


def mine(max_topics=6):
    """主入口：搜若干领域 feature request -> AI 聚类蓝海需求。"""
    from concurrent.futures import ThreadPoolExecutor

    topics = ISSUE_TOPICS[:max_topics]
    all_issues = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for iss in ex.map(lambda t: _fetch_feature_issues(t[0]), topics):
            all_issues.extend(iss)
            time.sleep(0.3)  # GitHub search API 限速较严
    print("[issues] 共抓到 feature request %d 条，交 AI 抽取 ..." % len(all_issues))
    if not all_issues:
        return []
    demands = _ai_extract_demands(all_issues)
    for d in demands:
        d["source_post"] = "GitHub feature request 挖掘"
        d["source_url"] = "https://github.com/issues"
        d["source_points"] = 0
    print("[issues] AI 抽取 %d 条蓝海需求" % len(demands))
    return demands


if __name__ == "__main__":
    import pprint
    pprint.pprint(mine(max_topics=3)[:3])