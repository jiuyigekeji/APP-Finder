# -*- coding: utf-8 -*-
"""AI 深度分析：拉取仓库核心源码，让 AI 分析整套代码，确认解决的痛点。

默认走 Gemini 免费 API（OpenAI 兼容）。未配置 AI 时返回 None，由调用方回退启发式。
"""
import json
import urllib.request

import config


def _headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "AppFinder/1.0"}
    if config.GITHUB_TOKEN:
        h["Authorization"] = "Bearer " + config.GITHUB_TOKEN
    return h


def _list_tree(repo):
    """获取仓库文件树，返回 [(path, size)]。"""
    owner_repo = repo["name"]
    # 取默认分支的树
    url = "https://api.github.com/repos/%s/git/trees/HEAD?recursive=1" % owner_repo
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        return [(t["path"], t.get("size", 0)) for t in data.get("tree", []) if t["type"] == "blob"]
    except Exception as e:
        print("[ai] 获取文件树失败: %s" % e)
        return []


def _pick_source_files(tree):
    """从文件树挑选核心源码文件：优先 README + 主要语言源文件。"""
    code_exts = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".kt", ".swift", ".dart",
        ".java", ".go", ".rs", ".cs", ".cpp", ".c", ".h", ".rb", ".php",
        ".vue", ".svelte",
    }
    # 排除测试/文档构建/依赖目录
    skip_dirs = ("test", "tests", "docs", "node_modules", "vendor", "dist",
                 "build", ".github", "example", "examples", "bench")
    readme = None
    sources = []
    for path, size in tree:
        low = path.lower()
        if any(d in low for d in skip_dirs):
            continue
        if readme is None and low.startswith("readme"):
            readme = path
            continue
        if any(low.endswith(ext) for ext in code_exts):
            # 偏好根目录或一级目录下的核心文件
            depth = path.count("/")
            if depth <= 2:
                sources.append((path, size))
    sources.sort(key=lambda x: (x[0].count("/"), -x[1]))  # 浅目录优先，大文件优先
    picked = sources[:config.AI_REPO_FILES_MAX]
    if readme:
        picked = [readme] + picked
    return picked


def _fetch_file(repo, path):
    """获取单文件内容（base64）。"""
    url = "https://api.github.com/repos/%s/contents/%s" % (repo["name"], urllib.parse.quote(path))
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        import base64
        content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
        return content[:config.AI_REPO_FILE_MAX_CHARS]
    except Exception:
        return ""


import urllib.parse  # noqa: E402


def _gather_code(repo):
    """返回拼接好的代码上下文字符串。"""
    tree = _list_tree(repo)
    if not tree:
        return repo.get("readme_excerpt", "")
    picked = _pick_source_files(tree)
    parts = []
    for path in picked:
        content = _fetch_file(repo, path)
        if content:
            parts.append("### 文件: %s\n```\n%s\n```" % (path, content))
    return "\n\n".join(parts)[:12000]


def _call_ai(prompt):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode("utf-8")
    url = "%s/models/%s:generateContent?key=%s" % (config.AI_API_BASE, config.AI_MODEL, config.AI_API_KEY)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def deep_analyze(repo):
    """分析整套代码，返回 dict: problem / pain_point / app_idea / why_app / key_logic。"""
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return None
    code = _gather_code(repo)
    prompt = (
        "你是一名资深产品经理兼工程师。请分析以下 GitHub 仓库的源代码，理解它实现了什么逻辑，"
        "然后输出 JSON：\n"
        "key_logic: 核心代码逻辑是什么（实现原理概要）\n"
        "problem: 解决了什么问题\n"
        "pain_point: 用户的痛点是什么\n"
        "app_idea: 适合做成什么 APP/小程序\n"
        "why_app: 为什么适合做成 APP\n\n"
        "仓库: %s\n描述: %s\n\n源代码：\n%s"
    ) % (repo["name"], repo["desc"], code)
    try:
        return _call_ai(prompt)
    except Exception as e:
        print("[ai] 代码分析失败: %s" % e)
        return None
