import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import re
from datetime import datetime, timedelta

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
st.set_page_config(page_title="KBO 팀 대시보드", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOGO_DIR = os.path.join(DATA_DIR, "ai 구단 로고")

# 팀 이름 → 팀 코드 (gameId 기반)
TEAM_CODE = {
    "KIA": "HT", "KT": "KT", "한화": "HH", "LG": "LG",
    "두산": "OB", "NC": "NC", "삼성": "SS", "SSG": "SK",
    "키움": "WO", "롯데": "LT",
}
# 팀 코드 → 팀 이름
CODE_TEAM = {v: k for k, v in TEAM_CODE.items()}

TEAMS = ["KIA", "KT", "LG", "NC", "SSG", "두산", "롯데", "삼성", "키움", "한화"]

TEAM_COLOR = {
    "KIA":  "#ea0029", "KT":   "#231f20", "LG":   "#c30452",
    "NC":   "#071d49", "SSG":  "#ce0e2d", "두산":  "#131230",
    "롯데":  "#002469", "삼성":  "#074ca1", "키움":  "#820024",
    "한화":  "#ff6600",
}

LOGO_FILE = {
    "KIA": "KIA.png", "KT": "KT.png", "LG": "LG.png",
    "NC": "NC.png",   "SSG": "SSG.png", "두산": "두산.png",
    "롯데": "롯데.png",  "삼성": "삼성.png", "키움": "키움.png",
    "한화": "한화.png",
}

POSITION_MAP = {
    "중견수": "CF", "1루수": "1B", "우익수": "RF", "좌익수": "LF",
    "3루수": "3B", "지명타자": "DH", "포수": "C", "유격수": "SS", "2루수": "2B",
}
POSITIONS = ["1B", "2B", "3B", "C", "SS", "LF", "CF", "RF", "DH"]
POS_LABEL = {v: k for k, v in POSITION_MAP.items()}

# ─────────────────────────────────────────
# 데이터 로드 (캐시)
# ─────────────────────────────────────────
@st.cache_data
def load_data():
    d = {}
    d["match_elo"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_match_elo_current.csv"))
    d["match_record"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_match_record_current.csv"))
    d["batter_record"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_batter_record_current.csv"))
    d["pitcher_record"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_pitcher_record_current.csv"))
    d["player_batter_result"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_player_batter_result_current.csv"))
    d["player_pitcher_result"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_player_pitcher_result_current.csv"))
    d["team_batter_result"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_team_batter_result_current.csv"))
    d["team_pitcher_result"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_team_pitcher_result_current.csv"))
    d["player_batter_id"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_player_batter_id_current.csv"))
    d["player_pitcher_id"] = pd.read_csv(os.path.join(DATA_DIR, "KBO_player_pitcher_id_current.csv"))
    with open(os.path.join(DATA_DIR, "team_info_rows.json"), encoding="utf-8") as f:
        d["team_info"] = json.load(f)
    # parse dates
    d["match_elo"]["date"] = pd.to_datetime(d["match_elo"]["date"])
    d["match_record"]["Date"] = pd.to_datetime(d["match_record"]["Date"], format="%Y.%m.%d")
    d["batter_record"]["날짜"] = pd.to_datetime(d["batter_record"]["날짜"])
    d["pitcher_record"]["날짜"] = pd.to_datetime(d["pitcher_record"]["날짜"])
    d["player_batter_result"]["날짜"] = pd.to_datetime(d["player_batter_result"]["날짜"])
    d["player_pitcher_result"]["날짜"] = pd.to_datetime(d["player_pitcher_result"]["날짜"])
    d["team_batter_result"]["날짜"] = pd.to_datetime(d["team_batter_result"]["날짜"])
    d["team_pitcher_result"]["날짜"] = pd.to_datetime(d["team_pitcher_result"]["날짜"])
    return d


def get_team_info(data, team):
    """팀 기본 정보 (team_info_rows.json)"""
    name_map = {
        "KIA": "KIA 타이거즈", "KT": "KT 위즈", "LG": "LG 트윈스",
        "NC": "NC 다이노스", "SSG": "SSG 랜더스", "두산": "두산 베어스",
        "롯데": "롯데 자이언츠", "삼성": "삼성 라이온즈", "키움": "키움 히어로즈",
        "한화": "한화 이글스",
    }
    full = name_map.get(team, team)
    for row in data["team_info"]:
        if row.get("fullName") == full:
            return row
    return {}


def calc_standings(match_elo):
    """승무패 집계 및 순위 계산"""
    records = {t: {"W": 0, "L": 0, "D": 0} for t in TEAMS}
    completed = match_elo.dropna(subset=["Away_R", "Home_R"])
    for _, row in completed.iterrows():
        a, h = row["Away"], row["Home"]
        ar, hr = row["Away_R"], row["Home_R"]
        if a not in records or h not in records:
            continue
        if ar > hr:
            records[a]["W"] += 1; records[h]["L"] += 1
        elif hr > ar:
            records[h]["W"] += 1; records[a]["L"] += 1
        else:
            records[a]["D"] += 1; records[h]["D"] += 1
    rows = []
    for t, r in records.items():
        g = r["W"] + r["L"] + r["D"]
        wp = r["W"] / (r["W"] + r["L"]) if (r["W"] + r["L"]) > 0 else 0
        rows.append({"팀": t, "G": g, "W": r["W"], "L": r["L"], "D": r["D"], "WP": wp})
    df = pd.DataFrame(rows).sort_values("WP", ascending=False)
    # 공동순위
    df["순위"] = df["WP"].rank(method="min", ascending=False).astype(int)
    return df.reset_index(drop=True)


def get_elo(match_elo, team):
    """팀의 최신 ELO"""
    away = match_elo[match_elo["Away"] == team].dropna(subset=["elo_post_away"])
    home = match_elo[match_elo["Home"] == team].dropna(subset=["elo_post_home"])
    if away.empty and home.empty:
        return 1500.0
    candidates = []
    if not away.empty:
        row = away.sort_values("date").iloc[-1]
        candidates.append((row["date"], row["elo_post_away"]))
    if not home.empty:
        row = home.sort_values("date").iloc[-1]
        candidates.append((row["date"], row["elo_post_home"]))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return round(candidates[0][1], 1)


def get_team_games(match_elo, team):
    """팀 경기 목록 (완료된 경기)"""
    completed = match_elo.dropna(subset=["Away_R", "Home_R"])
    away = completed[completed["Away"] == team][["date", "gameId", "Away", "Away_R", "Home_R", "Home", "Stadium"]].copy()
    away["is_home"] = False; away["opponent"] = away["Home"]; away["team_r"] = away["Away_R"]; away["opp_r"] = away["Home_R"]
    home = completed[completed["Home"] == team][["date", "gameId", "Away", "Away_R", "Home_R", "Home", "Stadium"]].copy()
    home["is_home"] = True; home["opponent"] = home["Away"]; home["team_r"] = home["Home_R"]; home["opp_r"] = home["Away_R"]
    games = pd.concat([away, home]).sort_values("date").reset_index(drop=True)
    games["result"] = games.apply(lambda r: "W" if r["team_r"] > r["opp_r"] else ("L" if r["team_r"] < r["opp_r"] else "D"), axis=1)
    return games


# ─────────────────────────────────────────
# UI 헬퍼
# ─────────────────────────────────────────
def result_badge(r):
    if r == "W":
        return '<span style="background:#1a7f37;color:white;padding:2px 8px;border-radius:4px;font-weight:bold;">승</span>'
    elif r == "L":
        return '<span style="background:#cf222e;color:white;padding:2px 8px;border-radius:4px;font-weight:bold;">패</span>'
    else:
        return '<span style="background:#6e7781;color:white;padding:2px 8px;border-radius:4px;font-weight:bold;">무</span>'





# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
data = load_data()
match_elo = data["match_elo"]
match_record = data["match_record"]
batter_record = data["batter_record"]
pitcher_record = data["pitcher_record"]
player_batter_result = data["player_batter_result"]
player_pitcher_result = data["player_pitcher_result"]
team_batter_result = data["team_batter_result"]
team_pitcher_result = data["team_pitcher_result"]
player_batter_id = data["player_batter_id"]
player_pitcher_id = data["player_pitcher_id"]

# ─────── 팀 선택 (최상단) ───────
st.markdown("## ⚾ KBO 10개 구단 대시보드")
col_logo, col_sel = st.columns([1, 5])
with col_sel:
    selected_team = st.selectbox("팀 선택", TEAMS, index=0, label_visibility="collapsed")

team_color = TEAM_COLOR.get(selected_team, "#333333")
logo_path = os.path.join(LOGO_DIR, LOGO_FILE.get(selected_team, ""))
with col_logo:
    if os.path.exists(logo_path):
        st.image(logo_path, width=70)

# 팀 기본 통계
standings = calc_standings(match_elo)
team_games = get_team_games(match_elo, selected_team)
team_games_count = len(team_games)

st.markdown(f'<hr style="border-top:3px solid {team_color};">', unsafe_allow_html=True)

# ══════════════════════════════════════
# 상단 2열 레이아웃
# ══════════════════════════════════════
top_left, top_right = st.columns([3, 2])

# ─────────────────────────────────────────
# § 1  팀 기본 정보
# ─────────────────────────────────────────
with top_left:
    info = get_team_info(data, selected_team)
    st.markdown(f'<h3 style="color:{team_color}">{selected_team} 팀 정보</h3>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("창단연도", info.get("founded", "-"))
    c2.metric("홈구장", info.get("stadium", "-"))
    c3.metric("정규리그 우승", f'{info.get("regularWins","0")}회')
    c4.metric("한국시리즈 우승", f'{info.get("championWins","0")}회')

    # § 2  팀 순위 & ELO
    st.markdown("---")
    st.markdown("#### 📊 팀 순위 & ELO Rating")
    t_row = standings[standings["팀"] == selected_team]
    rank = t_row["순위"].values[0] if not t_row.empty else "-"
    elo = get_elo(match_elo, selected_team)
    r = t_row.iloc[0] if not t_row.empty else {}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("순위", f'{rank}위')
    c2.metric("ELO Rating", f"{elo:.0f}")
    if not t_row.empty:
        c3.metric("경기", int(r["G"]))
        c4.metric("승/패/무", f'{int(r["W"])}-{int(r["L"])}-{int(r["D"])}')
        c5.metric("승률", f'{r["WP"]:.3f}')

# ─────────────────────────────────────────
# § 3  팀 주요 지표
# ─────────────────────────────────────────
with top_right:
    st.markdown(f'<h3 style="color:{team_color}">팀 주요 지표</h3>', unsafe_allow_html=True)
    last_bat = team_batter_result[team_batter_result["팀"] == selected_team].sort_values("날짜").iloc[-1] if not team_batter_result[team_batter_result["팀"] == selected_team].empty else None
    last_pit = team_pitcher_result[team_pitcher_result["팀"] == selected_team].sort_values("날짜").iloc[-1] if not team_pitcher_result[team_pitcher_result["팀"] == selected_team].empty else None
    c1, c2, c3 = st.columns(3)
    c1.metric("팀 타율", f'{last_bat["타율"]:.3f}' if last_bat is not None else "-")
    c2.metric("팀 OPS", f'{last_bat["OPS"]:.3f}' if last_bat is not None else "-")
    c3.metric("팀 ERA", f'{last_pit["ERA"]:.2f}' if last_pit is not None else "-")

    # § 13  오늘/다음 경기
    st.markdown("---")
    st.markdown("#### 📅 다음 경기")
    completed_mr = match_record.dropna(subset=["Away_R", "Home_R"])
    last_done_date = completed_mr["Date"].max()
    upcoming = match_record[
        (match_record["Date"] > last_done_date) &
        ((match_record["Away"] == selected_team) | (match_record["Home"] == selected_team))
    ].sort_values("Date")
    if not upcoming.empty:
        nxt = upcoming.iloc[0]
        is_home = nxt["Home"] == selected_team
        opp = nxt["Away"] if is_home else nxt["Home"]
        loc = "홈" if is_home else "원정"
        st.markdown(f"**{nxt['Date'].strftime('%m/%d')} {nxt.get('Time','TBD')}**")
        opp_logo = os.path.join(LOGO_DIR, LOGO_FILE.get(opp, ""))
        c1, c2 = st.columns([1, 3])
        with c1:
            if os.path.exists(opp_logo):
                st.image(opp_logo, width=50)
        with c2:
            st.markdown(f"**vs {opp}** ({loc})")
            st.markdown(f"🏟️ {nxt.get('Stadium', '-')}")
    else:
        st.info("예정 경기 없음")

st.markdown("---")

# ══════════════════════════════════════
# § 4  최근 일정 (3주 달력)
# ══════════════════════════════════════
st.markdown("### 📆 최근 일정 (3주)")

today = pd.Timestamp("2026-04-13")
# 이번주 월요일
this_monday = today - timedelta(days=today.weekday())
week_starts = [this_monday - timedelta(weeks=2), this_monday - timedelta(weeks=1), this_monday]
week_labels = ["2주전", "1주전", "이번주"]

# 완료 경기 (match_elo)
completed_games = match_elo.dropna(subset=["Away_R", "Home_R"])

# 예정 경기 (match_record - 점수 없는 것)
upcoming_games = match_record[match_record["Away_R"].isna()]

for w_idx, (w_start, w_label) in enumerate(zip(week_starts, week_labels)):
    w_end = w_start + timedelta(days=6)
    st.markdown(f"**{w_label} ({w_start.strftime('%m/%d')} ~ {w_end.strftime('%m/%d')})**")
    cols = st.columns(7)
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    for d_idx in range(7):
        day = w_start + timedelta(days=d_idx)
        with cols[d_idx]:
            st.markdown(f"<div style='text-align:center;font-size:11px;color:#888'>{day_names[d_idx]}<br>{day.strftime('%m/%d')}</div>", unsafe_allow_html=True)
            # 완료된 경기에서 해당 팀 찾기
            day_complete = completed_games[
                (completed_games["date"] == day) &
                ((completed_games["Away"] == selected_team) | (completed_games["Home"] == selected_team))
            ]
            day_upcoming = upcoming_games[
                (upcoming_games["Date"] == day) &
                ((upcoming_games["Away"] == selected_team) | (upcoming_games["Home"] == selected_team))
            ]
            if not day_complete.empty:
                row = day_complete.iloc[0]
                is_home = row["Home"] == selected_team
                opp = row["Away"] if is_home else row["Home"]
                team_r = row["Home_R"] if is_home else row["Away_R"]
                opp_r = row["Away_R"] if is_home else row["Home_R"]
                if team_r > opp_r:
                    color, txt = "#1a7f37", "승"
                elif team_r < opp_r:
                    color, txt = "#cf222e", "패"
                else:
                    color, txt = "#6e7781", "무"
                st.markdown(f'<div style="text-align:center;font-size:12px;"><b>{opp}</b><br><span style="background:{color};color:white;padding:1px 6px;border-radius:3px">{txt}</span><br><span style="font-size:10px">{int(team_r)}-{int(opp_r)}</span></div>', unsafe_allow_html=True)
            elif not day_upcoming.empty:
                row = day_upcoming.iloc[0]
                is_home = row["Home"] == selected_team
                opp = row["Away"] if is_home else row["Home"]
                loc = "🏠" if is_home else "✈"
                st.markdown(f'<div style="text-align:center;font-size:12px;">{loc}<b>{opp}</b></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="text-align:center;color:#ccc;font-size:12px;">-</div>', unsafe_allow_html=True)

st.markdown("---")

# ══════════════════════════════════════
# § 7 & § 8  최근 10경기 & 팀 컨디션
# ══════════════════════════════════════
col_r10, col_cond = st.columns([3, 2])

with col_r10:
    st.markdown("### 🔟 최근 10경기 성적")
    recent10 = team_games.tail(10)
    badges = " ".join([result_badge(r) for r in recent10["result"]])
    st.markdown(badges, unsafe_allow_html=True)
    w10 = (recent10["result"] == "W").sum()
    l10 = (recent10["result"] == "L").sum()
    d10 = (recent10["result"] == "D").sum()
    st.markdown(f"**{w10}승 {l10}패 {d10}무**")

with col_cond:
    st.markdown("### 💪 팀 컨디션")
    games10 = len(recent10)
    if games10 > 0:
        wp10 = w10 / games10
        cond_score = int(wp10 * 1.4 * 100)
        if cond_score >= 90:
            grade, gc = "PERFECT", "#6f42c1"
        elif cond_score >= 80:
            grade, gc = "GREAT", "#1a7f37"
        elif cond_score >= 70:
            grade, gc = "GOOD", "#0969da"
        elif cond_score >= 60:
            grade, gc = "SO SO", "#9a6700"
        elif cond_score >= 50:
            grade, gc = "BAD", "#cf222e"
        elif cond_score >= 40:
            grade, gc = "SO BAD", "#a40000"
        else:
            grade, gc = "TERRIBLE", "#6e0000"
        # 게이지 바
        st.markdown(f"""
        <div style="background:#f0f0f0;border-radius:8px;height:24px;width:100%">
            <div style="background:{gc};width:{min(cond_score,100)}%;height:24px;border-radius:8px;text-align:center;color:white;font-weight:bold;line-height:24px">{cond_score}%</div>
        </div>
        <div style="text-align:center;font-size:1.2em;font-weight:bold;color:{gc};margin-top:4px">{grade}</div>
        """, unsafe_allow_html=True)
    else:
        st.info("데이터 없음")

st.markdown("---")

# ══════════════════════════════════════
# § 5  라인업 (최근 / 시즌 탭)
# ══════════════════════════════════════
st.markdown("### 👥 라인업")
lu_tab1, lu_tab2 = st.tabs(["최근 라인업", "시즌 라인업"])

with lu_tab1:
    # 가장 최근 경기 날짜의 라인업
    team_bat = batter_record[batter_record["팀"] == selected_team].copy()
    if not team_bat.empty:
        last_game_date = team_bat["날짜"].max()
        last_game_bat = team_bat[team_bat["날짜"] == last_game_date]
        # 스타팅 포지션 추출: 포지션 컬럼에서 → 이전 부분만 사용
        def get_start_pos(pos_str):
            if not isinstance(pos_str, str):
                return str(pos_str)
            return pos_str.split("→")[0].strip()
        last_game_bat = last_game_bat.copy()
        last_game_bat["start_pos"] = last_game_bat["포지션"].apply(get_start_pos)
        # 각 타순의 첫 번째 선수(스타팅)만 추출
        valid_pos = set(POSITIONS)
        starters = last_game_bat[last_game_bat["start_pos"].isin(valid_pos)]
        # 타순별 첫 번째 선수
        lineup = starters.sort_values("타순").drop_duplicates(subset=["타순"], keep="first")
        # 포지션별 첫 번째 선수
        pos_lineup = lineup.drop_duplicates(subset=["start_pos"], keep="first")
        pos_dict = {row["start_pos"]: row["선수명"] for _, row in pos_lineup.iterrows()}
        st.markdown(f"**{last_game_date.strftime('%Y-%m-%d')} 경기 라인업**")
        cols = st.columns(9)
        for i, pos in enumerate(POSITIONS):
            with cols[i]:
                player = pos_dict.get(pos, "-")
                st.markdown(f'<div style="text-align:center;background:#f8f9fa;padding:8px;border-radius:6px;"><b style="color:{team_color}">{pos}</b><br>{player}</div>', unsafe_allow_html=True)
    else:
        st.info("라인업 데이터 없음")

with lu_tab2:
    # 시즌 라인업: 규정타석 기준 wRC+ 최고 선수
    st.markdown("**시즌 대표 라인업 (규정타석 기준 wRC+ 최고)**")
    # 팀 경기수
    t_games = team_games_count
    qual_pa = int(t_games * 3.1)
    # 선수 최신 성적 (마지막 날짜 기준)
    pb_team = player_batter_result[player_batter_result["팀"] == selected_team]
    if not pb_team.empty:
        pb_latest = pb_team.sort_values("날짜").groupby("선수명").last().reset_index()
    else:
        pb_latest = pd.DataFrame()
    # 포지션 정보 from player_batter_id
    pid_team = player_batter_id[player_batter_id["Team"] == selected_team].copy()
    pid_team["pos_code"] = pid_team["position"].map(POSITION_MAP)
    season_lineup = {}
    if not pb_latest.empty:
        thresholds = [1.0, 0.9, 0.8, 0.7]
        for pos in POSITIONS:
            pid_pos = pid_team[pid_team["pos_code"] == pos]
            if pid_pos.empty:
                season_lineup[pos] = {"name": "-", "wRC+": "-", "page_id": None}
                continue
            merged = pid_pos.merge(pb_latest[["선수명", "타석", "wRC+", "page_id"]], left_on="Batter", right_on="선수명", how="left")
            found = False
            for thr in thresholds:
                thr_pa = qual_pa * thr
                qual_players = merged[merged["타석"] >= thr_pa].copy()
                if not qual_players.empty:
                    best = qual_players.sort_values("wRC+", ascending=False).iloc[0]
                    season_lineup[pos] = {"name": best["Batter"], "wRC+": f'{best["wRC+"]:.1f}', "page_id": best.get("page_id_x") or best.get("page_id_y")}
                    found = True
                    break
            if not found:
                # 타석이 가장 많은 선수
                if not merged.empty and "타석" in merged.columns:
                    best = merged.sort_values("타석", ascending=False).dropna(subset=["선수명"]).head(1)
                    if not best.empty:
                        season_lineup[pos] = {"name": best.iloc[0]["Batter"], "wRC+": "-", "page_id": None}
                    else:
                        season_lineup[pos] = {"name": "-", "wRC+": "-", "page_id": None}
                else:
                    season_lineup[pos] = {"name": "-", "wRC+": "-", "page_id": None}
    else:
        for pos in POSITIONS:
            season_lineup[pos] = {"name": "-", "wRC+": "-", "page_id": None}
    cols = st.columns(9)
    for i, pos in enumerate(POSITIONS):
        with cols[i]:
            info_p = season_lineup[pos]
            st.markdown(f'<div style="text-align:center;background:#f8f9fa;padding:8px;border-radius:6px;"><b style="color:{team_color}">{pos}</b><br>{info_p["name"]}<br><small>wRC+: {info_p["wRC+"]}</small></div>', unsafe_allow_html=True)

st.markdown("---")

# ══════════════════════════════════════
# § 6  선발 로테이션
# ══════════════════════════════════════
st.markdown("### ⚾ 선발 로테이션")
rot_tab1, rot_tab2 = st.tabs(["최근 5경기", "시즌 TOP5"])

with rot_tab1:
    # match_elo에서 해당 팀의 최근 5경기 선발 찾기
    team_away = match_elo[match_elo["Away"] == selected_team][["date", "gameId", "Away", "Home", "Away_R", "Home_R", "away_starter"]].copy()
    team_away = team_away.rename(columns={"away_starter": "starter"})
    team_away["is_home"] = False
    team_home = match_elo[match_elo["Home"] == selected_team][["date", "gameId", "Away", "Home", "Away_R", "Home_R", "home_starter"]].copy()
    team_home = team_home.rename(columns={"home_starter": "starter"})
    team_home["is_home"] = True
    team_starts = pd.concat([team_away, team_home]).sort_values("date")
    completed_starts = team_starts.dropna(subset=["Away_R", "Home_R", "starter"])
    recent5 = completed_starts.tail(5)
    # 선수별 최신 성적 from player_pitcher_result
    pp_team = player_pitcher_result[player_pitcher_result["팀"] == selected_team]
    if not pp_team.empty:
        pp_latest = pp_team.sort_values("날짜").groupby("선수명").last().reset_index()
        pp_wins = pp_team[pp_team["결과"] == "승"].groupby("선수명").size().rename("wins")
        pp_losses = pp_team[pp_team["결과"] == "패"].groupby("선수명").size().rename("losses")
        pp_record = pd.concat([pp_wins, pp_losses], axis=1).fillna(0).reset_index()
        pp_latest = pp_latest.merge(pp_record, on="선수명", how="left")
    else:
        pp_latest = pd.DataFrame()
    cols = st.columns(5)
    for i, (_, row) in enumerate(recent5.iterrows()):
        with cols[i]:
            starter = row["starter"]
            is_home = row["is_home"]
            opp = row["Away"] if is_home else row["Home"]
            team_r = row["Home_R"] if is_home else row["Away_R"]
            opp_r = row["Away_R"] if is_home else row["Home_R"]
            result = "W" if team_r > opp_r else ("L" if team_r < opp_r else "D")
            era_val, ip_val, win_l, lose_l = "-", "-", 0, 0
            if not pp_latest.empty:
                p_row = pp_latest[pp_latest["선수명"] == starter]
                if not p_row.empty:
                    era_val = f'{p_row.iloc[0]["ERA"]:.2f}' if pd.notna(p_row.iloc[0]["ERA"]) else "-"
                    ip_val = f'{p_row.iloc[0]["IP"]:.1f}' if pd.notna(p_row.iloc[0]["IP"]) else "-"
                    win_l = int(p_row.iloc[0].get("wins", 0))
                    lose_l = int(p_row.iloc[0].get("losses", 0))
            badge = result_badge(result)
            st.markdown(f"""
            <div style="background:#f8f9fa;padding:8px;border-radius:6px;font-size:12px">
            <b style="color:{team_color}">{row['date'].strftime('%m/%d')}</b> vs {opp}<br>
            {badge}<br>
            <b>{starter}</b><br>
            승패: {win_l}승{lose_l}패<br>ERA: {era_val}<br>IP: {ip_val}
            </div>
            """, unsafe_allow_html=True)

with rot_tab2:
    st.markdown(f"**시즌 선발 TOP5** (경기수: {team_games_count}, 규정이닝: {team_games_count}IP 이상)")
    pp_team2 = player_pitcher_result[player_pitcher_result["팀"] == selected_team]
    if not pp_team2.empty:
        pp_lat2 = pp_team2.sort_values("날짜").groupby("선수명").last().reset_index()
        # 역할별 카운트
        role_cnt = pp_team2.groupby(["선수명", "역할"]).size().unstack(fill_value=0).reset_index()
        role_cnt.columns.name = None
        if "선발" not in role_cnt.columns:
            role_cnt["선발"] = 0
        if "중계" not in role_cnt.columns:
            role_cnt["중계"] = 0
        role_cnt["total"] = role_cnt["선발"] + role_cnt["중계"]
        role_cnt["G_all"] = pp_lat2.set_index("선수명")["G"].reindex(role_cnt["선수명"]).values
        role_cnt["start_pct"] = role_cnt["선발"] / role_cnt["G_all"].where(role_cnt["G_all"] > 0, 1)
        starters_season = role_cnt[role_cnt["start_pct"] >= 0.5]["선수명"].tolist()
        pp_starters = pp_lat2[pp_lat2["선수명"].isin(starters_season)].copy()
        qual_ip = team_games_count
        wins_s = pp_team2[pp_team2["결과"] == "승"].groupby("선수명").size().rename("wins")
        losses_s = pp_team2[pp_team2["결과"] == "패"].groupby("선수명").size().rename("losses")
        pp_starters = pp_starters.merge(wins_s, on="선수명", how="left").merge(losses_s, on="선수명", how="left")
        pp_starters["wins"] = pp_starters["wins"].fillna(0).astype(int)
        pp_starters["losses"] = pp_starters["losses"].fillna(0).astype(int)
        # 규정이닝 기준으로 TOP5 선발
        result_pitchers = []
        thresholds_p = [1.0, 0.9, 0.8, 0.7]
        needed = 5
        for thr in thresholds_p:
            thr_ip = qual_ip * thr
            q = pp_starters[pp_starters["IP"] >= thr_ip].sort_values("ERA")
            for _, row in q.iterrows():
                if row["선수명"] not in [x["선수명"] for x in result_pitchers]:
                    result_pitchers.append(row.to_dict())
                    if len(result_pitchers) >= needed:
                        break
            if len(result_pitchers) >= needed:
                break
        # 부족하면 나머지에서 ERA 순
        if len(result_pitchers) < needed:
            existing_names = [x["선수명"] for x in result_pitchers]
            extras = pp_starters[~pp_starters["선수명"].isin(existing_names)].sort_values("ERA")
            for _, row in extras.iterrows():
                result_pitchers.append(row.to_dict())
                if len(result_pitchers) >= needed:
                    break
        cols = st.columns(5)
        for i, p in enumerate(result_pitchers[:5]):
            with cols[i]:
                st.markdown(f"""
                <div style="background:#f8f9fa;padding:8px;border-radius:6px;font-size:12px">
                <b style="color:{team_color}">{p['선수명']}</b><br>
                승패: {p['wins']}승{p['losses']}패<br>
                ERA: {p.get('ERA','-'):.2f}<br>IP: {p.get('IP','-'):.1f}
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("데이터 없음")

st.markdown("---")

# ══════════════════════════════════════
# § 9  불펜 과부하 관리
# ══════════════════════════════════════
st.markdown("### 🔥 불펜 과부하 관리 (TOP 10)")

team_pr = pitcher_record[pitcher_record["팀"] == selected_team].copy()
team_pr["날짜"] = pd.to_datetime(team_pr["날짜"])
# 불펜 선수 (선발 아님)
# match_elo 기반 선발 목록 구분
starters_set = set()
for _, row in match_elo.dropna(subset=["Away_R", "Home_R"]).iterrows():
    if row["Away"] == selected_team and pd.notna(row["away_starter"]):
        starters_set.add(row["away_starter"])
    if row["Home"] == selected_team and pd.notna(row["home_starter"]):
        starters_set.add(row["home_starter"])

bullpen_pr = team_pr.copy()  # 혹사지수는 모두 계산 (선발 포함 가능)

def calc_overload(player_df):
    """혹사지수 계산"""
    df = player_df.sort_values("날짜").reset_index(drop=True)
    total = 0.0
    prev_date = None
    prev_date_list = []
    for _, row in df.iterrows():
        pitches = row.get("투구수", 0) or 0
        cur_date = row["날짜"]
        # 더블헤더 감지: 같은 날짜 2번 등판
        same_day_count = sum(1 for d in prev_date_list if d == cur_date)
        if same_day_count >= 1:
            mult = 5.0
        elif prev_date is not None:
            rest = (cur_date - prev_date).days - 1
            if rest <= 0:  # 연투: 이전에도 연투였으면 3연투(×5), 아니면 2연투(×4)
                if len(prev_date_list) >= 2 and (prev_date - prev_date_list[-2]).days <= 1:
                    mult = 5.0  # 3연투
                else:
                    mult = 4.0  # 2연투
            elif rest == 1:
                mult = 3.0
            elif rest == 2:
                mult = 2.0
            elif rest == 3:
                mult = 1.5
            else:
                mult = 1.0
        else:
            mult = 1.0
        total += pitches * mult
        prev_date_list.append(cur_date)
        prev_date = cur_date
    return round(total, 1)

if not bullpen_pr.empty:
    overload_data = []
    for player, grp in bullpen_pr.groupby("선수명"):
        ol = calc_overload(grp)
        overload_data.append({"선수명": player, "혹사지수": ol})
    overload_df = pd.DataFrame(overload_data).sort_values("혹사지수", ascending=False).head(10)
    # 성적 연계
    pp_team3 = player_pitcher_result[player_pitcher_result["팀"] == selected_team]
    if not pp_team3.empty:
        pp_lat3 = pp_team3.sort_values("날짜").groupby("선수명").last().reset_index()
        hold_cnt = pp_team3[pp_team3["결과"] == "홀드"].groupby("선수명").size().rename("홀드")
        save_cnt = pp_team3[pp_team3["결과"] == "세"].groupby("선수명").size().rename("세")
        pp_lat3 = pp_lat3.merge(hold_cnt, on="선수명", how="left").merge(save_cnt, on="선수명", how="left")
        pp_lat3["홀드"] = pp_lat3["홀드"].fillna(0).astype(int)
        pp_lat3["세"] = pp_lat3["세"].fillna(0).astype(int)
        overload_df = overload_df.merge(pp_lat3[["선수명", "IP", "ERA", "홀드", "세", "page_id"]], on="선수명", how="left")
    disp_cols = ["선수명", "혹사지수", "IP", "ERA", "홀드", "세"]
    disp_df = overload_df[[c for c in disp_cols if c in overload_df.columns]].rename(columns={"혹사지수": "혹사지수"})
    st.dataframe(disp_df, use_container_width=True, hide_index=True)
else:
    st.info("데이터 없음")

st.markdown("---")

# ══════════════════════════════════════
# § 10  시즌 퍼포먼스 순위
# ══════════════════════════════════════
st.markdown("### 🏆 시즌 퍼포먼스 순위")
perf_tab1, perf_tab2 = st.tabs(["타자 TOP10", "투수 TOP10"])

with perf_tab1:
    # 규정 70% 기준
    pb_all = player_batter_result.copy()
    if not pb_all.empty:
        pb_all_lat = pb_all.sort_values("날짜").groupby(["팀", "선수명"]).last().reset_index()
        # 각 팀별 경기수 계산
        team_game_counts = {t: len(get_team_games(match_elo, t)) for t in TEAMS}
        def get_qual_pa(team):
            return int(team_game_counts.get(team, 0) * 3.1 * 0.7)
        pb_all_lat["qual_pa"] = pb_all_lat["팀"].map(lambda t: get_qual_pa(t))
        qual_batters = pb_all_lat[pb_all_lat["타석"] >= pb_all_lat["qual_pa"]].copy()
        top10_bat = qual_batters.sort_values("OPS", ascending=False).head(10)
        display_bat = top10_bat[["팀", "선수명", "타석", "타율", "OPS", "wRC+"]].copy()
        display_bat["타율"] = display_bat["타율"].apply(lambda x: f"{x:.3f}")
        display_bat["OPS"] = display_bat["OPS"].apply(lambda x: f"{x:.3f}")
        display_bat["wRC+"] = display_bat["wRC+"].apply(lambda x: f"{x:.1f}")
        st.dataframe(display_bat, use_container_width=True, hide_index=True)
    else:
        st.info("데이터 없음")

with perf_tab2:
    # 규정 30%, 선발 4명 + 불펜 6명
    pp_all = player_pitcher_result.copy()
    if not pp_all.empty:
        pp_all_lat = pp_all.sort_values("날짜").groupby(["팀", "선수명"]).last().reset_index()
        # 역할 판별
        role_all = pp_all.groupby(["팀", "선수명", "역할"]).size().unstack(fill_value=0).reset_index()
        role_all.columns.name = None
        if "선발" not in role_all.columns: role_all["선발"] = 0
        if "중계" not in role_all.columns: role_all["중계"] = 0
        role_all["G_t"] = role_all["선발"] + role_all["중계"]
        role_all["start_pct_all"] = role_all["선발"] / role_all["G_t"].where(role_all["G_t"] > 0, 1)
        pp_all_lat = pp_all_lat.merge(role_all[["팀", "선수명", "start_pct_all"]], on=["팀", "선수명"], how="left")
        def get_qual_ip(team):
            return team_game_counts.get(team, 0) * 0.3
        pp_all_lat["qual_ip"] = pp_all_lat["팀"].map(lambda t: get_qual_ip(t))
        qual_pitchers = pp_all_lat[pp_all_lat["IP"] >= pp_all_lat["qual_ip"]].copy()
        # 선발 TOP4
        starters_all = qual_pitchers[qual_pitchers["start_pct_all"] >= 0.5].sort_values("ERA").head(4)
        # 불펜 TOP6
        bullpen_all = qual_pitchers[qual_pitchers["start_pct_all"] < 0.5].sort_values("ERA").head(6)
        combined = pd.concat([starters_all, bullpen_all])
        combined["역할"] = combined["start_pct_all"].apply(lambda x: "선발" if x >= 0.5 else "불펜")
        disp_pit = combined[["역할", "팀", "선수명", "G", "IP", "ERA", "K/9"]].copy()
        disp_pit["ERA"] = disp_pit["ERA"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")
        disp_pit["K/9"] = disp_pit["K/9"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")
        st.dataframe(disp_pit, use_container_width=True, hide_index=True)
    else:
        st.info("데이터 없음")

st.markdown("---")

# ══════════════════════════════════════
# § 11  경계할 타자 / 투수
# ══════════════════════════════════════
st.markdown("### ⚠️ 경계할 타자 / 투수")
watch_tab1, watch_tab2 = st.tabs(["경계할 타자", "경계할 투수"])

# 우리팀 gameId 목록
team_code = TEAM_CODE.get(selected_team, "")
team_game_ids = set()
for _, row in match_elo.dropna(subset=["Away_R", "Home_R"]).iterrows():
    if row["Away"] == selected_team or row["Home"] == selected_team:
        team_game_ids.add(row["gameId"])

with watch_tab1:
    # 우리팀과 대전한 상대 타자 성적 집계
    opp_bat = batter_record[
        (batter_record["gameId"].isin(team_game_ids)) &
        (batter_record["팀"] != selected_team)
    ].copy()
    min_pa = int(team_games_count * 3.1 * 0.05)
    st.markdown(f"*최소 타석: {min_pa}*")
    if not opp_bat.empty:
        opp_bat_agg = opp_bat.groupby(["팀", "선수명", "page_id"]).agg(
            타석=("타석", "sum"), 타수=("타수", "sum"), 안타=("안타", "sum"),
            홈런=("홈런", "sum"), 볼넷=("볼넷", "sum"), 사구=("사구", "sum"), 희비=("희생플라이", "sum")
        ).reset_index()
        opp_bat_agg = opp_bat_agg[opp_bat_agg["타석"] >= min_pa].copy()
        opp_bat_agg["타율"] = (opp_bat_agg["안타"] / opp_bat_agg["타수"].where(opp_bat_agg["타수"] > 0, 1)).round(3)
        opp_bat_agg["출루율"] = ((opp_bat_agg["안타"] + opp_bat_agg["볼넷"] + opp_bat_agg["사구"]) /
                                 (opp_bat_agg["타수"] + opp_bat_agg["볼넷"] + opp_bat_agg["사구"] + opp_bat_agg["희비"]).where(
                                     (opp_bat_agg["타수"] + opp_bat_agg["볼넷"] + opp_bat_agg["사구"] + opp_bat_agg["희비"]) > 0, 1)).round(3)
        opp_bat_agg["장타율"] = ((opp_bat_agg["안타"] + opp_bat_agg["홈런"]) / opp_bat_agg["타수"].where(opp_bat_agg["타수"] > 0, 1)).round(3)
        opp_bat_agg["OPS"] = (opp_bat_agg["출루율"] + opp_bat_agg["장타율"]).round(3)
        top5 = opp_bat_agg.sort_values("OPS", ascending=False).head(5)
        cols = st.columns(5)
        for i, (_, row) in enumerate(top5.iterrows()):
            with cols[i]:
                st.markdown(f"""
                <div style="background:#fff3cd;padding:10px;border-radius:6px;text-align:center;font-size:12px">
                <b style="color:{team_color}">{row['선수명']}</b><br>
                <small>({row['팀']})</small><br>
                OPS: <b>{row['OPS']:.3f}</b><br>홈런: {int(row['홈런'])}<br>
                타율: {row['타율']:.3f} ({int(row['안타'])}/{int(row['타수'])})
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("데이터 없음")

with watch_tab2:
    opp_pit = pitcher_record[
        (pitcher_record["gameId"].isin(team_game_ids)) &
        (pitcher_record["팀"] != selected_team)
    ].copy()
    min_ip_raw = team_games_count * 1 * 0.07
    st.markdown(f"*최소 이닝(아웃수 기준): {min_ip_raw:.1f} IP*")
    if not opp_pit.empty:
        # 아웃수 합산으로 이닝 계산
        opp_pit_agg = opp_pit.groupby(["팀", "선수명", "page_id"]).agg(
            아웃수=("아웃수", "sum"), 삼진=("삼진", "sum"), 볼넷=("볼넷", "sum"),
            실점=("실점", "sum"), 자책=("자책", "sum"), 투구수=("투구수", "sum")
        ).reset_index()
        opp_pit_agg["IP"] = opp_pit_agg["아웃수"] / 3.0
        opp_pit_agg = opp_pit_agg[opp_pit_agg["IP"] >= min_ip_raw].copy()
        opp_pit_agg["ERA"] = (opp_pit_agg["자책"] / opp_pit_agg["IP"].where(opp_pit_agg["IP"] > 0, 1) * 9).round(2)
        # 승패세홀 from player_pitcher_result
        top5_pit = opp_pit_agg.sort_values("ERA").head(5)
        cols = st.columns(5)
        for i, (_, row) in enumerate(top5_pit.iterrows()):
            with cols[i]:
                # 승패세홀 조회
                pp_res = player_pitcher_result[player_pitcher_result["선수명"] == row["선수명"]]
                w_p = (pp_res["결과"] == "승").sum()
                l_p = (pp_res["결과"] == "패").sum()
                s_p = (pp_res["결과"] == "세").sum()
                h_p = (pp_res["결과"] == "홀드").sum()
                st.markdown(f"""
                <div style="background:#cff4fc;padding:10px;border-radius:6px;text-align:center;font-size:12px">
                <b style="color:{team_color}">{row['선수명']}</b><br>
                <small>({row['팀']})</small><br>
                ERA: <b>{row['ERA']:.2f}</b><br>K: {int(row['삼진'])}<br>
                {w_p}승{l_p}패{s_p}세{h_p}홀
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("데이터 없음")

st.markdown("---")

# ══════════════════════════════════════
# § 12  팀별 상대 전적
# ══════════════════════════════════════
st.markdown("### 🔄 팀별 상대 전적")
h2h_data = []
for opp in TEAMS:
    if opp == selected_team:
        continue
    w = l = d = 0
    for _, row in match_elo.dropna(subset=["Away_R", "Home_R"]).iterrows():
        is_our_away = (row["Away"] == selected_team and row["Home"] == opp)
        is_our_home = (row["Home"] == selected_team and row["Away"] == opp)
        if not (is_our_away or is_our_home):
            continue
        team_r = row["Away_R"] if is_our_away else row["Home_R"]
        opp_r = row["Home_R"] if is_our_away else row["Away_R"]
        if team_r > opp_r: w += 1
        elif team_r < opp_r: l += 1
        else: d += 1
    h2h_data.append({"상대팀": opp, "승": w, "패": l, "무": d, "전적": f"{w}승{l}패{d}무"})
h2h_df = pd.DataFrame(h2h_data)
cols = st.columns(9)
for i, (_, row) in enumerate(h2h_df.iterrows()):
    with cols[i % 9]:
        opp_logo2 = os.path.join(LOGO_DIR, LOGO_FILE.get(row["상대팀"], ""))
        if os.path.exists(opp_logo2):
            st.image(opp_logo2, width=40)
        color_h2h = "#1a7f37" if row["승"] > row["패"] else ("#cf222e" if row["승"] < row["패"] else "#6e7781")
        st.markdown(f'<div style="text-align:center;font-size:12px;"><b>{row["상대팀"]}</b><br><span style="color:{color_h2h}">{row["전적"]}</span></div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown('<div style="text-align:center;color:#888;font-size:12px">KBO 대시보드 | 데이터 기준: 2026-04-12</div>', unsafe_allow_html=True)
