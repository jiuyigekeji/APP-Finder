"""可选 AI 分析：接入 OpenAI 兼容接口（如 Gemini 免费 API）做深度解读。"""
import json
import urllib.request

import config


def deep_analyze(repo):
    """返回 dict: problem / pain_point / app_idea / why_app。失败返回 None。"""
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return None
    prompt = (
        "你是一名产品经理。分析以下 GitHub 仓库，输出 JSON:\n"
        "problem: 解决了什么问题\n"
        "pain_point: 用户痛点是什么\n"
        "app_idea: 适合做成什么 APP/小程序\n"
        "why_app: 为什么适合做成 APP\n\n"
        "仓库: %s\n描述: %s\nREADME 摘要: %s"
    ) % (repo["name"], repo["desc"], repo.get("readme_excerpt", "")[:1500])

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode("utf-8")
    url = "%s/models/%s:generateContent?key=%s" % (config.AI_API_BASE, config.AI_MODEL, config.AI_API_KEY)
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception as e:
        print("[ai] 分析失败: %s" % e)
        return None
