# -*- coding: utf-8 -*-
"""关键词翻译：英文关键词翻译为中文。

优先级：
1. AI API（若启用 ENABLE_AI_ANALYSIS 且有 AI_API_KEY）
2. LibreTranslate 公共实例（免费无 key）
3. 原文不翻译（保证不中断）
"""
import json
import urllib.request
import urllib.parse
import re

import config

UA = "Mozilla/5.0 (AppFinder/1.0)"


def _is_mostly_chinese(text):
    s = re.sub(r"\s+", "", str(text))
    if not s:
        return True
    cn = sum(1 for c in s if "\u4e00" <= c <= "\u9fa5")
    return cn / len(s) > 0.3


def _by_google(text):
    """Google 翻译非官方端点（免费无 key，稳定）。返回中文译文或 None。"""
    url = config.GOOGLE_TRANSLATE_URL + "?client=gtx&sl=auto&tl=zh&dt=t&q=" + urllib.parse.quote(text)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        # data[0] 是翻译片段列表，每项 [translated, original, ...]
        return "".join(seg[0] for seg in data[0] if seg and seg[0])
    except Exception as e:
        print("[translate] google 失败: %s" % e)
        return None


def _by_ai(text):
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return None
    prompt = "把下面这个词组翻译成简洁的中文短语，只输出译文，不要解释：\n%s" % text
    body = json.dumps({
        "model": config.AI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode("utf-8")
    url = config.AI_API_BASE.rstrip("/") + "/chat/completions"
    try:
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + config.AI_API_KEY,
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _by_libretranslate(text):
    body = json.dumps({
        "q": text, "source": "auto", "target": "zh", "format": "text",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            config.LIBRETRANSLATE_URL, data=body,
            headers={"Content-Type": "application/json", "User-Agent": UA},
        )
        with urllib.request.urlopen(req, timeout=config.LIBRETRANSLATE_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        return (data.get("translatedText") or "").strip()
    except Exception:
        return None


def translate(text):
    """返回翻译后的中文。已是中文则原样返回。失败回退原文。"""
    text = str(text).strip()
    if not text or _is_mostly_chinese(text):
        return text
    for fn in (_by_google, _by_ai, _by_libretranslate):
        t = fn(text)
        if t and t.lower() != text.lower():
            return t
    return text


def translate_keywords(keywords):
    """返回 [(原词, 中文翻译)] 列表。"""
    out = []
    for kw in keywords:
        zh = translate(kw)
        out.append((kw, zh))
    return out


if __name__ == "__main__":
    print(translate_keywords(["habit tracker", "LLM", "记账", "pomodoro"]))
