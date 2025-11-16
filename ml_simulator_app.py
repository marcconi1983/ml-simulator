import math
import random
import re
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import streamlit as st
import requests

# ============================
#   MODELI
# ============================

@dataclass
class Player:
    name: str
    role: str      # Gk, Def, Mid, Att
    q: float
    kp: float
    tk: float
    pa: float
    sh: float
    he: float
    sp: float
    st: float
    pe: float
    bc: float


@dataclass
class TeamStats:
    attacking: float
    defending: float
    counter_attacking: float
    offside: float
    free_kick: float
    corner: float
    penalty: float
    understanding: float
    teamplay: float


@dataclass
class Team:
    name: str
    players: List[Player]
    formation: str
    style: str
    pressure: str
    stats: TeamStats
    home: bool


# ============================
#   HELPERI
# ============================

def pos_to_role(pos: str) -> str:
    """Pretvori oznaku pozicije u ulogu za engine."""
    pos = pos.lower()
    if pos in ("gk",):
        return "Gk"
    if pos.startswith("d"):
        return "Def"
    if pos.startswith("m"):
        return "Mid"
    if pos.startswith("a") or pos.startswith("s"):
        return "Att"
    return "Mid"


# ============================
#   SCRAPER ZA ml-club.eu
# ============================

def scrape_team_from_ml_club(url: str) -> List[Dict[str, float]]:
    """
    Prima link sa ml-club.eu (npr. https://ml-club.eu/?team=118270%3A)
    i vraća listu dict-ova:
      { 'name', 'age', 'q','kp','tk','pa','sh','he','sp','st','pe','bc' }
    """
    players: List[Dict[str, float]] = []
    if not url.strip():
        return players

    try:
        resp = requests.get(url.strip(), timeout=10)
        resp.raise_for_status()
    except Exception:
        return players

    # Skini HTML tagove, ostavi čist tekst
    text = resp.text
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    header = "Age Name Q Kp Tk Pa Sh He Sp St Pe Bc"
    idx = text.find(header)
    if idx == -1:
        return players

    body = text[idx + len(header):]

    # 31 Predrag Rajković 96.250 98 79 86 71 74 97 94 96 95 89.513 93 4
    row_pattern = re.compile(
        r"(\d+)\s+([^\d]+?)\s+([\d.]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)",
        re.UNICODE
    )

    for m in row_pattern.finditer(body):
        age = int(m.group(1))
        name = m.group(2).strip()
        q = float(m.group(3))
        kp = float(m.group(4))
        tk = float(m.group(5))
        pa = float(m.group(6))
        sh = float(m.group(7))
        he = float(m.group(8))
        sp = float(m.group(9))
        st_attr = float(m.group(10))
        pe = float(m.group(11))
        bc = float(m.group(12))

        players.append({
            "age": age,
            "name": name,
            "q": q,
            "kp": kp,
            "tk": tk,
            "pa": pa,
            "sh": sh,
            "he": he,
            "sp": sp,
            "st": st_attr,
            "pe": pe,
            "bc": bc,
        })

    return players


# ============================
#   TAKTIČKI BONUSI / ENGINE
# ============================

def style_match_bonus(my_style: str, opp_style: str) -> float:
    my = my_style.lower()
    op = opp_style.lower()
    if my == op:
        return 0.0

    # Longballs > Continental > Mixed > Longballs
    if my == "longballs" and op == "continental":
        return +2.0
    if my == "continental" and op == "mixed":
        return +2.0
    if my == "mixed" and op == "longballs":
        return +2.0

    if op == "longballs" and my == "continental":
        return -2.0
    if op == "continental" and my == "mixed":
        return -2.0
    if op == "mixed" and my == "longballs":
        return -2.0
    return 0.0


FORMATION_MATCHUPS = {
    ("4-4-2", "3-5-2"): +1.0,
    ("3-5-2", "4-4-2"): -1.0,
    ("4-5-1", "3-4-3"): +1.0,
    ("3-4-3", "4-5-1"): -1.0,
    ("4-4-2", "4-3-3"): -0.5,
    ("4-3-3", "4-4-2"): +0.5,
}

def formation_match_bonus(my_form: str, opp_form: str) -> float:
    return FORMATION_MATCHUPS.get((my_form, opp_form), 0.0)


def average_q(team: Team) -> float:
    return sum(p.q for p in team.players) / max(1, len(team.players))


def compute_line_ratings(team: Team) -> Tuple[float, float]:
    base_q = average_q(team)
    atk_raw = 0.0
    def_raw = 0.0

    for p in team.players:
        role = p.role.lower()
        if role == "att":
            atk_raw += (
                0.35 * p.sh +
                0.25 * p.pa +
                0.10 * p.kp +
                0.15 * p.sp +
                0.05 * p.he +
                0.10 * p.q
            )
            def_raw += 0.15 * p.tk + 0.10 * p.bc + 0.05 * p.st
        elif role == "mid":
            atk_raw += (
                0.25 * p.sh +
                0.30 * p.pa +
                0.15 * p.kp +
                0.10 * p.sp +
                0.05 * p.he +
                0.05 * p.q
            )
            def_raw += 0.25 * p.tk + 0.10 * p.bc + 0.05 * p.st
        elif role == "def":
            def_raw += (
                0.35 * p.tk +
                0.20 * p.he +
                0.15 * p.st +
                0.15 * p.bc +
                0.05 * p.q
            )
            atk_raw += 0.05 * p.pa + 0.05 * p.he
        else:  # Gk
            def_raw += 0.40 * p.q + 0.15 * p.bc + 0.10 * p.st

    if team.players:
        atk_raw /= len(team.players)
        def_raw /= len(team.players)

    s = team.stats

    atk_mod  = 0.06 * (s.attacking - 50) / 50.0
    atk_mod += 0.03 * (s.teamplay - 50) / 50.0
    atk_mod += 0.03 * (s.understanding - 50) / 50.0
    atk_mod += 0.02 * (s.counter_attacking - 50) / 50.0
    atk_mod += 0.01 * (s.free_kick - 50) / 50.0
    atk_mod += 0.01 * (s.corner - 50) / 50.0

    def_mod  = 0.06 * (s.defending - 50) / 50.0
    def_mod += 0.03 * (s.offside - 50) / 50.0

    home_atk = 0.5 if team.home else 0.0
    home_def = 0.5 if team.home else 0.0

    attack_rating  = base_q + atk_raw * 0.15 + atk_mod * 5 + home_atk
    defense_rating = base_q + def_raw * 0.15 + def_mod * 5 + home_def

    p = team.pressure.lower()
    if p == "attacking":
        attack_rating += 1.0
        defense_rating -= 0.5
    elif p == "defending":
        attack_rating -= 0.5
        defense_rating += 1.0
    elif p == "counter-attacking":
        attack_rating += 0.5 * ((s.counter_attacking - 50) / 50.0)
        defense_rating += 0.2

    return attack_rating, defense_rating


def compute_effective_strengths(team_a: Team, team_b: Team) -> Tuple[float, float, float, float]:
    atk_a, def_a = compute_line_ratings(team_a)
    atk_b, def_b = compute_line_ratings(team_b)

    style_bonus_a = style_match_bonus(team_a.style, team_b.style)
    style_bonus_b = style_match_bonus(team_b.style, team_a.style)
    form_bonus_a = formation_match_bonus(team_a.formation, team_b.formation)
    form_bonus_b = formation_match_bonus(team_b.formation, team_a.formation)

    atk_a += style_bonus_a + form_bonus_a
    def_a += style_bonus_a * 0.3 + form_bonus_a * 0.3
    atk_b += style_bonus_b + form_bonus_b
    def_b += style_bonus_b * 0.3 + form_bonus_b * 0.3

    return atk_a, def_a, atk_b, def_b


def poisson_sample(lmbda: float) -> int:
    L = math.exp(-max(lmbda, 0.01))
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def simulate_single_match(team_a: Team, team_b: Team) -> Tuple[int, int]:
    atk_a, def_a, atk_b, def_b = compute_effective_strengths(team_a, team_b)
    diff_a = atk_a - def_b
    diff_b = atk_b - def_a
    lambda_a = max(0.1, 1.3 + diff_a * 0.05)
    lambda_b = max(0.1, 1.3 + diff_b * 0.05)
    goals_a = poisson_sample(lambda_a)
    goals_b = poisson_sample(lambda_b)
    return goals_a, goals_b


def simulate_series(team_a: Team, team_b: Team, n_matches: int) -> Tuple[float, float, float, Dict[Tuple[int, int], int]]:
    win_a = draw = win_b = 0
    scores: Dict[Tuple[int, int], int] = {}
    for _ in range(n_matches):
        ga, gb = simulate_single_match(team_a, team_b)
        if ga > gb:
            win_a += 1
        elif gb > ga:
            win_b += 1
        else:
            draw += 1
        scores[(ga, gb)] = scores.get((ga, gb), 0) + 1

    return (
        100 * win_a / n_matches,
        100 * draw / n_matches,
        100 * win_b / n_matches,
        scores,
    )

# ============================
#   UI – TEAM / STATS
# ============================

def inputs_for_team_stats(prefix: str) -> TeamStats:
    st.subheader(f"{prefix} – Team stats (0–100)")
    attacking = st.number_input(f"{prefix} Attacking", 0, 100, 95)
    defending = st.number_input(f"{prefix} Defending", 0, 100, 96)
    counter = st.number_input(f"{prefix} Counter-attacking", 0, 100, 50)
    offside = st.number_input(f"{prefix} Offside", 0, 100, 90)
    free_kick = st.number_input(f"{prefix} Free-kick", 0, 100, 97)
    corner = st.number_input(f"{prefix} Corner", 0, 100, 96)
    penalty = st.number_input(f"{prefix} Penalty", 0, 100, 70)
    understanding = st.number_input(f"{prefix} Understanding", 0, 100, 93)
    teamplay = st.number_input(f"{prefix} Teamplay", 0, 100, 95)

    return TeamStats(
        attacking=attacking,
        defending=defending,
        counter_attacking=counter,
        offside=offside,
        free_kick=free_kick,
        corner=corner,
        penalty=penalty,
        understanding=understanding,
        teamplay=teamplay,
    )


def build_team(side: str) -> Team:
    st.header(f"Tim: {side}")

    name = st.text_input(f"{side} – ime tima", value=side)

    # Link ka ml-club.eu
    team_url = st.text_input(
        f"{side} – ml-club link tima",
        help="Npr. https://ml-club.eu/?team=118270%3A",
        key=f"{side}_url",
    )

    if st.button(f"Učitaj tim sa ml-club.eu", key=f"{side}_load"):
        squad = scrape_team_from_ml_club(team_url)
        if not squad:
            st.warning("Nisam uspeo da učitam tim sa datog linka.")
        else:
            st.session_state[f"{side}_squad"] = squad

    squad = st.session_state.get(f"{side}_squad", [])

    # Taktika
    st.subheader(f"{side} – Taktika")
    col1, col2, col3 = st.columns(3)
    with col1:
        formation = st.selectbox(
            f"{side} – formacija",
            ["4-4-2", "4-5-1", "4-3-3", "3-5-2", "3-4-3", "5-4-1"],
            index=0,
        )
    with col2:
        style = st.selectbox(
            f"{side} – stil igre",
            ["mixed", "continental", "longballs"],
            index=0,
        )
    with col3:
        pressure = st.selectbox(
            f"{side} – pressure",
            ["normal", "attacking", "defending", "counter-attacking"],
            index=0,
        )

    players: List[Player] = []

    if squad:
        st.subheader(f"{side} – sastav (čekiraj 11 igrača za simulaciju)")

        for idx, pl in enumerate(squad):
            key_prefix = f"{side}_pl_{idx}"
            cols = st.columns(6)

            with cols[0]:
                use_default = idx < 11
                use = st.checkbox("XI", value=use_default, key=f"{key_prefix}_use")

            with cols[1]:
                st.write(pl["name"])

            with cols[2]:
                # Za prvi igrača pretpostavi Gk, ostali Mid po defaultu.
                default_role = "Gk" if idx == 0 else "Mid"
                role = st.selectbox(
                    "Uloga",
                    ["Gk", "Def", "Mid", "Att"],
                    index=["Gk", "Def", "Mid", "Att"].index(default_role),
                    key=f"{key_prefix}_role",
                )

            with cols[3]:
                q = st.number_input(
                    "Q", 0, 100, int(round(pl["q"])),
                    key=f"{key_prefix}_q",
                )
                kp = st.number_input(
                    "Kp", 0, 100, int(pl["kp"]),
                    key=f"{key_prefix}_kp",
                )
                tk = st.number_input(
                    "Tk", 0, 100, int(pl["tk"]),
                    key=f"{key_prefix}_tk",
                )

            with cols[4]:
                pa = st.number_input(
                    "Pa", 0, 100, int(pl["pa"]),
                    key=f"{key_prefix}_pa",
                )
                sh = st.number_input(
                    "Sh", 0, 100, int(pl["sh"]),
                    key=f"{key_prefix}_sh",
                )
                he = st.number_input(
                    "He", 0, 100, int(pl["he"]),
                    key=f"{key_prefix}_he",
                )

            with cols[5]:
                sp = st.number_input(
                    "Sp", 0, 100, int(pl["sp"]),
                    key=f"{key_prefix}_sp",
                )
                st_attr = st.number_input(
                    "St", 0, 100, int(pl["st"]),
                    key=f"{key_prefix}_st",
                )
                pe = st.number_input(
                    "Pe", 0, 100, int(pl["pe"]),
                    key=f"{key_prefix}_pe",
                )
                bc = st.number_input(
                    "Bc", 0, 100, int(pl["bc"]),
                    key=f"{key_prefix}_bc",
                )

            if use:
                players.append(
                    Player(
                        name=pl["name"],
                        role=role,
                        q=float(q),
                        kp=float(kp),
                        tk=float(tk),
                        pa=float(pa),
                        sh=float(sh),
                        he=float(he),
                        sp=float(sp),
                        st=float(st_attr),
                        pe=float(pe),
                        bc=float(bc),
                    )
                )

        st.markdown("---")
    else:
        st.info("Unesi ml-club link i klikni 'Učitaj tim' da vidiš igrače.")

    stats = inputs_for_team_stats(side)

    return Team(
        name=name,
        players=players,
        formation=formation,
        style=style,
        pressure=pressure,
        stats=stats,
        home=False,
    )


# ============================
#   MAIN
# ============================

def main():
    st.title("ManagerLeague – taktički simulator (ml-club import)")

    # TEREN
    st.subheader("Teren")
    ground = st.radio(
        "",
        ["Neutralno", "Ja sam domaćin", "Protivnik je domaćin"],
        index=0,
        horizontal=True,
    )

    colA, colB = st.columns(2)
    with colA:
        team_a = build_team("Ja")
    with colB:
        team_b = build_team("Protivnik")

    if ground == "Neutralno":
        team_a.home = False
        team_b.home = False
    elif ground == "Ja sam domaćin":
        team_a.home = True
        team_b.home = False
    else:
        team_a.home = False
        team_b.home = True

    st.subheader("Simulacija")
    n_matches = st.number_input("Broj simulacija", 50, 5000, 500, step=50)

    if st.button("Pokreni simulacije"):
        if len(team_a.players) != 11:
            st.error(f"{team_a.name}: mora biti tačno 11 čekiranih igrača (trenutno {len(team_a.players)}).")
            return
        if len(team_b.players) != 11:
            st.error(f"{team_b.name}: mora biti tačno 11 čekiranih igrača (trenutno {len(team_b.players)}).")
            return

        win_a, draw, win_b, scores = simulate_series(team_a, team_b, int(n_matches))

        st.subheader("Rezultat simulacije (u %)")
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Pobede {team_a.name}", f"{win_a:.1f} %")
        c2.metric("Nerešeno", f"{draw:.1f} %")
        c3.metric(f"Pobede {team_b.name}", f"{win_b:.1f} %")

        st.subheader("5 najčešćih rezultata")
        if scores:
            total = float(n_matches)
            top5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
            for (ga, gb), cnt in top5:
                st.write(f"{ga} : {gb}  –  {100*cnt/total:.1f}%  ({cnt} puta)")
        else:
            st.write("Nema podataka.")


if __name__ == "__main__":
    main()
