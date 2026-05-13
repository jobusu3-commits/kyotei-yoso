def should_skip(ranked: list[dict]) -> dict | None:
    """見送り推奨条件をチェック。見送り時はreason dictを、予想OKならNoneを返す"""
    if not ranked:
        return {"reason": "データなし"}
    top = ranked[0]
    if top["score"] < 60:
        return {"reason": f"本命スコアが低すぎます（{top['score']}点 / 基準60点）。混戦の可能性が高く、このレースは見送りを推奨します。"}
    if len(ranked) >= 2:
        gap = top["score"] - ranked[1]["score"]
        if gap < 8:
            return {"reason": f"1位と2位のスコア差が小さすぎます（差{gap}点 / 基準8点）。本命が絞れないため、このレースは見送りを推奨します。"}
    return None


def advise(ranked: list[dict], budget: int, anaba: list[dict] = None) -> dict:
    result = {}
    top = ranked[0] if len(ranked) >= 1 else None
    second = ranked[1] if len(ranked) >= 2 else None
    third = ranked[2] if len(ranked) >= 3 else None

    # 単勝（オッズ2.0倍以上のみ）
    if top and top["score"] >= 50 and top.get("odds", 10.0) >= 2.0:
        amount = int(budget * 0.35 / 100) * 100
        result["単勝"] = {
            "買い目": f"{top['course']}号艇 {top['name']}",
            "金額": amount,
            "理由": f"スコア{top['score']}点。{top['course']}コース×{top['rank']}選手（オッズ{top['odds']}倍）",
        }

    # 2連複
    if top and second:
        amount = int(budget * 0.25 / 100) * 100
        nums = sorted([top["course"], second["course"]])
        result["2連複"] = {
            "買い目": f"{nums[0]}-{nums[1]}",
            "金額": amount,
            "理由": "スコア上位2艇の組み合わせ",
        }

    # 1号艇との2連複（1位が1号艇でなく、2位も1号艇でない場合のみ追加）
    if top and top["course"] != 1 and (not second or second["course"] != 1):
        boat1 = next((r for r in ranked if r["course"] == 1), None)
        if boat1:
            amount = int(budget * 0.15 / 100) * 100
            nums = sorted([top["course"], 1])
            result["2連複（1号艇保険）"] = {
                "買い目": f"{nums[0]}-{nums[1]}",
                "金額": amount,
                "理由": f"1コースは2着率が高いため{top['name']}×1号艇を保険で押さえる",
            }

    # 2連単（両方向）
    if top and second:
        unit = max(100, int(budget * 0.10 / 100) * 100)
        result["2連単（正）"] = {
            "買い目": f"{top['course']}→{second['course']}",
            "金額": unit,
            "理由": f"{top['name']}1着・{second['name']}2着を予想",
        }
        result["2連単（逆）"] = {
            "買い目": f"{second['course']}→{top['course']}",
            "金額": unit,
            "理由": f"{second['name']}1着・{top['name']}2着（逆順保険）",
        }

    # 3連複
    if top and second and third:
        amount = int(budget * 0.05 / 100) * 100
        if amount >= 100:
            nums = sorted([top["course"], second["course"], third["course"]])
            result["3連複"] = {
                "買い目": f"{nums[0]}-{nums[1]}-{nums[2]}",
                "金額": amount,
                "理由": "スコア上位3艇のボックス",
            }

    return result
