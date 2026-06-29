# -*- coding: utf-8 -*-
"""蓝海来源四：应用商店差评挖掘。

核心思想：用户已经下载并使用某类 APP，却打差评 = 痛点最真实、最可落地。
从热门 APP 的 1-2 星差评里，AI 抽取「想要但没满足的功能」，
这类用户已证明会付费/会下载，只是现有 APP 没满足他，是离「真实蓝海」最近的信号。

数据源：google-play-scraper 的 reviews()（免费无 key，已验证可用）。
"""
import urllib.request
import urllib.parse
import json
import time

import config

# 要挖掘差评的「热门 APP 包名 + 所属品类」。
# 选品原则：选各品类头部 APP（下载量大、评论多），差评里藏的未满足需求最有代表性。
# 品类刻意覆盖非红海方向（避开记账/计算器/天气），偏向有细分空间的生活/效率/创作类。
REVIEW_APPS = [
    # (包名, 品类标签, 中文品类)
    ("com.ticktick.task", "todo", "待办效率"),
    ("com.netease.mail", "email", "邮箱"),
    ("com.sdu.didi.psnger", "travel", "出行打车"),
    ("com.taobao.taobao", "shopping", "购物"),
    ("com.eg.android.AlipayGphone", "finance", "支付生活"),
    ("cn.wps.moffice_eng", "office", "办公文档"),
    ("com.miui.calculator", "calculator", "计算器"),
    ("com.iflytek.inputmethod", "input", "输入法"),
    ("com.tencent.wework", "work", "企业协作"),
    ("com.smile.gifmaker", "video", "短视频创作"),
]


def _fetch_bad_reviews(app_id, label, n=30):
    """抓某 APP 的最新差评（1-2 星）。返回 [{score, content, app, label}]。"""
    try:
        from google_play_scraper import reviews, Sort
    except ImportError:
        print("[review] 未安装 google-play-scraper，跳过")
        return []
    out = []
    try:
        r, _ = reviews(app_id, lang="zh", country="cn", count=n * 4, sort=Sort.NEWEST)
    except Exception as e:
        print("[review] 抓取 %s 失败: %s" % (app_id, e))
        return []
    for x in r:
        score = x.get("score") or 0
        if score > 2:
            continue
        content = (x.get("content") or "").strip()
        if len(content) < 6:
            continue
        out.append({"score": score, "content": content, "app": app_id, "label": label})
        if len(out) >= n:
            break
    print("[review] %s(%s) 抓到 %d 条差评" % (app_id, label, len(out)))
    return out


def _ai_extract_demands(all_reviews):
    """AI 从差评里抽取结构化蓝海需求。

    输入：跨 APP 的差评集合。AI 聚类同类抱怨，提炼出「用户想要但现有 APP 没满足」的功能点。
    输出：[{need, audience, pain, why_gap, search_queries(英文), store_query(中文)}]
    """
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return []
    if not all_reviews:
        return []
    # 每条差评带品类标签喂给 AI，帮它区分场景
    lines = []
    for i, rv in enumerate(all_reviews, 1):
        lines.append("%d. [%s/%d星] %s" % (i, rv["label"], rv["score"], rv["content"][:120]))
    blob = "\n".join(lines)
    prompt = (
        "你是一名资深产品经理，专长从用户差评里发现蓝海 APP 机会。\n"
        "下面是多个热门 APP 的真实差评（含品类标签和星级）。这些都是用户已经下载使用、却表达不满的反馈。\n\n"
        "%s\n\n"
        "请从中挖掘「用户反复想要、但现有 APP 都没做好/没满足」的功能点，形成可做成独立 APP 的蓝海机会。\n"
        "挖掘原则：\n"
        "1. 聚类同类抱怨：多条差评指向同一个未满足需求才提取，单条吐槽不提取\n"
        "2. 必须是「功能缺口」而非「bug/卡顿/广告」类抱怨（如「经常不提醒」不是机会，「想要按地点触发提醒」才是）\n"
        "3. 排除红海：记账/计算器/天气/笔记/清理/输入法/壁纸/播放器/翻译/背单词\n"
        "4. 宁缺毋滥，最多 4 个最有蓝海潜力的需求\n"
        "5. search_queries 给 2-3 个英文搜索词（用于商店查重），store_query 给 6-12 字中文场景词\n\n"
        "输出 JSON: {\"demands\":[{\"need\":\"具体需求(含场景)\",\"audience\":\"人群\","
        "\"pain\":\"痛点(用户差评里反复出现的抱怨)\","
        "\"why_gap\":\"为何现有APP没解决\",\"search_queries\":[\"英文词\"],\"store_query\":\"中文查重词\"}]}\n"
        "只输出 JSON，不要 markdown。"
    ) % blob
    body = json.dumps({
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": "你是产品经理，从差评里挖蓝海机会，只输出合法JSON。"},
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
        print("[review] AI 抽取失败: %s" % e)
    return []


def mine(max_apps=6):
    """主入口：抓若干热门 APP 差评 -> AI 抽取蓝海需求。

    返回 [{need, audience, pain, why_gap, search_queries, store_query, source_*}]。
    """
    from concurrent.futures import ThreadPoolExecutor

    apps = REVIEW_APPS[:max_apps]
    all_reviews = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for rvs in ex.map(lambda a: _fetch_bad_reviews(a[0], a[2], 25), apps):
            all_reviews.extend(rvs)
    print("[review] 共抓到差评 %d 条，交 AI 抽取 ..." % len(all_reviews))
    if not all_reviews:
        return []
    demands = _ai_extract_demands(all_reviews)
    for d in demands:
        d["source_post"] = "应用商店差评挖掘"
        d["source_url"] = "Google Play 评论"
        d["source_points"] = 0
    print("[review] AI 抽取 %d 条蓝海需求" % len(demands))
    return demands


if __name__ == "__main__":
    import pprint
    pprint.pprint(mine(max_apps=3)[:3])