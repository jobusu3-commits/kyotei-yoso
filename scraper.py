import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.boatrace.jp/",
}

VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}


def _extract_params(url: str) -> tuple[str, str, str]:
    rno = re.search(r'rno=(\d+)', url)
    jcd = re.search(r'jcd=(\d+)', url)
    hd = re.search(r'hd=(\d+)', url)
    if not (rno and jcd and hd):
        raise ValueError(
            "URLからrno/jcd/hdが取得できません。\n"
            "例: https://www.boatrace.jp/owpc/pc/race/racelist?rno=1&jcd=01&hd=20260511"
        )
    return rno.group(1), jcd.group(1), hd.group(1)


def _fetch_odds(rno: str, jcd: str, hd: str) -> dict:
    """単勝オッズ {艇番(str): float}"""
    try:
        url = f"https://www.boatrace.jp/owpc/pc/race/oddstf?rno={rno}&jcd={jcd}&hd={hd}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        odds_map = {}
        for td in soup.find_all("td", class_=re.compile(r"is-boatColor\d")):
            boat_num = td.get_text(strip=True)
            if re.match(r'^[1-6]$', boat_num):
                next_td = td.find_next_sibling("td")
                if next_td:
                    try:
                        odds_map[boat_num] = float(next_td.get_text(strip=True))
                    except ValueError:
                        pass
        if not odds_map:
            for table in soup.find_all("table"):
                for row in table.find_all("tr"):
                    tds = row.find_all("td")
                    if len(tds) >= 2:
                        boat = tds[0].get_text(strip=True)
                        odds_text = tds[1].get_text(strip=True)
                        if re.match(r'^[1-6]$', boat) and re.match(r'^\d+\.\d+$', odds_text):
                            odds_map[boat] = float(odds_text)
        return odds_map
    except Exception:
        return {}


def _fetch_weather(rno: str, jcd: str, hd: str) -> dict:
    """直前情報から天候・風速・波高を取得"""
    default = {"weather": "不明", "wind_speed": 0, "wave": 0, "wind_dir": ""}
    try:
        url = f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={rno}&jcd={jcd}&hd={hd}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator=" ")

        weather = "不明"
        for w in ["晴", "曇", "雨", "雪"]:
            if w in text:
                weather = w
                break

        wind_m = re.search(r'風速\s*(\d+)', text)
        wave_m = re.search(r'波高\s*(\d+)', text)
        wind_dir_m = re.search(r'(追い風|向かい風|横風|無風)', text)

        return {
            "weather": weather,
            "wind_speed": int(wind_m.group(1)) if wind_m else 0,
            "wave": int(wave_m.group(1)) if wave_m else 0,
            "wind_dir": wind_dir_m.group(1) if wind_dir_m else "",
        }
    except Exception:
        return default


def fetch_race_data(url: str) -> tuple[list[dict], dict]:
    rno, jcd, hd = _extract_params(url)

    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    # ページ全体から登録番号→選手名マップを事前構築
    id_to_name = {}
    for a in soup.find_all("a"):
        href = a.get("href", "")
        toban_m = re.search(r'toban=(\d+)', href)
        if not toban_m:
            continue
        text = a.get_text(strip=True)
        if re.search(r'[一-龯ぁ-んァ-ン]{2,}', text):
            id_to_name[toban_m.group(1)] = text

    racers = []
    seen_courses = set()

    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 9:
            continue

        try:
            course = int(tds[0].get_text(strip=True))
            if not (1 <= course <= 6) or course in seen_courses:
                continue
        except ValueError:
            continue

        seen_courses.add(course)

        # 登録番号を取得してマップから選手名を引く
        racer_id = ""
        for a in row.find_all("a"):
            m = re.search(r'toban=(\d+)', a.get("href", ""))
            if m:
                racer_id = m.group(1)
                break
        name = id_to_name.get(racer_id, "")

        # フォールバック: tobanリンクを含むtdのテキストから直接名前を抽出
        if not name:
            for td in tds:
                if not any('toban=' in a.get("href", "") for a in td.find_all("a")):
                    continue
                td_text = td.get_text(separator="\n", strip=True)
                lines = [l.strip() for l in td_text.split('\n') if l.strip()]
                jp_parts = [l for l in lines if re.match(r'^[一-龯ぁ-んァ-ン]{1,5}$', l)]
                if jp_parts:
                    name = "　".join(jp_parts[:2]) if len(jp_parts) >= 2 else jp_parts[0]
                    break

        if not name:
            name = f"{course}号艇"

        # 階級
        rank = "B1"
        rank_m = re.search(r'\b(A1|A2|B1|B2)\b', row.get_text())
        if rank_m:
            rank = rank_m.group(1)

        # 数値データ（ST値を除外して勝率・2連率系を取得）
        float_vals = []
        for td in tds:
            text = td.get_text(separator=" ", strip=True)
            for m in re.finditer(r'\b(\d{1,2}\.\d{2})\b', text):
                val = float(m.group(1))
                if val >= 1.0:
                    float_vals.append(val)

        win_vals = [v for v in float_vals if 1.0 <= v <= 9.9]
        rate_vals = [v for v in float_vals if v >= 10.0]

        def safe(lst, i, default):
            return lst[i] if i < len(lst) else default

        racers.append({
            "course": course,
            "name": name,
            "racer_id": racer_id,
            "rank": rank,
            "win_rate": safe(win_vals, 0, 5.0),
            "nirenritsu": safe(rate_vals, 0, 35.0),
            "local_win_rate": safe(win_vals, 1, 5.0),
            "local_nirenritsu": safe(rate_vals, 1, 35.0),
            "motor_nirenritsu": safe(rate_vals, 2, 35.0),
            "boat_nirenritsu": safe(rate_vals, 3, 35.0),
            "odds": 10.0,
        })

    if not racers:
        raise ValueError(
            "出走表データが取得できませんでした。\n"
            "例: https://www.boatrace.jp/owpc/pc/race/racelist?rno=1&jcd=01&hd=20260511"
        )

    racers.sort(key=lambda r: r["course"])

    # 並行取得
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_odds = ex.submit(_fetch_odds, rno, jcd, hd)
        f_weather = ex.submit(_fetch_weather, rno, jcd, hd)
        odds_map = f_odds.result()
        weather = f_weather.result()

    for r in racers:
        r["odds"] = odds_map.get(str(r["course"]), 10.0)

    race_info = {
        "rno": rno,
        "jcd": jcd,
        "venue": VENUE_NAMES.get(jcd, f"場{jcd}"),
        "date": f"{hd[:4]}-{hd[4:6]}-{hd[6:]}",
        "weather": weather,
    }

    return racers, race_info
