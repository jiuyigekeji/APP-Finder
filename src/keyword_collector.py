"""关键词采集：百度热搜 + Google Trends RSS，失败回退种子词。"""
import urllib.request
import json
import re
import xml.etree.ElementTree as ET

import config


def _get(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0 (AndroidAppFinder/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def from_baidu():
    try:
        text = _get(config.BAIDU_HOT_URL)
        data = json.loads(text)
        items = data.get("data", {}).get("cards", [{}])[0].get("content", [])
        return [it.get("word") or it.get("query") for it in items if it.get("word") or it.get("query")]
    except Exception:
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
    except Exception:
        return []


def clean_keywords(words):
    seen = set()
    out = []
    for w in words:
        w = re.sub(r"\s+", " ", str(w)).strip()
        if not w or len(w) > 30 or w.lower() in seen:
            continue
        seen.add(w.lower())
        out.append(w)
        if len(out) >= config.MAX_KEYWORDS:
            break
    return out


def collect():
    print("[keywords] 采集百度热搜 + Google Trends ...")
    words = from_baidu() + from_google_trends()
    words = clean_keywords(words)
    if len(words) < 5:
        print("[keywords] 在线来源不足，补充种子词")
        words = clean_keywords(words + config.SEED_KEYWORDS)
    print("[keywords] 共 %d 个" % len(words))
    return words


if __name__ == "__main__":
    print(collect())
