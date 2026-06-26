# -*- coding: utf-8 -*-
"""关键词采集：百度热搜 + Google Trends RSS，失败回退种子词。

collect() 返回 {"baidu": [...], "google": [...]}，保留来源标签。
"""
import urllib.request
import json
import re
import time
import xml.etree.ElementTree as ET

import config

UA_MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1")


def _get(url, headers=None, timeout=10, retries=2):
    """带重试的 GET，应对百度 SSL 偶发断连。"""
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": UA_MOBILE})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            last_err = e
            time.sleep(1)
    raise last_err


def from_baidu():
    try:
        text = _get(config.BAIDU_HOT_URL)
        data = json.loads(text)
        cards = data.get("data", {}).get("cards", [])
        words = []
        for card in cards:
            content = card.get("content", [])
            for it in content:
                w = it.get("word") or it.get("query")
                if w:
                    words.append(w)
                for sub in it.get("content", []) if isinstance(it.get("content"), list) else []:
                    sw = sub.get("word") or sub.get("query") or sub.get("name")
                    if sw:
                        words.append(sw)
        return words
    except Exception as e:
        print("[keywords] 百度热搜失败: %s" % e)
        return []


def from_google_trends():
    try:
        text = _get(config.GOOGLE_TRENDS_RSS)
        root = ET.fromstring(text)
        items = root.findall(".//{*}item")
        out = []
        for it in items:
            title = it.findtext("{*}title")
            if title:
                out.append(title.strip())
        return out
    except Exception as e:
        print("[keywords] Google Trends 失败: %s" % e)
        return []


def clean_keywords(words, limit=None):
    """去重、去噪、限长。limit 为 None 时不限。"""
    limit = limit if limit is not None else config.MAX_KEYWORDS
    seen = set()
    out = []
    for w in words:
        w = re.sub(r"\s+", " ", str(w)).strip()
        if not w or len(w) > 30 or w.lower() in seen:
            continue
        seen.add(w.lower())
        out.append(w)
        if len(out) >= limit:
            break
    return out


def collect():
    """返回 {"baidu": [...], "google": [...]}，各来源独立清洗与限流。"""
    print("[keywords] 采集百度热搜 + Google Trends ...")
    baidu = clean_keywords(from_baidu())
    google = clean_keywords(from_google_trends())

    # 两者都失败时回退种子词（归入 baidu 桶）
    if not baidu and not google:
        print("[keywords] 在线来源均失败，补充种子词")
        baidu = clean_keywords(config.SEED_KEYWORDS)

    print("[keywords] 百度 %d 个，谷歌 %d 个" % (len(baidu), len(google)))
    return {"baidu": baidu, "google": google}


def _should_skip(kw):
    """命中预筛黑名单的词跳过 GitHub 搜索（人名/赛事/娱乐，无对应仓库）。"""
    for pat in config.KEYWORD_SKIP_PATTERNS:
        if re.search(pat, kw, re.IGNORECASE):
            return True
    return False


def all_keywords(grouped):
    """合并所有来源关键词（去重 + 预筛），用于 GitHub 搜索。
    有效词不足时补充科技种子词，保证候选数量。"""
    seen = set()
    out = []
    for src in ("baidu", "google"):
        for w in grouped.get(src, []):
            wl = w.lower()
            if wl in seen or _should_skip(w):
                continue
            seen.add(wl)
            out.append(w)
    # 始终补充科技种子词（去重），保证有出仓库的搜索词，候选数量稳定
    for w in config.TECH_SEED_KEYWORDS:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            out.append(w)
    return out


if __name__ == "__main__":
    import pprint
    pprint.pprint(collect())
