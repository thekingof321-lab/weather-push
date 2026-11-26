import os, sys, json, gzip, math, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

SENDKEY = os.environ["SENDKEY"]
QWKEY = os.environ["QWKEY"]
HOST = "nf6aq2yvr9.re.qweatherapi.com"
MODE = sys.argv[1] if len(sys.argv) > 1 else "realtime"
ACTION = sys.argv[2] if len(sys.argv) > 2 else "send"
DRY = os.environ.get("DRY_RUN", "") == "1"
REPO = "thekingof321-lab/weather-push"
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

def collect():
    bj = timezone(timedelta(hours=8))
    now = datetime.now(bj)
    today = now.strftime("%Y-%m-%d")
    target = (now + timedelta(days=1)).strftime("%Y-%m-%d") + "T00:00+08:00"
    is_mid = MODE == "midnight"
    res = []
    for name, loc in CITIES:
        if is_mid:
            d = fetch("/v7/weather/24h", loc)
            hr = next((x for x in d["hourly"] if x["fxTime"] == target), None)
            if hr is None:
                res.append({"name": name, "missing": True, "link": d.get("fxLink", "")})
                continue
            t, rh = float(hr["temp"]), float(hr["humidity"])
            res.append({
                "name": name, "temp": hr["temp"],
                "feel": f(feels_like(t, rh, float(hr["windSpeed"])), 1),
                "rh": hr["humidity"], "dew": hr["dew"], "pop": hr["pop"],
                "wind": hr["windSpeed"], "winddir": hr["windDir"] + hr["windScale"] + "\u7ea7",
                "text": hr["text"], "pressure": hr["pressure"],
                "lo": None, "hi": None, "sunrise": None, "sunset": None,
                "link": d.get("fxLink", ""),
            })
        else:
            d = fetch("/v7/weather/now", loc)
            h24 = fetch("/v7/weather/24h", loc)
            d7 = fetch("/v7/weather/7d", loc)
            n, day = d["now"], d7["daily"][0]
            t, rh = float(n["temp"]), float(n["humidity"])
            cur = min(h24["hourly"], key=lambda x: abs(
                (datetime.strptime(x["fxTime"][:16], "%Y-%m-%dT%H:%M") -
                 datetime.strptime(n["obsTime"][:16], "%Y-%m-%dT%H:%M")).total_seconds()))
            pops = [int(x["pop"]) for x in h24["hourly"] if x["fxTime"].startswith(today) and x.get("pop")]
            res.append({
                "name": name, "temp": n["temp"],
                "feel": n.get("feelsLike") or f(feels_like(t, rh, float(n["windSpeed"])), 1),
                "rh": n["humidity"], "dew": cur["dew"], "pop": max(pops) if pops else 0,
                "wind": n["windSpeed"], "winddir": n["windDir"] + n["windScale"] + "\u7ea7",
                "text": n["text"], "pressure": n["pressure"],
                "lo": day["tempMin"], "hi": day["tempMax"],
                "sunrise": day["sunrise"][-5:], "sunset": day["sunset"][-5:],
                "link": d.get("fxLink", ""),
            })
    return res, is_mid, now

def chart_rows(a, b):
    return [
        ("气温", float(a["temp"]), a["temp"] + "℃", float(b["temp"]), b["temp"] + "℃", 35.0, 0),
        ("体感", float(a["feel"]), a["feel"] + "℃", float(b["feel"]), b["feel"] + "℃", 35.0, 0),
        ("湿度", float(a["rh"]), f(a["rh"]) + "%", float(b["rh"]), f(b["rh"]) + "%", 100.0, 0),
        ("露点", float(a["dew"]), a["dew"] + "℃", float(b["dew"]), b["dew"] + "℃", 35.0, 10),
        ("降水概率", float(a["pop"]), f(a["pop"]) + "%", float(b["pop"]), f(b["pop"]) + "%", 30.0, 0),
        ("风速", float(a["wind"]), f(a["wind"]) + "km/h", float(b["wind"]), f(b["wind"]) + "km/h", 40.0, 0),
    ]

def font_path():
    p = os.environ.get("FONT_PATH", "NotoSansCJKsc-Regular.otf")
    if os.path.exists(p):
        return p
    for cand in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]:
        if os.path.exists(cand):
            return cand
    return p

def blen(v, mx):
    return max(20.0, 360.0 * float(v) / float(mx))

def draw_image(rows, a, b, is_mid, now, out):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("(PIL 不可用，跳过画图)")
        return False
    fp = font_path()
    if not os.path.exists(fp):
        print("(找不到中文字体，跳过画图)")
        return False
    W, H = 1120, 660
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    C_TITLE = (17, 24, 39); C_NUM = (31, 41, 55); C_METRIC = (55, 65, 81)
    C_SUB = (100, 116, 139); C_BLUE = (59, 130, 246); C_ORANGE = (249, 115, 22)
    C_SLOT = (238, 242, 247); C_LEGEND = (55, 65, 81)
    C_CARD = (241, 243, 245); C_CARDT = (31, 41, 55); C_CARDS = (71, 85, 105)
    cache = {}
    def F(size):
        if size not in cache:
            cache[size] = ImageFont.truetype(fp, size)
        return cache[size]
    def txt(x, y, s, size, fill, anchor="mm", bold=False):
        d.text((x, y), s, font=F(size), fill=fill, anchor=anchor,
               stroke_width=1 if bold else 0, stroke_fill=fill)
    def rrect(x1, y1, x2, y2, r, fill):
        d.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fill)

    txt(560, 34, "两地天气对比", 27, C_TITLE, bold=True)
    tag = "今晚12点预报" if is_mid else "实况"
    txt(560, 68, tag + " · " + now.strftime("%m-%d %H:%M"), 16, C_SUB)

    rrect(170, 100, 186, 116, 4, C_BLUE)
    txt(194, 108, "中山", 20, C_LEGEND, anchor="lm", bold=True)
    rrect(934, 100, 950, 116, 4, C_ORANGE)
    txt(958, 108, "廉江", 20, C_LEGEND, anchor="lm", bold=True)

    SLOT_W = 360.0
    rowH = 58; startY = 152; barH = 22
    LX = 40; RX = 720
    for i, (name, v1, s1, v2, s2, mx, off) in enumerate(rows):
        cy = startY + i * rowH
        by = cy - barH // 2
        rrect(LX, by, LX + SLOT_W, by + barH, 11, C_SLOT)
        zw = blen(v1 + off, mx)
        rrect(LX + SLOT_W - zw, by, LX + SLOT_W, by + barH, 11, C_BLUE)
        rrect(RX, by, RX + SLOT_W, by + barH, 11, C_SLOT)
        lw = blen(v2 + off, mx)
        rrect(RX, by, RX + lw, by + barH, 11, C_ORANGE)
        txt(410, cy, s1, 23, C_NUM, anchor="lm")
        txt(560, cy, name, 30, C_METRIC, anchor="mm")
        txt(710, cy, s2, 23, C_NUM, anchor="rm")

    if not is_mid:
        l2 = "今日 %s~%s℃" % (a["lo"], a["hi"])
        l3 = "日出 %s · 日落 %s" % (a["sunrise"], a["sunset"])
        l2b = "今日 %s~%s℃" % (b["lo"], b["hi"])
        l3b = "日出 %s · 日落 %s" % (b["sunrise"], b["sunset"])
    else:
        l2 = "气温 %s℃ · 体感 %s℃" % (a["temp"], a["feel"])
        l3 = "气压 %shPa · 风 %s" % (a["pressure"], a["winddir"])
        l2b = "气温 %s℃ · 体感 %s℃" % (b["temp"], b["feel"])
        l3b = "气压 %shPa · 风 %s" % (b["pressure"], b["winddir"])

    for x, city, cond, s2, s3 in (
        (40, a["name"], a["text"], l2, l3),
        (600, b["name"], b["text"], l2b, l3b)):
        rrect(x, 462, x + 480, 645, 12, C_CARD)
        txt(x + 28, 496, "%s · %s" % (city, cond), 27, C_CARDT, anchor="lm", bold=True)
        txt(x + 28, 546, s2, 29, C_CARDS, anchor="lm")
        txt(x + 28, 596, s3, 29, C_CARDS, anchor="lm")

    img.save(out)
    return True

def build_desp(data, is_mid, now, img_url):
    lines = ["![两地天气对比](%s)" % img_url, ""]
    tag = "今晚12点" if is_mid else "实况"
    for c in data:
        if c.get("missing"):
            lines += ["**%s · %s**" % (c["name"], tag), "暂无数据", ""]
            continue
        lines.append("**%s · %s**" % (c["name"], tag))
        lines.append("气温 %s℃｜体感 %s℃｜湿度 %s%%｜露点 %s℃" % (
            c["temp"], c["feel"], c["rh"], c["dew"]))
        if not is_mid:
            lines.append("%s｜今日 %s~%s℃｜降水概率 %s%%｜风 %skm/h %s" % (
                c["text"], c["lo"], c["hi"], c["pop"], c["wind"], c["winddir"]))
        else:
            lines.append("%s｜降水概率 %s%%｜气压 %shPa｜风 %s" % (
                c["text"], c["pop"], c["pressure"], c["winddir"]))
        lines.append("")
    lines.append("[查看" + data[0]["name"] + "详细天气 >>](" + data[0]["link"] + ")")
    lines.append("")
    lines.append("[查看" + data[1]["name"] + "详细天气 >>](" + data[1]["link"] + ")")
    return "\n".join(lines)

def main():
    data, is_mid, now = collect()
    day = now.strftime("%Y-%m-%d")
    img_name = "%s-%s.png" % (day, MODE)
    os.makedirs("img", exist_ok=True)
    img_path = os.path.join("img", img_name)
    img_url = "https://cdn.jsdelivr.net/gh/%s@main/img/%s" % (REPO, img_name)
    title = "今晚12点天气预报" if is_mid else "两地实时天气"
    desp = build_desp(data, is_mid, now, img_url)

    drawn = False
    if ACTION != "send":
        drawn = draw_image(chart_rows(data[0], data[1]), data[0], data[1], is_mid, now, img_path)
        print("IMG_PATH:", img_path, "DRAWN:", drawn)

    if DRY or ACTION != "send":
        print("TITLE:", title)
        print(desp)
        return

    payload = urllib.parse.urlencode({"title": title, "desp": desp}).encode()
    req = urllib.request.Request("https://sctapi.ftqq.com/" + SENDKEY + ".send", data=payload)
    with urllib.request.urlopen(req, timeout=30) as r:
        print(r.read().decode())

if __name__ == "__main__":
    main()
