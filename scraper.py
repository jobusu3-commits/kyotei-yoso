import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

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


def _build_id_to_name(soup) -> dict:
    """ページ内のtobanリンクから登録番号→選手名マップを構築"""
    id_to_name = {}
    for a in soup.find_all("a"):
        href = a.get("href", "")
        toban_m = re.search(r'toban=(\d+)', href)
        if not toban_m:
            continue
        toban = toban_m.group(1)
        if toban in id_to_name:
            continue

        # アンカーのテキスト
        text = a.get_text(strip=True)
        if re.search(r'[一-龯ぁ-んァ-ン]{2,}', text):
            id_to_name[toban] = text
            continue

        # 親要素・兄弟要素からも探す
        parent = a.parent
        if parent:
            for elem in [parent] + list(parent.find_next_siblings(limit=2)):
                t = elem.get_text(strip=True)
                if re.search(r'[一-龯]{2,}', t) and len(t) <= 12:
                    id_to_name[toban] = t
                    break

    return id_to_name


def _fetch_odds_page(rno: str, jcd: str, hd: str):
    """オッズページを取得してBeautifulSoupを返す"""
    url = f"https://www.boatrace.jp/owpc/pc/race/oddstf?rno={rno}&jcd={jcd}&hd={hd}"
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            return BeautifulSoup(resp.text, "html.parser")
        except Exception:
            if attempt == 2:
                raise
    return BeautifulSoup("", "html.parser")


def _fetch_odds_from_soup(soup) -> dict:
    """オッズページsoupから単勝オッズを取得"""
    odds_map = {}
    # is-boatColor td から同じ行のオッズを探す
    for td in soup.find_all("td", class_=re.compile(r"is-boatColor\d")):
        boat_num = td.get_text(strip=True)
        if not re.match(r'^[1-6]$', boat_num):
            continue
        row = td.find_parent("tr")
        if not row:
            continue
        for sibling_td in row.find_all("td"):
            text = sibling_td.get_text(strip=True)
            if re.match(r'^\d{1,3}\.\d$', text):
                try:
                    odds_map[boat_num] = float(text)
                    break
                except ValueError:
                    pass

    # フォールバック: 全テーブルから艇番+オッズパターン
    if not odds_map:
        for row in soup.find_all("tr"):
            tds = row.find_all("td")
            for i, td in enumerate(tds):
                boat = td.get_text(strip=True)
                if not re.match(r'^[1-6]$', boat):
                    continue
                for j in range(i + 1, min(i + 5, len(tds))):
                    t = tds[j].get_text(strip=True)
                    if re.match(r'^\d{1,3}\.\d$', t):
                        try:
                            odds_map[boat] = float(t)
                        except ValueError:
                            pass
                        break

    return odds_map


def _fetch_names_from_odds_page(soup) -> dict:
    """オッズページから艇番→選手名を取得"""
    boat_to_name = {}
    id_to_name = _build_id_to_name(soup)

    for td in soup.find_all("td", class_=re.compile(r"is-boatColor[1-6]")):
        boat_num = td.get_text(strip=True)
        if not re.match(r'^[1-6]$', boat_num):
            continue
        if boat_num in boat_to_name:
            continue
        row = td.find_parent("tr")
        if not row:
            continue

        # 行内のtobanリンクから名前を取得
        for a in row.find_all("a"):
            m = re.search(r'toban=(\d+)', a.get("href", ""))
            if m and m.group(1) in id_to_name:
                boat_to_name[boat_num] = id_to_name[m.group(1)]
                break

        # tobanなし: 行内の日本語テキストから探す
        if boat_num not in boat_to_name:
            for row_td in row.find_all("td"):
                text = row_td.get_text(strip=True)
                if re.search(r'[一-龯]{2,}', text) and len(text) <= 12 and text != boat_num:
                    boat_to_name[boat_num] = text
                    break

    return boat_to_name


def _fetch_weather(rno: str, jcd: str, hd: str) -> dict:
    """直前情報から天候・風速・波高を取得"""
    default = {"weather": "不明", "wind_speed": 0, "wave": 0, "wind_dir": ""}
    try:
        url = f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={rno}&jcd={jcd}&hd={hd}"
        resp = requests.get(url, headers=HEADERS, timeout=20)
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


def _extract_floats(text: str) -> list[float]:
    vals = []
    for m in re.finditer(r'\b(\d{1,2}\.\d{2})\b', text):
        v = float(m.group(1))
        if v >= 1.0:
            vals.append(v)
    return vals


def fetch_race_data(url: str) -> tuple[list[dict], dict]:
    rno, jcd, hd = _extract_params(url)

    # 出走表ページ取得
    resp = requests.get(url, headers=HEADERS, timeout=25)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    # オッズページを並行取得（名前補完・オッズ取得に使う）
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_odds_soup = ex.submit(_fetch_odds_page, rno, jcd, hd)
        f_weather = ex.submit(_fetch_weather, rno, jcd, hd)
        odds_soup = f_odds_soup.result()
        weather = f_weather.result()

    odds_map = _fetch_odds_from_soup(odds_soup)
    boat_to_name_from_odds = _fetch_names_from_odds_page(odds_soup)

    # 出走表ページから登録番号→名前マップ構築
    id_to_name = _build_id_to_name(soup)

    # tobanリンクを持つ行を選手行として特定
    racer_rows = {}
    for row in soup.find_all("tr"):
        racer_id = ""
        for a in row.find_all("a"):
            m = re.search(r'toban=(\d+)', a.get("href", ""))
            if m:
                racer_id = m.group(1)
                break
        if not racer_id:
            continue
        tds = row.find_all("td")
        if not tds:
            continue
        try:
            course = int(tds[0].get_text(strip=True))
            if not (1 <= course <= 6):
                continue
        except ValueError:
            continue
        if course not in racer_rows:
            racer_rows[course] = (row, racer_id)

    # is-boatColor で不足分を補完
    if len(racer_rows) < 6:
        for td in soup.find_all("td", class_=re.compile(r"is-boatColor[1-6]")):
            boat_text = td.get_text(strip=True)
            if not re.match(r'^[1-6]$', boat_text):
                continue
            course = int(boat_text)
            if course in racer_rows:
                continue
            row = td.find_parent("tr")
            if row:
                racer_rows[course] = (row, "")

    # コースが取れなかった場合は1〜6を全部作る
    for c in range(1, 7):
        if c not in racer_rows:
            racer_rows[c] = (None, "")

    all_rows = soup.find_all("tr")
    racers = []

    for course in sorted(racer_rows.keys()):
        row, racer_id = racer_rows[course]

        # 選手名: id_to_name → オッズページ補完 → X号艇
        name = id_to_name.get(racer_id, "")
        if not name:
            name = boat_to_name_from_odds.get(str(course), "")
        if not name and row is not None:
            for td in row.find_all("td"):
                td_text = td.get_text(separator="\n", strip=True)
                lines = [l.strip() for l in td_text.split('\n') if l.strip()]
                jp = [l for l in lines if re.match(r'^[一-龯ぁ-んァ-ン]{1,5}$', l)]
                if len(jp) >= 2:
                    name = "　".join(jp[:2])
                    break
                elif len(jp) == 1:
                    name = jp[0]
                    break
        if not name:
            name = f"{course}号艇"

        # 階級
        rank = "B1"
        if row is not None:
            rank_m = re.search(r'\b(A1|A2|B1|B2)\b', row.get_text())
            if rank_m:
                rank = rank_m.group(1)

        # 数値データ: 当該行 + 直後5行を合算
        combined_text = ""
        if row is not None:
            combined_text = row.get_text(separator=" ")
            try:
                row_idx = all_rows.index(row)
                for i in range(1, 6):
                    if row_idx + i >= len(all_rows):
                        break
                    next_row = all_rows[row_idx + i]
                    has_toban = any('toban=' in a.get("href", "") for a in next_row.find_all("a"))
                    has_boat_color = bool(next_row.find("td", class_=re.compile(r"is-boatColor[1-6]")))
                    if has_toban or has_boat_color:
                        break
                    combined_text += " " + next_row.get_text(separator=" ")
            except ValueError:
                pass

        float_vals = _extract_floats(combined_text)
        win_vals = [v for v in float_vals if 1.0 <= v <= 9.99]
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
            "odds": odds_map.get(str(course), 10.0),
        })

    if not any(r["name"] != f"{r['course']}号艇" for r in racers):
        raise ValueError(
            "出走表データが取得できませんでした。\n"
            "例: https://www.boatrace.jp/owpc/pc/race/racelist?rno=1&jcd=01&hd=20260511"
        )

    racers.sort(key=lambda r: r["course"])

    race_info = {
        "rno": rno,
        "jcd": jcd,
        "venue": VENUE_NAMES.get(jcd, f"場{jcd}"),
        "date": f"{hd[:4]}-{hd[4:6]}-{hd[6:]}",
        "weather": weather,
    }

    return racers, race_info
