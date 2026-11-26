import os, sys, json, gzip, math, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

SENDKEY = os.environ["SENDKEY"]
QWKEY = os.environ["QWKEY"]
HOST = "nf6aq2yvr9.re.qweatherapi.com"
MODE = sys.argv[1] if len(sys.argv) > 1 else "realtime"
DRY = os.environ.get("DRY_RUN", "") == "1"
CITIES = [("中山", "113.463889,22.529167"), ("廉江", "110.318174,21.606512")]

def fetch(path, loc):
    url = "https://" + HOST + path + "?location=" + loc
    req = urllib.request.Request(url, headers={"X-QW-Api-Key": QWKEY, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)

def feels_like(t, rh, wind_kmh):
    e = rh / 100.0 * 6.105 * math.exp(17.27 * t / (237.7 + t))
    return t + 0.33 * e - 0.70 * (wind_kmh / 3.6) - 4.00

def f(x, d=0):
    return ("%." + str(d) + "f") % float(x)

def realtime_lines():
    lines = []
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    for name, loc in CITIES:
        d = fetch("/v7/weather/now", loc)
        h24 = fetch("/v7/weather/24h", loc)
        d7 = fetch("/v7/weather/7d", loc)
        n, day = d["now"], d7["daily"][0]
        t, rh = float(n["temp"]), float(n["humidity"])
        cur_hour = min(h24["hourly"], key=lambda x: abs(
            (datetime.strptime(x["fxTime"][:16], "%Y-%m-%dT%H:%M") -
             datetime.strptime(n["obsTime"][:16], "%Y-%m-%dT%H:%M")).total_seconds()))
        dp = cur_hour["dew"]
        fl = n.get("feelsLike") or f(feels_like(t, rh, float(n["windSpeed"])), 1)
        pops = [int(x["pop"]) for x in h24["hourly"] if x["fxTime"].startswith(today) and x.get("pop")]
        pop = max(pops) if pops else 0
        lines += [
            "【%s·实况】" % name,
            "气温 %s℃｜体感 %s℃｜湿度 %s%%｜露点 %s℃" % (f(t), fl, f(rh), f(dp)),
            "%s｜今日 %s~%s℃｜降水概率 %s%%｜风 %skm/h %s%s级｜气压 %shPa｜能见度 %skm｜UV %s｜日出 %s 日落 %s" % (
                n["text"], day["tempMin"], day["tempMax"], pop, n["windSpeed"],
                n["windDir"], n["windScale"], n["pressure"], n["vis"],
                day["uvIndex"], day["sunrise"], day["sunset"]),
            "[查看%s详细天气 >>](%s)" % (name, d["fxLink"]),
            "",
        ]
    return lines

def midnight_lines():
    bj = timezone(timedelta(hours=8))
    target = (datetime.now(bj) + timedelta(days=1)).strftime("%Y-%m-%d") + "T00:00+08:00"
    lines = []
    for name, loc in CITIES:
        d = fetch("/v7/weather/24h", loc)
        hr = next((x for x in d["hourly"] if x["fxTime"] == target), None)
        if hr is None:
            lines += ["【%s·今晚12点】暂无数据" % name, ""]
            continue
        t, rh = float(hr["temp"]), float(hr["humidity"])
        dp = hr["dew"]
        fl = feels_like(t, rh, float(hr["windSpeed"]))
        lines += [
            "【%s·今晚12点】" % name,
            "气温 %s℃｜体感 %s℃｜湿度 %s%%｜露点 %s℃" % (f(t), f(fl, 1), f(rh), f(dp)),
            "%s｜降水概率 %s%%｜风 %skm/h %s%s级｜气压 %shPa" % (
                hr["text"], hr["pop"], hr["windSpeed"], hr["windDir"],
                hr["windScale"], hr["pressure"]),
            "[查看%s详细天气 >>](%s)" % (name, d["fxLink"]),
            "",
        ]
    return lines

def main():
    if MODE == "midnight":
        lines, title = midnight_lines(), "今晚12点天气预报"
    else:
        lines, title = realtime_lines(), "两地实时天气"
    content = "\n".join(lines)
    if DRY:
        print(title)
        print(content)
        return
    payload = urllib.parse.urlencode({"title": title, "desp": content}).encode()
    req = urllib.request.Request("https://sctapi.ftqq.com/" + SENDKEY + ".send", data=payload)
    with urllib.request.urlopen(req, timeout=30) as r:
        print(r.read().decode())

main()
