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

    # 複勝（2連複ベース）
    if top and second:
        amount = int(budget * 0.25 / 100) * 100
        nums = sorted([top["course"], second["course"]])
        result["2連複"] = {
            "買い目": f"{nums[0]}-{nums[1]}",
            "金額": amount,
            "理由": f"スコア上位2艇の組み合わせ",
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
        unit = max(100, int(budget * 0.15 / 2 / 100) * 100)
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
        amount = int(budget * 0.1 / 100) * 100
        nums = sorted([top["course"], second["course"], third["course"]])
        result["3連複"] = {
            "買い目": f"{nums[0]}-{nums[1]}-{nums[2]}",
            "金額": amount,
            "理由": "スコア上位3艇のボックス",
        }

    # 3連単（1着固定マルチ）
    if top and len(ranked) >= 3:
        from itertools import permutations
        others = [r for r in ranked[1:4] if r["course"] != top["course"]]
        combos = list(permutations(others, 2))
        unit = max(100, int(budget * 0.12 / max(len(combos), 1) / 100) * 100)
        for i, (a, b) in enumerate(combos):
            result[f"3連単M{i + 1}"] = {
                "買い目": f"{top['course']}→{a['course']}→{b['course']}",
                "金額": unit,
                "理由": f"1着{top['name']}固定、2着{a['name']}・3着{b['name']}",
            }

    # 穴艇込み3連複（複数パターン）
    if anaba and top and second:
        amount = int(budget * 0.05 / 100) * 100
        bought = set()
        count = 0
        for ana in anaba:
            for base_a, base_b in [(top, second), (top, third), (second, third)]:
                if base_a is None or base_b is None:
                    continue
                nums_set = tuple(sorted({base_a["course"], base_b["course"], ana["course"]}))
                if len(nums_set) == 3 and nums_set not in bought:
                    bought.add(nums_set)
                    nums_str = "-".join(str(n) for n in nums_set)
                    key = "3連複（穴艇込み）" if count == 0 else f"3連複（穴艇込み）{count + 1}"
                    result[key] = {
                        "買い目": f"{nums_str}（穴：{ana['course']}号艇 {ana['name']}）",
                        "金額": amount,
                        "理由": f"{ana['name']}（{ana['course']}コース・{ana['rank']}）を穴艇として組み込む",
                    }
                    count += 1
                    if count >= 1:
                        break
            if count >= 1:
                break

    # 予算超過時に3連単マルチを末尾から削除して調整
    total = sum(v["金額"] for v in result.values())
    if total > budget:
        for key in sorted([k for k in result if "3連単M" in k], reverse=True):
            if sum(v["金額"] for v in result.values()) <= budget:
                break
            result.pop(key)

    return result
