# 場ごとの1コース補正（全国平均より不利な場はマイナス）
VENUE_COURSE_ADJ = {
    "03": {1: -8, 2: +3},   # 江戸川: 水流・潮の影響で1コース最も不利
    "02": {1: -4},           # 戸田: 狭いコースで1コース不利
    "04": {1: -3},           # 平和島: 海水・うねりで1コース不利
    "11": {1: -3},           # びわこ: 風の影響が強い
    "05": {1: -1},           # 多摩川: やや1コース不利
}

# 波高・風速による1コース補正
def _wave_adj(wave: int, wind_speed: int) -> int:
    if wave >= 15 or wind_speed >= 7:
        return -5  # 荒水面は1コース大幅不利
    elif wave >= 10 or wind_speed >= 5:
        return -3
    return 0


def score_course(course: int, jcd: str = "", wave: int = 0, wind_speed: int = 0) -> int:
    base = {1: 25, 2: 13, 3: 9, 4: 7, 5: 5, 6: 3}.get(course, 3)
    adj = VENUE_COURSE_ADJ.get(jcd, {}).get(course, 0)
    if course == 1:
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
