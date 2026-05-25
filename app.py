import csv
import os
from datetime import date
import streamlit as st
from scraper import fetch_race_data
from scorer import rank_racers, find_anaba
from advisor import advise, should_skip

RESULTS_LOG = os.path.join(os.path.dirname(__file__), "results_log.csv")
BOAT_COLORS = {1: "🟥", 2: "⬜", 3: "🟦", 4: "🟨", 5: "⬛", 6: "🟩"}

st.set_page_config(page_title="競艇予想ツール", page_icon="🚤", layout="wide")

with st.sidebar:
    st.header("🚤 競艇予想ツール")
    st.divider()
    url = st.text_input(
        "出走表URL",
        placeholder="https://www.boatrace.jp/owpc/pc/race/racelist?rno=1&jcd=01&hd=20260511",
    )
    budget = st.number_input("予算（円）", min_value=1000, max_value=100000, value=3000, step=500)
    run = st.button("予想する", type="primary", use_container_width=True)
    st.divider()
    st.caption("boatrace.jp の出走表URLを貼り付けて「予想する」を押してください。")

tab_yoso, tab_log = st.tabs(["🔮 予想", "📊 結果ログ"])

with tab_yoso:
    if not run:
        st.markdown("## ようこそ")
        st.info("サイドバーに出走表のURLと予算を入力し、「予想する」を押してください。")
        with st.expander("📊 コース別全国平均勝率（参考）"):
            st.markdown("""
| コース | 全国平均勝率 |
|---|---|
| 1コース | 約55% |
| 2コース | 約17% |
| 3コース | 約12% |
| 4コース | 約8% |
| 5コース | 約5% |
| 6コース | 約3% |
""")
        st.stop()

    if run and not url:
        st.warning("URLを入力してください。")
        st.stop()

    with st.spinner("データ取得中..."):
        try:
            racers, race_info = fetch_race_data(url)
        except ValueError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"データ取得エラー: {e}")
            st.stop()

    weather = race_info.get("weather", {})
    wave = weather.get("wave", 0)
    wind_speed = weather.get("wind_speed", 0)
    jcd = race_info.get("jcd", "")

    ranked = rank_racers(racers, jcd, wave, wind_speed)
    anaba = find_anaba(ranked)
    skip_info = should_skip(ranked, jcd, wave, wind_speed)
    advice = advise(ranked, budget, anaba)

    # ── レース情報ヘッダー ──────────────────────────────────────────
    st.subheader(f"📍 {race_info['venue']} {race_info['rno']}R　{race_info['date']}")

    if skip_info:
        st.warning(f"⚠️ **見送り推奨:** {skip_info['reason']}")

    if weather.get("weather") != "不明":
        wcols = st.columns(4)
        wcols[0].metric("天候", weather.get("weather", "不明"))
        wcols[1].metric("風速", f"{wind_speed}m")
        wcols[2].metric("波高", f"{wave}cm")
        wcols[3].metric("風向", weather.get("wind_dir", "-") or "-")
        if wind_speed >= 5:
            st.caption("⚠️ 風速5m以上は直前に変化する場合があります。レース前に再実行を推奨します。")

    st.divider()

    # ── 2カラムレイアウト ───────────────────────────────────────────
    col_rank, col_bet = st.columns([6, 4], gap="large")

    with col_rank:
        st.markdown("### 🏆 予想ランキング")
        cols = st.columns([1, 2, 1, 1, 1, 1, 1, 1, 1])
        for col, h in zip(cols, ["順位", "選手名", "艇番", "階級", "スコア", "全国勝率", "2連率", "モーター2連率", "単勝オッズ"]):
            col.markdown(f"**{h}**")

        for i, r in enumerate(ranked):
            cols = st.columns([1, 2, 1, 1, 1, 1, 1, 1, 1])
            cols[0].write(f"{i+1}位")
            cols[1].write(f"{BOAT_COLORS.get(r['course'], '')} {r['name']}")
            cols[2].write(str(r["course"]))
            cols[3].write(r["rank"])
            cols[4].write(f"**{r['score']}**")
            cols[5].write(f"{r['win_rate']:.2f}")
            cols[6].write(f"{r['nirenritsu']:.1f}%")
            cols[7].write(f"{r['motor_nirenritsu']:.1f}%")
            odds = r.get("odds", 0)
            cols[8].write(f"{odds:.1f}倍" if odds > 0 else "-")

        with st.expander("📊 コース別全国平均勝率（参考）"):
            st.markdown("""
| コース | 全国平均勝率 |
|---|---|
| 1コース | 約55% |
| 2コース | 約17% |
| 3コース | 約12% |
| 4コース | 約8% |
| 5コース | 約5% |
| 6コース | 約3% |
""")

    with col_bet:
        st.markdown("### 💰 買い目提案")
        total = 0
        for bet_type, info in advice.items():
            with st.container(border=True):
                b1, b2 = st.columns([1, 1])
                b1.markdown(f"**{bet_type}**")
                b2.markdown(f"`{info['買い目']}`　**{info['金額']}円**")
                st.caption(info["理由"])
            total += info["金額"]
        st.markdown(f"**合計：{total}円 / 予算：{budget}円**")

        if anaba:
            st.markdown("### 💥 穴艇候補")
            for a in anaba:
                st.info(
                    f"{BOAT_COLORS.get(a['course'], '')} **{a['course']}号艇 {a['name']}**（{a['rank']}）\n\n"
                    f"2連率 {a['nirenritsu']:.1f}%　モーター {a['motor_nirenritsu']:.1f}%"
                )

    st.divider()

    # ── 結果記録 ────────────────────────────────────────────────────
    with st.expander("📝 結果を記録する"):
        st.caption("レース終了後に実際の着順を入力してください")
        with st.form("log_form"):
            log_cols = st.columns(6)
            actual = {}
            for i, r in enumerate(sorted(racers, key=lambda x: x["course"])):
                actual[r["course"]] = log_cols[i].number_input(
                    f"{BOAT_COLORS.get(r['course'], '')}{r['course']}号艇",
                    min_value=1, max_value=6, value=i+1, key=f"place_{r['course']}"
                )
            submitted = st.form_submit_button("記録する", use_container_width=True)
            if submitted:
                file_exists = os.path.exists(RESULTS_LOG)
                with open(RESULTS_LOG, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["date", "venue", "race", "course", "name", "rank", "tool_rank", "score", "odds", "actual_place"])
                    for i, r in enumerate(ranked):
                        writer.writerow([
                            race_info["date"],
                            race_info["venue"],
                            race_info["rno"],
                            r["course"],
                            r["name"],
                            r["rank"],
                            i + 1,
                            r["score"],
                            r.get("odds", 0),
                            actual.get(r["course"], 0),
                        ])
                st.success("記録しました！")

with tab_log:
    st.markdown("### 📊 過去の予想結果")
    if os.path.exists(RESULTS_LOG):
        import pandas as pd
        df = pd.read_csv(RESULTS_LOG)
        if not df.empty:
            top1 = df[df["tool_rank"] == 1]
            hit = (top1["actual_place"] == 1).sum()
            total_r = len(top1)
            if total_r > 0:
                mcols = st.columns(3)
                mcols[0].metric("予想レース数", total_r)
                mcols[1].metric("1位的中数", hit)
                mcols[2].metric("的中率", f"{hit/total_r*100:.1f}%")
            st.dataframe(df, use_container_width=True)
    else:
        st.info("まだ記録がありません。予想後に結果を入力してください。")
