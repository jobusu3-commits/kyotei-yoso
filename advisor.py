def advise(ranked: list[dict], budget: int, anaba: list[dict] = None) -> dict:
    result = {}
    top = ranked[0] if len(ranked) >= 1 else None
    second = ranked[1] if len(ranked) >= 2 else None
    third = ranked[2] if len(ranked) >= 3 else None

    # 単勝
    if top and top["score"] >= 50:
        amount = int(budget * 0.35 / 100) * 100
        result["単勝"] = {
            "買い目": f"{top['course']}号艇 {top['name']}",
            "金額": amount,
            "理由": f"スコア{top['score']}点。{top['course']}コース×{top['rank']}選手",
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

    # 1号艇との2連複（予想1位が1号艇でない場合に追加）
    if top and top["course"] != 1:
        boat1 = next((r for r in ranked if r["course"] == 1), None)
        if boat1:
            amount = int(budget * 0.15 / 100) * 100
            nums = sorted([top["course"], 1])
            result["2連複（1号艇保険）"] = {
                "買い目": f"{nums[0]}-{nums[1]}",
                "金額": amount,
                "理由": f"1コースは2着率が高いため{top['name']}×1号艇を保険で押さえる",
            }

    # 2連単
    if top and second:
        amount = int(budget * 0.15 / 100) * 100
        result["2連単"] = {
            "買い目": f"{top['course']}→{second['course']}",
            "金額": amount,
            "理由": f"{top['name']}1着・{second['name']}2着を予想",
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

    # 3連単
    if top and second and third:
        amount = int(budget * 0.1 / 100) * 100
        result["3連単"] = {
            "買い目": f"{top['course']}→{second['course']}→{third['course']}",
            "金額": amount,
            "理由": "スコア順に1・2・3着を予想（高配当狙い）",
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
                    if count >= 3:
                        break
            if count >= 3:
                break

    return result
