# -*- coding: utf-8 -*-
"""蓝海需求假设器：AI 提蓝海假设 + 百度联想词验证需求 + 商店查重验证供给。

核心思想：蓝海 = 需求真实(有人在找) + 供给不足(商店同类少)。
不从「高频热词」(=红海)出发，而从「小众人群的日常痛点」出发——
这些人群巨头不做(市场小)、但痛点具体、会付费。

流程：
1. 内置小众人群种子库(色弱/左撇子/多肉养护/手账/夜班/快递员...)
2. AI 对每个群体推理「反复遇到但找不到好工具的痛点」，输出结构化假设
3. 百度联想词验证需求真实性：联想词里是否有相关搜索 = 真有人在找
4. 商店查重验证供给不足：同类 <= 阈值 = 蓝海
5. 两项都满足才入选

完全不依赖 GitHub 仓库，也不依赖被封的社区(知乎/贴吧/百度知道都 403)。
"""
import urllib.request
import urllib.parse
import json
import time

import config


# 小众人群种子库：巨头不做、人群明确、有具体日常痛点的群体
# 每个含：人群名 + 该人群常搜/常遇的场景线索(供 AI 推理用)
NICHE_AUDIENCES = [
    {"audience": "色弱/色盲人群", "hints": "辨别交通灯、地铁线路图颜色、衣服配色、电线颜色、蔬菜成熟度"},
    {"audience": "左撇子", "hints": "剪刀、鼠标、吉他、相机、门把手、厨房工具都是右手设计"},
    {"audience": "多肉/绿植养护者", "hints": "不知品种、不知何时浇水、病虫害识别、配土比例"},
    {"audience": "手账/bullet journal爱好者", "hints": "排版灵感、习惯追踪、月度复盘模板、贴纸管理"},
    {"audience": "夜班/倒班工作者", "hints": "排班提醒、睡眠节律调整、夜班餐饮、生物钟管理"},
    {"audience": "快递员/外卖骑手", "hints": "路线规划、多平台接单、天气应对、电动车续航、收入记账"},
    {"audience": "考研/考公党", "hints": "复习进度管理、专注力、错题归因、倒计时、考点背诵"},
    {"audience": "租房族", "hints": "房租水电分摊、维修报备、室友公约、退房清单、搬家打包"},
    {"audience": "钓鱼爱好者", "hints": "天气气压鱼情、钓点记录、渔获记录、饵料配方、鱼种识别"},
    {"audience": "爬宠/异宠饲养者", "hints": "温湿度监控、喂食周期、蜕皮记录、品种百科、就医"},
    {"audience": "字帖/书法练习者", "hints": "字帖临摹、运笔轨迹、每日练习打卡、字形结构分析"},
    {"audience": "慢性病患者/长期服药者", "hints": "服药提醒、药物相互作用、复诊记录、指标趋势、医保"},
    {"audience": "宝妈/新手父母", "hints": "喂奶时间、睡眠规律、疫苗时间表、辅食食谱、成长记录"},
    {"audience": "freelancer/自由职业者", "hints": "多项目时间管理、发票合同、收入波动、社保自理、报价"},
    {"audience": "听力障碍者", "hints": "门铃/警报声觉、会议转文字、视频字幕、紧急求助"},
    {"audience": "古钱币/邮票收藏者", "hints": "品种鉴定、行情查询、保存方法、交换交易、版别识别"},
    {"audience": "露营/户外爱好者", "hints": "营地推荐、装备清单、天气地形、离线地图、装备收纳"},
    {"audience": "手游玩家(特定小众游戏)", "hints": "抽卡记录、伤害计算、配装模拟、活动日历、素材farming"},
    {"audience": "方言/少数民族语言学习者", "hints": "方言词汇查询、发音对比、日常用语、文化背景"},
    {"audience": "过敏体质者", "hints": "食物成分排查、过敏原识别、症状记录、就医指引、餐厅筛选"},
    # === 新增 15 个小众群体（巨头不做、人群明确、有具体日常痛点）===
    {"audience": "视障/低视力人群", "hints": "识别钞票面额、药品说明书、菜单、商品标签、寻找掉落物"},
    {"audience": "轮椅使用者/行动不便者", "hints": "无障碍路线、坡道电梯位置、无障碍厕所、商家可进性"},
    {"audience": "自闭症/阿斯伯格谱系", "hints": "社交脚本、情绪识别、感官过载预警、日常流程可视化"},
    {"audience": "ADHD/注意力缺陷者", "hints": "任务拆解、时间盲区、拖延启动、多任务切换、服药节律"},
    {"audience": "老年智能手机用户", "hints": "字体放大、防诈骗、简化操作、亲情协助、紧急呼叫"},
    {"audience": "代驾/网约车司机", "hints": "停车场记忆、车辆识别、夜间安全、收入多平台、疲劳管理"},
    {"audience": "小店主/个体工商户", "hints": "库存盘点、多渠道对账、进货比价、会员管理、税务申报"},
    {"audience": "民宿/短租房东", "hints": "多平台日历同步、清洁排期、入住指引、物品损耗、定价"},
    {"audience": "宠物主(猫狗以外)", "hints": "兔子/仓鼠/鸟类/水族/爬宠的品种、喂养、健康、用品"},
    {"audience": "汉服/lo裙/jk制服爱好者", "hints": "尺码换算、穿搭灵感、二手交易、活动日历、穿搭天气"},
    {"audience": "桌游/TRPG玩家", "hints": "规则查询、组队匹配、跑团记录、骰子、角色卡管理"},
    {"audience": "摄影后期爱好者", "hints": "RAW管理、批量调色预设、元数据、硬盘整理、作品归档"},
    {"audience": "健身/增肌减脂者", "hints": "训练记录、蛋白质摄入、动作库、器械使用、围度追踪"},
    {"audience": "跨境购物/海淘者", "hints": "关税计算、物流追踪、尺码换算、真假鉴别、转运"},
    {"audience": "麻将/棋牌爱好者", "hints": "牌谱记录、规则查询、段位统计、约牌、复盘分析"},
]

def _get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Chrome/124"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def baidu_suggest(word):
    """百度搜索联想词。返回 [sug, ...]。"""
    url = config.BAIDU_SUGGEST_URL.format(kw=urllib.parse.quote(word))
    try:
        data = _get(url)
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
            return data[1]
    except Exception as e:
        print("[hypo] 百度联想 '%s' 失败: %s" % (word, e))
    return []


def _ai_hypothesize(audience, hints):
    """AI 对一个小众人群推理未满足痛点，输出结构化需求假设。

    返回 [{need, audience, pain, search_verify_word(百度验证词), why_no_tool}, ...]
    """
    if not (config.ENABLE_AI_ANALYSIS and config.AI_API_KEY):
        return []
    prompt = (
        "你是一名资深产品经理，专长发现蓝海 APP 机会。\n"
        "目标人群：%s\n"
        "该人群的日常场景线索：%s\n\n"
        "请推理这个人群「反复遇到、但找不到好工具解决」的具体痛点。\n"
        "要求：\n"
        "1. 必须是具体场景(如「色弱人群难以辨别地铁线路图颜色」而非「色弱看不清」)\n"
        "2. 现有 APP 没解决或解决得差(巨头不做因为人群小)\n"
        "3. 给两个搜索词：\n"
        "   - search_verify_word: 4-8字中文，宽泛些，用于百度联想词验证是否真有人在搜\n"
        "   - store_query: 6-12字中文，要具体到场景+人群，用于应用商店查重(越具体越能查到真实供给)\n"
        "     例: 不要给「项目排期」(会查到一堆项目管理软件)，给「自由职业者多项目排期提醒」\n"
        "4. 排除红海：记账/计算器/天气/笔记/清理/输入法/壁纸/播放器/翻译/背单词/项目管理/办公\n"
        "5. 宁缺毋滥，最多 3 个最有蓝海潜力的痛点\n\n"
        "输出 JSON: {\"demands\": [{\"need\":\"具体需求(含场景)\",\"audience\":\"人群\","
        "\"pain\":\"痛点描述\",\"search_verify_word\":\"百度验证词(宽)\","
        "\"store_query\":\"商店查重词(窄,含场景)\","
        "\"why_no_tool\":\"为何现有工具没解决\"}]}\n"
        "只输出 JSON，不要 markdown 代码块。"
    ) % (audience, hints)
    body = json.dumps({
        "model": config.AI_MODEL,
        "messages": [
            {"role": "system", "content": "你是产品经理，只输出合法 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    url = config.AI_API_BASE.rstrip("/") + "/chat/completions"
    try:
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + config.AI_API_KEY,
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
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
        print("[hypo] AI 假设失败 (%s): %s" % (audience, e))
    return []


def verify_demand(verify_word):
    """用百度联想词验证需求真实性：联想词里有相关搜索 = 真有人在找。

    返回 (is_real, related_count, samples)。
    """
    sugs = baidu_suggest(verify_word)
    if not sugs:
        return False, 0, []
    # 联想词数量 >= 5 且含「怎么/如何/工具/软件/方法」类 = 真痛点
    real_cues = ["怎么", "如何", "工具", "软件", "方法", "怎么办", "有没有", "app", "应用"]
    related = [s for s in sugs if any(c in s.lower() for c in real_cues)]
    is_real = len(sugs) >= 5 and len(related) >= 2
    return is_real, len(related), sugs[:8]


def mine(max_audiences=8):
    """主入口：对小众人群推理痛点 + 双重验证。

    返回 [{need, audience, pain, why_no_tool, search_verify_word,
           demand_verified(真有人在搜), related_searches, store_check(由 main 填)}, ...]
    """
    import random
    audiences = list(NICHE_AUDIENCES)
    random.shuffle(audiences)
    audiences = audiences[:max_audiences]

    all_hypotheses = []
    for a in audiences:
        hyps = _ai_hypothesize(a["audience"], a["hints"])
        for h in hyps:
            h["audience"] = a["audience"]
            all_hypotheses.append(h)
        print("[hypo] %s -> %d 个假设" % (a["audience"], len(hyps)))
        time.sleep(0.5)

    print("[hypo] 共 %d 个假设，开始需求验证 ..." % len(all_hypotheses))

    # 需求验证：百度联想词
    verified = []
    for h in all_hypotheses:
        vw = h.get("search_verify_word", "")
        if not vw:
            continue
        is_real, related_n, samples = verify_demand(vw)
        h["demand_verified"] = is_real
        h["related_searches"] = samples
        h["related_count"] = related_n
        if is_real:
            verified.append(h)
            print("[hypo] 需求验证通过: %s (相关搜索 %d)" % (vw, related_n))
        else:
            print("[hypo] 需求验证未通过: %s" % vw)

    print("[hypo] 需求验证通过 %d / %d" % (len(verified), len(all_hypotheses)))
    # 供给验证(商店查重)由 main 调用 app_store_checker 完成，这里只返回需求验证通过的
    return verified


if __name__ == "__main__":
    import pprint
    pprint.pprint(mine(max_audiences=2)[:3])
