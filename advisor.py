def should_skip(ranked: list[dict], jcd: str = "", wave: int = 0, wind_speed: int = 0) -> dict | None:
    """見送り推奨条件をチェック。見送り時はreason dictを、予想OKならNoneを返す"""
    if not ranked:
        return {"reason": "データなし"}
    # 全選手がデフォルト値 → スクレイピング失敗
    if all(r["win_rate"] == 5.0 and r["nirenritsu"] == 35.0 for r in ranked):
        return {"reason": "選手データを取得できませんでした。出走表URLを確認して再実行してください。"}
    # 江戸川の荒水面は外コースのまくり・差しが多発するため見送り
    if jcd == "03" and (wave >= 15 or wind_speed >= 8):
        return {"reason": f"江戸川の荒水面（波高{wave}cm・風速{wind_speed}m）は外コース展開が読めません。このレースは見送りを推奨します。"}
    top = ranked[0]
    # 江戸川は穏やか水面でもまくりが多発するため、本命スコア80点未満は見送り
    if jcd == "03" and top["score"] < 80:
        return {"reason": f"江戸川は本命スコアが{top['score']}点（基準80点）では的中率が低い傾向があります。このレースは見送りを推奨します。"}
    if top["score"] < 60:
        return {"reason": f"本命スコアが低すぎます（{top['score']}点 / 基準60点）。混戦の可能性が高く、このレースは見送りを推奨します。"}
    if len(ranked) >= 2:
        gap = top["score"] - ranked[1]["score"]
        # 1位スコアが68点以上なら高確率本命とみなし、差が小さくても見送らない
        if gap < 8 and top["score"] < 68:
            return {"reason": f"1位と2位のスコア差が小さすぎます（差{gap}点 / 基準8点）。本命が絞れないため、このレースは見送りを推奨します。"}
    return None


def advise(ranked: list[dict], budget: int, anaba: list[dict] = None) -> dict:
    result = {}
    top = ranked[0] if len(ranked) >= 1 else None
    second = ranked[1] if len(ranked) >= 2 else None
    third = ranked[2] if len(ranked) >= 3 else None

    # 単勝（1号艇スコア75点以上は1.5倍以上、それ以外は2.0倍以上）
    if top and top["score"] >= 50:
        odds_threshold = 1.5 if (top["course"] == 1 and top["score"] >= 75) else 2.0
        if top.get("odds", 10.0) >= odds_threshold:
            amount = int(budget * 0.35 / 100) * 100
            result["単勝"] = {
                "買い目": f"{top['course']}号艇 {top['name']}",
                "金額": amount,
                "理由": f"スコア{top['score']}点。{top['course']}コース×{top['rank']}選手（オッズ{top['odds']}倍）",
            }

    # 2連複（1号艇スコア70点以上が本命のとき2位・3位に分散）
    if top and second:
        if top["course"] == 1 and top["score"] >= 70 and third:
            amount_main = int(budget * 0.15 / 100) * 100
            amount_sub = int(budget * 0.10 / 100) * 100
            nums1 = sorted([top["course"], second["course"]])
            nums2 = sorted([top["course"], third["course"]])
            result["2連複"] = {
                "買い目": f"{nums1[0]}-{nums1[1]}",
                "金額": amount_main,
                "理由": "1号艇本命軸・2位との組み合わせ",
            }
            result["2連複（3位分散）"] = {
                "買い目": f"{nums2[0]}-{nums2[1]}",
                "金額": amount_sub,
                "理由": "1号艇本命軸・3位との組み合わせ（2位予想分散）",
            }
        else:
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
        # 2位のオッズが5倍未満のときのみ逆を買う（高オッズ穴は1着に来にくいため）
        if second.get("odds", 10.0) < 5.0:
            result["2連単（逆）"] = {
                "買い目": f"{second['course']}→{top['course']}",
                "金額": unit,
                "理由": f"{second['name']}1着・{top['name']}2着（逆順保険・オッズ{second.get('odds', 10.0)}倍）",
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
