"""仓库分析：读取 README，评估 APP 适配度，给出评分与理由。"""
import urllib.request
import json
from datetime import datetime, timezone

import config
import app_store_checker


def _headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "AndroidAppFinder/1.0"}
    if config.GITHUB_TOKEN:
        h["Authorization"] = "Bearer " + config.GITHUB_TOKEN
    return h


def _readme(repo):
    url = "https://api.github.com/repos/%s/readme" % repo["name"]
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        import base64
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")[:8000]
    except Exception:
        return ""


def _score(repo, readme):
    reasons = []
    score = 0
    low = (repo["desc"] + " " + readme).lower()

    # star 适中加分：太大说明已成熟，太小说明没人验证
    stars = repo["stars"]
    if 100 <= stars <= 5000:
        score += config.W_STARS
        reasons.append("star 适中(%d)，有验证但未被巨头覆盖" % stars)

    # 语言
    if repo["language"] in config.APP_FRIENDLY_LANGUAGES:
        score += config.W_LANGUAGE
        reasons.append("主语言 %s 适合移动端/客户端开发" % repo["language"])

    # topics
    hit_topics = [t for t in repo["topics"] if t.lower() in config.APP_FRIENDLY_TOPICS]
    if hit_topics:
        score += config.W_TOPICS
        reasons.append("topics 命中 APP 友好领域: %s" % ", ".join(hit_topics))

    # README 命中 APP 词
    app_hits = [k for k in config.APP_KEYWORDS if k in low]
    if app_hits:
        score += config.W_APP_README
        reasons.append("README 出现移动/用户向关键词: %s" % ", ".join(app_hits[:5]))

    # 非 APP 特征扣分
    non_hits = [k for k in config.NON_APP_KEYWORDS if k in low]
    if non_hits:
        score += config.W_NON_APP_PENALTY
        reasons.append("命中基础设施特征(扣分): %s" % ", ".join(non_hits))

    # 近期活跃
    try:
        pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - pushed).days
        if days <= 30:
            score += config.W_FRESHNESS
            reasons.append("近 %d 天有更新，活跃维护" % days)
    except Exception:
        pass

    # 单一明确用途：描述短而聚焦
    desc_len = len(repo["desc"])
    if 10 <= desc_len <= 120:
        score += config.W_SINGLE_PURPOSE
        reasons.append("描述聚焦明确，单一用途")

    return score, reasons


def _pain_points(repo, readme):
    """从描述和 README 抽取痛点与解决的问题（启发式）。"""
    text = repo["desc"] + " " + readme
    sentences = [s.strip() for s in text.replace("\n", ".").split(".") if len(s.strip()) > 15]
    # 优先取含问题/解决/帮助/提供等词的句子
    cues = ["solve", "help", "provide", "allow", "enable", "generate", "automate", "convert", "track", "manage"]
    picked = [s for s in sentences if any(c in s.lower() for c in cues)][:2]
    if not picked:
        picked = sentences[:2]
    return picked


def analyze(repos):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:
        readmes = list(ex.map(_readme, repos))
    out = []
    for repo, readme in zip(repos, readmes):
        score, reasons = _score(repo, readme)
        repo["score"] = score
        repo["reasons"] = reasons
        repo["pain_points"] = _pain_points(repo, readme)
        repo["readme_excerpt"] = readme[:500]
        out.append(repo)
    out.sort(key=lambda r: r["score"], reverse=True)

    # 应用商店查重（并发，仅对进入报告的候选）
    candidates = [r for r in out if r["score"] >= config.MIN_REPORT_SCORE]
    if candidates:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as ex:
            store_results = list(ex.map(app_store_checker.check, candidates))
        for r, sr in zip(candidates, store_results):
            r["store_check"] = sr
        print("[analyzer] 商店查重完成，覆盖 %d 个候选" % len(candidates))

    print("[analyzer] 分析完成，最高分 %d" % (out[0]["score"] if out else 0))
    return out


if __name__ == "__main__":
    sample = [{"name": "owner/repo", "url": "", "desc": "A tool to track habits", "stars": 200,
               "language": "Kotlin", "topics": ["habit", "productivity"],
               "created_at": "", "pushed_at": "2026-06-01T00:00:00Z", "homepage": "", "owner": "x"}]
    print(analyze(sample))
