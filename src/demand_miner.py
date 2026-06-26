# -*- coding: utf-8 -*-
"""需求挖掘：从领域种子词出发，用百度搜索联想词扩展出用户真实在搜的长尾需求。

百度联想词反映用户持续搜索的「解决方案型」需求（如「手机充不进电怎么办」），
区别于热搜的突发事件。这是 APP 机会挖掘的核心需求信号。
"""
import urllib.request
import urllib.parse
import json
import re
import random

import config

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def baidu_suggest(seed):
    """返回单个种子词的百度联想词列表。"""
    url = config.BAIDU_SUGGEST_URL.format(kw=urllib.parse.quote(seed))
    try:
        text = _get(url)
        data = json.loads(text)
        # 格式: ["seed", ["sug1", "sug2", ...]]
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
            return data[1]
    except Exception as e:
        print("[demand] 百度联想 '%s' 失败: %s" % (seed, e))
    return []


def _is_solution_query(w):
    """判断是否「找解决方案」型需求（而非泛词/导航词/事件）。

    特征：含疑问词/动作词/怎么/如何/为什么/工具/软件/方法/下载等。
    同时排除红海品类（记账/计算器等已饱和市场）。
    """
    w = str(w)
    if not (config.DEMAND_MIN_LEN <= len(w) <= config.DEMAND_MAX_LEN):
        return False
    low = w.lower()
    # 红海品类排除
    for kw in config.RED_OCEAN_KEYWORDS:
        if kw in low:
            return False
    # 疑问/求助/工具型关键词
    solution_cues = [
        "怎么", "如何", "为什么", "怎么办", "原理", "方法", "技巧",
        "软件", "工具", "app", "应用", "下载", "转换", "提取", "去除",
        "修复", "解决", "查询", "计算", "识别", "生成", "制作", "导出",
        "压缩", "合并", "分割", "恢复", "备份", "清理", "加速",
    ]
    low = w.lower()
    return any(c in low for c in solution_cues)


def mine():
    """从领域种子词挖掘长尾需求。返回 [(需求词, 来源种子词)]。"""
    seeds = list(config.DEMAND_SEED_DOMAINS)
    random.shuffle(seeds)
    seeds = seeds[:config.MAX_DEMAND_SEEDS]

    seen = set()
    demands = []
    for seed in seeds:
        sugs = baidu_suggest(seed)
        for w in sugs:
            w = re.sub(r"\s+", " ", w).strip()
            wl = w.lower()
            if wl in seen or not _is_solution_query(w):
                continue
            seen.add(wl)
            demands.append((w, seed))
        if len(demands) >= 30:
            break
    print("[demand] 从 %d 个种子词挖出 %d 条长尾需求" % (len(seeds), len(demands)))
    return demands


if __name__ == "__main__":
    import pprint
    pprint.pprint(mine()[:10])
