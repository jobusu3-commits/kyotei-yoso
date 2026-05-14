# 場ごとのコース補正（全国平均1コース勝率55%からの乖離をポイント換算）
VENUE_COURSE_ADJ = {
    "01": {1: -2, 4: +2, 5: +2, 6: +1},  # 桐生(52%): 強風でアウト有利
    "02": {1: -4},                          # 戸田(48%): 狭く差し多発
    "03": {1: -8, 2: +3},                  # 江戸川(41%): 潮流で全国最不利
    "04": {1: -3},                          # 平和島(50%): 海水・うねり
    "05": {1: -1},                          # 多摩川(54%): やや不利
    "06": {1: -2},                          # 浜名湖(53%): 海水・風
    "07": {},                               # 蒲郡(55%): 全国平均
    "08": {},                               # 常滑(56%): ほぼ平均
    "09": {1: -2},                          # 津(53%): 海水・うねり
    "10": {1: -2},                          # 三国(53%): 海水・風
    "11": {1: -3},                          # びわこ(51%): 風の影響大
    "12": {1: +3},                          # 住之江(59%): 内水面・1コース有利
    "13": {1: +2},                          # 尼崎(58%): 内水面・1コース有利
    "14": {1: +1},                          # 鳴門(56%): やや1コース有利
    "15": {1: -1},                          # 丸亀(54%): 潮流の影響
    "16": {1: -1},                          # 児島(54%): 海水
    "17": {1: -2},                          # 宮島(53%): 海水・潮流
    "18": {},                               # 徳山(55%): ほぼ平均
    "19": {1: -1},                          # 下関(54%): 海水
    "20": {1: -1},                          # 若松(53%): 海水・風
    "21": {1: +2},                          # 芦屋(57%): 内水面・1コース有利
    "22": {1: +2},                          # 福岡(57%): 1コース有利
    "23": {1: -3},                          # 唐津(48%): 潮流・風の影響大
    "24": {1: +5},                          # 大村(65%): 内水面・全国最有利
}

# 波高・風速による1コース補正
def _wave_adj(wave: int, wind_speed: int) -> int:
    if wave >= 15 or wind_speed >= 7:
        return -5  # 荒水面は1コース大幅不利
    elif wave >= 10 or wind_speed >= 5:
        return -3
    return 0


def score_course(course: int, jcd: str = "", wave: int = 0, wind_speed: int = 0) -> int:
    # 2コース: 2着率約25%と高いため+4、3コース: 2着率約18%のため+2
    base = {1: 25, 2: 17, 3: 11, 4: 7, 5: 5, 6: 3}.get(course, 3)
    adj = VENUE_COURSE_ADJ.get(jcd, {}).get(course, 0)
    if course == 1:
        # 江戸川の穏やか水面（波高<8cm・風速≤6m）では1コース補正を-8→-4に緩和
        if jcd == "03" and wave < 8 and wind_speed <= 6:
            adj = -4
        adj += _wave_adj(wave, wind_speed)
    return max(1, base + adj)


def score_rank(rank: str) -> int:
    return {"A1": 20, "A2": 14, "B1": 7, "B2": 2}.get(rank, 7)


def score_win_rate(rate: float) -> int:
    if rate >= 7.0:
        return 18
    elif rate >= 6.5:
        return 15
    elif rate >= 6.0:
        return 12
    elif rate >= 5.5:
        return 9
    elif rate >= 5.0:
        return 6
    elif rate >= 4.5:
        return 3
    else:
        return 1


def score_nirenritsu(rate: float) -> int:
    if rate >= 55.0:
        return 14
    elif rate >= 50.0:
        return 12
    elif rate >= 45.0:
        return 10
    elif rate >= 40.0:
        return 8
    elif rate >= 35.0:
        return 6
    elif rate >= 30.0:
        return 4
    else:
        return 2


def score_motor(rate: float) -> int:
    if rate >= 50.0:
        return 12
    elif rate >= 45.0:
        return 10
    elif rate >= 40.0:
        return 8
    elif rate >= 35.0:
        return 6
    elif rate >= 30.0:
        return 4
    elif rate >= 25.0:
        return 2
    else:
        return 1


def score_local(rate: float) -> int:
    if rate >= 50.0:
        return 8
    elif rate >= 40.0:
        return 6
    elif rate >= 30.0:
        return 4
    else:
        return 2


def calc_score(racer: dict, jcd: str = "", wave: int = 0, wind_speed: int = 0) -> int:
    return (
        score_course(racer["course"], jcd, wave, wind_speed)
        + score_rank(racer["rank"])
        + score_win_rate(racer["win_rate"])
        + score_nirenritsu(racer["nirenritsu"])
        + score_motor(racer["motor_nirenritsu"])
        + score_local(racer["local_nirenritsu"])
    )


def find_anaba(racers: list[dict]) -> list[dict]:
    candidates = []
    for r in racers:
        if r["course"] <= 3:
            continue
        if r["nirenritsu"] >= 40 or r["motor_nirenritsu"] >= 45 or r["rank"] == "A1":
            candidates.append(r)
    return sorted(candidates, key=lambda r: r.get("score", 0), reverse=True)[:2]


def rank_racers(racers: list[dict], jcd: str = "", wave: int = 0, wind_speed: int = 0) -> list[dict]:
    for r in racers:
        r["score"] = calc_score(r, jcd, wave, wind_speed)
    return sorted(racers, key=lambda r: r["score"], reverse=True)
