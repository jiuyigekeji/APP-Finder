# -*- coding: utf-8 -*-
"""国内应用商店搜索：华为 / 小米 / vivo。

实现移植自 C:\\Users\\lpylinan\\Documents\\SEO\\aso-toolkit 项目的逆向成果：
- 华为：web-drcn.hispace.dbankcloud.com，先取 interfaceCode(JWT) 再调 /uowap/index。
- vivo：main.appstore.vivo.com.cn/port/packages，POST 表单，无需认证。
- 小米：app.market.xiaomi.com/apm/search，HMAC 签名（SALT="good luck!"，自定义 base64，字段重排）。
- OPPO：暂不搜索。

全部用 urllib 实现，无需第三方依赖。失败返回 (0, [])，不中断主流程。
"""
import urllib.request
import urllib.parse
import json
import hmac
import hashlib
import base64
import time
import random
import re

UA_MOBILE = "Mozilla/5.0 (Linux; Android 12; Build/SP1A.210812.003) AppleWebKit/537.36 Mobile Safari/537.36"
UA_DALVIK = "Dalvik/2.1.0 (Linux; U; Android 12; V2203A Build/SP1A.210812.003)"


def _get(url, headers=None, timeout=12):
    import gzip
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA_MOBILE, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return raw


def _post(url, body, headers=None, timeout=12):
    req = urllib.request.Request(url, data=body, headers=headers or {
        "User-Agent": UA_DALVIK, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ===================== 华为 =====================
_HUAWEI_BASE = "https://web-drcn.hispace.dbankcloud.com"
_ic_cache = {"code": None, "ts": 0}


def _huawei_interface_code():
    now = time.time()
    if _ic_cache["code"] and now - _ic_cache["ts"] < 600:
        return _ic_cache["code"]
    url = _HUAWEI_BASE + "/webedge/getInterfaceCode"
    try:
        data = _get(url, headers={"User-Agent": UA_MOBILE, "Accept": "application/json",
                                  "Referer": "https://appgallery.huawei.com/"})
        code = data.decode("utf-8", errors="ignore").strip().strip('"')
        _ic_cache["code"] = code
        _ic_cache["ts"] = now
        return code
    except Exception as e:
        print("[store] huawei 取 interfaceCode 失败: %s" % e)
        return None


def huawei_search(keyword, max_results=10):
    ic = _huawei_interface_code()
    if not ic:
        return 0, []
    uri = urllib.parse.quote("searchApp|%s" % keyword)
    path = ("/uowap/index?method=internal.getTabDetail&serviceType=20&reqPageNum=1"
            "&uri=%s&maxResults=%d&zone=&locale=zh_Hans_CN" % (uri, max_results))
    url = _HUAWEI_BASE + path
    ts = int(time.time() * 1000)
    headers = {
        "User-Agent": UA_MOBILE, "Accept": "application/json",
        "Referer": "https://appgallery.huawei.com/",
        "interfaceCode": ic, "Interface-Code": "%s_%s" % (ic, ts),
        "Content-Type": "application/json",
    }
    try:
        data = json.loads(_get(url, headers=headers).decode("utf-8", errors="ignore"))
    except Exception as e:
        print("[store] huawei 搜索失败: %s" % e)
        return 0, []
    if data.get("rtnCode") != 0:
        return 0, []
    items = []
    for layout in data.get("layoutData", []):
        for it in layout.get("dataList", []):
            if it.get("appid") and it.get("name"):
                items.append({
                    "name": it.get("name"),
                    "developer": it.get("developer"),
                    "genre": it.get("level1Category") or it.get("categoryName"),
                    "installs": it.get("downloadCountStr"),
                    "score": it.get("score"),
                })
    items = items[:max_results]
    return len(items), items


# ===================== vivo =====================
_VIVO_BASE = "https://main.appstore.vivo.com.cn"
_VIVO_DEVICE = {
    "deviceType": "phone", "ui_mode": "1", "model": "V2203A",
    "screensize": "1080_2400", "mfr": "vivo", "androidVer": "31",
    "androidName": "12", "build_number": "SP1A.210812.003",
    "density": "3.0", "nt": "WIFI", "patch_sup": "2",
}


def vivo_search(keyword, max_results=10):
    params = dict(_VIVO_DEVICE)
    params.update({
        "key": keyword, "page_index": "1",
        "apps_per_page": str(min(max_results, 20)), "search_source": "0",
    })
    body = urllib.parse.urlencode(params).encode("utf-8")
    try:
        data = json.loads(_post(_VIVO_BASE + "/port/packages/", body).decode("utf-8", errors="ignore"))
    except Exception as e:
        print("[store] vivo 搜索失败: %s" % e)
        return 0, []
    if not data.get("result") or not data.get("value"):
        return 0, []
    items = []
    for it in data["value"][:max_results]:
        items.append({
            "name": it.get("title_zh") or it.get("mainTitle"),
            "developer": it.get("developer"),
            "genre": it.get("level1CategoryName") or it.get("categoryName"),
            "installs": it.get("download_count"),
            "score": it.get("score"),
        })
    return len(items), items


# ===================== 小米 =====================
_MI_BASE = "https://app.market.xiaomi.com"
_MI_SALT = "good luck!"
_MI_B64_STD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_MI_B64_CUSTOM = "leDTKhmg4MafVFp73x6djvLiHn2G9XPruARBwS0q1OzNJt8WobZsQcYyEICk5U-_"
_MI_B64_TRANS = str.maketrans(_MI_B64_STD, _MI_B64_CUSTOM)
_MI_SIG_KEYS = {
    "activedTimeInterval", "ad", "appId", "count", "keyword", "la", "language",
    "lo", "co", "model", "device", "_n", "page", "pageSize", "ref", "refs",
    "flag", "sourcePackage", "pageRef", "searchFrom", "responseType",
    "native", "renderType", "bottomTab", "pageTag", "type", "stamp", "sid",
}
_MI_DEVICE = {
    "co": "CN", "la": "zh", "lo": "CN", "model": "MI 6", "device": "sagit",
    "deviceType": "0", "os": "9.9.3", "sdk": "28", "androidVersion": "9",
    "resolution": "1080*1920", "densityDpi": "440", "densityScaleFactor": "3.0",
    "marketVersion": "40007430", "miuiBigVersionCode": "8",
    "miuiBigVersionName": "V10-dev", "clientConfigVersion": "447",
    "pageConfigVersion": "18430101", "webResVersion": "3193",
    "network": "wifi", "carrier": "unknown", "cpuArchitecture": "arm64-v8a,armeabi-v7a,armeabi",
}


def _mi_nonce():
    ts = str(int(time.time() * 1000))
    return "%s_%s" % (ts, random.randint(100, 999))


def _mi_b64(data_bytes):
    std = base64.urlsafe_b64encode(data_bytes).decode("utf-8").rstrip("=")
    return std.translate(_MI_B64_TRANS)


def _mi_sign(base_url, params):
    parsed = urllib.parse.urlparse(base_url + "?" + urllib.parse.urlencode(params))
    path = parsed.path
    flat = {k: v for k, v in params.items()}
    nonce = _mi_nonce()
    flat["_n"] = nonce
    sig_params = {k: v for k, v in flat.items() if k in _MI_SIG_KEYS}
    sorted_keys = sorted(k for k in sig_params if k != "_n")
    tokens = ["_n", sig_params["_n"][::-1]]
    for k in sorted_keys:
        tokens.append(k)
        tokens.append(sig_params[k][::-1])
    parts = [tokens[i] + "&" + tokens[i + 1] for i in range(0, len(tokens), 2)]
    arranged = path + "\n" + "=".join(parts)
    ts = int(nonce.split("_")[0])
    algo_map = {0: hashlib.md5, 1: hashlib.sha256, 2: hashlib.sha1, 3: hashlib.sha384}
    h = hmac.new((_MI_SALT + nonce).encode("utf-8"), arranged.encode("utf-8"),
                 algo_map[ts % 4]).digest()
    return _mi_b64(h), nonce


def xiaomi_search(keyword, max_results=10):
    params = dict(_MI_DEVICE)
    params.update({
        "keyword": keyword, "page": "0", "flag": "2", "ref": "input",
        "refs": "input-searchResult", "pageRef": "android",
        "sourcePackage": "android", "searchFrom": "input",
        "responseType": "1", "native": "1", "renderType": "1",
        "bottomTab": "true", "activedTimeInterval": str(int(time.time() * 1000)),
    })
    try:
        sig, nonce = _mi_sign(_MI_BASE + "/apm/search", params)
        params["_n"] = nonce
        params["_s"] = sig
        params["_v"] = "1"
        url = _MI_BASE + "/apm/search?" + urllib.parse.urlencode(params)
        data = json.loads(_get(url, headers={"User-Agent": UA_DALVIK, "Accept": "application/json",
                                             "Accept-Encoding": "gzip"}, timeout=15).decode("utf-8", errors="ignore"))
    except Exception as e:
        print("[store] xiaomi 搜索失败: %s" % e)
        return 0, []
    if data.get("code") != 0:
        return 0, []
    items = []
    for grp in data.get("list", []):
        for app in grp.get("data", {}).get("listApp", []):
            items.append({
                "name": app.get("displayName", ""),
                "developer": app.get("publisherName", ""),
                "genre": app.get("level1CategoryName", ""),
                "installs": app.get("downloadCount"),
                "score": app.get("ratingScore"),
            })
    items = items[:max_results]
    return len(items), items


if __name__ == "__main__":
    for name, fn in [("huawei", huawei_search), ("vivo", vivo_search), ("xiaomi", xiaomi_search)]:
        n, items = fn("计算器")
        print(name, n, items[:2] if items else [])
