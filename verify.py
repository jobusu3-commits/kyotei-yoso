"""
verify.py  使い方: python verify.py <jcd> <hd> [budget]
例: python verify.py 03 20260513 3000
"""
import sys
import io
import re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests
from bs4 import BeautifulSoup
from scraper import fetch_race_data, VENUE_NAMES, HEADERS
from scorer import rank_racers, find_anaba
from advisor import advise, should_skip


def fetch_result(rno: str, jcd: str, hd: str) -> dict | None:
    """結果ページから着順・払戻を取得。取得失敗やレース未実施はNoneを返す"""
    url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={rno}&jcd={jcd}&hd={hd}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None

    # 着順テーブル: is-boatColor{N} を持つ td から艇番を順番に取得
    order = []
    for td in soup.find_all("td", class_=re.compile(r"is-boatColor[1-6]")):
        txt = td.get_text(strip=True)
        if re.match(r"^[1-6]$", txt):
            # 着順tbodyの行かを確認（同じクラスが払戻テーブルにも出る場合がある）
            row = td.find_parent("tr")
            if not row:
                continue
            # 着順行は「着」列（全角数字）が最初のtdにある
            first_td = row.find("td")
            if first_td and re.match(r"^[１-６]$", first_td.get_text(strip=True)):
                order.append(int(txt))

    if len(order) < 3:
        return None  # レース未実施 or 取得失敗

    # 払戻テーブル: span.is-payout1 から金額を取得
    payouts = {}
    payout_table = None
    for table in soup.find_all("table"):
        if table.find("th", string=re.compile("勝式")):
            payout_table = table
            break

    if payout_table:
        current_type = ""
        for row in payout_table.find_all("tr"):
            # 勝式名
            type_td = row.find("td", attrs={"rowspan": True})
            if type_td:
                current_type = type_td.get_text(strip=True)

            # 組番
            combo_nums = []
            for span in row.find_all("span", class_="numberSet1_number"):
                t = span.get_text(strip=True)
                if re.match(r"^[1-6]$", t):
                    combo_nums.append(int(t))

            # 払戻金
            payout_span = row.find("span", class_="is-payout1")
            if payout_span:
                amt_txt = payout_span.get_text(strip=True).replace("¥", "").replace(",", "").replace("¥", "")
                try:
                    amt = int(amt_txt)
                except ValueError:
                    amt = 0
                if current_type and combo_nums and amt > 0:
                    key = (current_type, tuple(combo_nums))
                    payouts[key] = amt

    return {"order": order, "payouts": payouts}


def calc_return(advice: dict, result: dict, skip: bool) -> tuple[int, int, list[str]]:
    """投資額・回収額・詳細メモを返す"""
    if skip or not result:
        return 0, 0, []

    order = result["order"]
    payouts = result["payouts"]
    top1, top2, top3 = order[0], order[1], order[2]

    total_bet = 0
    total_return = 0
    details = []

    for bet_type, info in advice.items():
        amount = info["金額"]
        combo_str = info["買い目"]
        total_bet += amount

        hit = False
        payout_per_100 = 0

        if "単勝" in bet_type and "2" not in bet_type and "3" not in bet_type:
            # 単勝: "X号艇 名前" 形式
            m = re.match(r"(\d)号艇", combo_str)
            if m and int(m.group(1)) == top1:
                hit = True
                for (t, nums), p in payouts.items():
                    if t == "単勝" and nums == (top1,):
                        payout_per_100 = p

        elif "2連複" in bet_type:
            # "X-Y" 形式
            m = re.match(r"(\d)-(\d)", combo_str)
            if m:
                combo = {int(m.group(1)), int(m.group(2))}
                if combo == {top1, top2}:
                    hit = True
                    for (t, nums), p in payouts.items():
                        if t == "2連複" and set(nums) == combo:
                            payout_per_100 = p

        elif "2連単" in bet_type:
            # "X→Y" 形式
            m = re.match(r"(\d)→(\d)", combo_str)
            if m and int(m.group(1)) == top1 and int(m.group(2)) == top2:
                hit = True
                for (t, nums), p in payouts.items():
                    if t == "2連単" and nums == (top1, top2):
                        payout_per_100 = p

        elif "3連複" in bet_type:
            # "X-Y-Z" 形式
            m = re.match(r"(\d)-(\d)-(\d)", combo_str)
            if m:
                combo = {int(m.group(1)), int(m.group(2)), int(m.group(3))}
                if combo == {top1, top2, top3}:
                    hit = True
                    for (t, nums), p in payouts.items():
                        if t == "3連複" and set(nums) == combo:
                            payout_per_100 = p

        if hit and payout_per_100 > 0:
            ret = payout_per_100 * (amount // 100)
            total_return += ret
            details.append(f"  ✅ {bet_type} {combo_str} {amount}円 → ¥{ret:,}（払戻¥{payout_per_100}）")
        else:
            details.append(f"  ❌ {bet_type} {combo_str} {amount}円")

    return total_bet, total_return, details


def verify_day(jcd: str, hd: str, budget: int = 3000):
    venue = VENUE_NAMES.get(jcd, f"場{jcd}")
    date_str = f"{hd[:4]}-{hd[4:6]}-{hd[6:]}"
    print(f"\n{'='*55}")
    print(f"  {venue}　{date_str}　予算¥{budget:,}")
    print(f"{'='*55}")

    total_bet = 0
    total_return = 0
    skip_ok = 0      # 見送り正解（荒れ）
    skip_miss = 0    # 見送り機会損失
    invest_hit = 0   # 投資して的中
    invest_miss = 0  # 投資して外れ

    for rno in range(1, 13):
        url = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={jcd}&hd={hd}"
        try:
            racers, race_info = fetch_race_data(url)
        except Exception as e:
            print(f"\n{rno:2}R  取得失敗: {e}")
            continue

        weather = race_info.get("weather", {})
        wave = weather.get("wave", 0)
        wind_speed = weather.get("wind_speed", 0)
        ranked = rank_racers(racers, jcd, wave, wind_speed)
        anaba = find_anaba(ranked)
        skip_info = should_skip(ranked, jcd, wave, wind_speed)
        advice = advise(ranked, budget, anaba) if not skip_info else {}

        result = fetch_result(str(rno), jcd, hd)
        order = result["order"] if result else []

        bet, ret, details = calc_return(advice, result, bool(skip_info))
        total_bet += bet
        total_return += ret

        top_score = ranked[0]["score"] if ranked else 0
        order_str = "-".join(str(x) for x in order[:3]) if order else "?"
        net = ret - bet

        if skip_info:
            # 見送り: 1号艇以外が1着 or 3連単¥5,000超なら荒れ
            if order and (order[0] != ranked[0]["course"] or
                          any(p > 500 for (t, _), p in result["payouts"].items() if t == "単勝")):
                label = "見送り✅（荒れ）"
                skip_ok += 1
            else:
                label = "見送り△（機会損失）"
                skip_miss += 1
        else:
            if net >= 0:
                label = f"投資✅ +¥{net:,}"
                invest_hit += 1
            else:
                label = f"投資❌  ¥{net:,}"
                invest_miss += 1

        print(f"\n{rno:2}R  [{label}]  本命{top_score}点  着順:{order_str}  収支:{'+' if net>=0 else ''}{net:,}円")
        if skip_info:
            print(f"    見送り理由: {skip_info['reason'][:40]}")
        for d in details:
            print(d)

    net_total = total_return - total_bet
    print(f"\n{'='*55}")
    print(f"  合計投資: ¥{total_bet:,}  回収: ¥{total_return:,}  損益: {'+' if net_total>=0 else ''}¥{net_total:,}")
    print(f"  見送り正解: {skip_ok}回  機会損失: {skip_miss}回  的中: {invest_hit}回  外れ: {invest_miss}回")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    jcd = sys.argv[1] if len(sys.argv) > 1 else "03"
    hd = sys.argv[2] if len(sys.argv) > 2 else "20260513"
    budget = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
    verify_day(jcd, hd, budget)
