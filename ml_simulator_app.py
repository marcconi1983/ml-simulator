import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict

import streamlit as st

# ============================
#   MODELI
# ============================

@dataclass
class Player:
    position: str  # GK, DL, DC, DR, ML, MC, MR, ST ...
    role: str      # Gk, Def, Mid, Att (za engine)
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

def formation_to_lines(formation: str) -> Tuple[int, int, int]:
    """4-4-2 -> (4,4,2) itd."""
    parts = formation.split("-")
    if len(parts) != 3:
        return 4, 4, 2
    try:
        d = int(parts[0])
        m = int(parts[1])
        a = int(parts[2])
        return d, m, a
    except ValueError:
        return 4, 4, 2


def pos_to_role(pos: str) -> str:
    pos = pos.upper()
    if pos == "GK":
        return "Gk"
    if pos.startswith("D"):
        return "Def"
    if pos.startswith("M"):
        return "Mid"
    if pos.startswith("A") or pos.startswith("S"):  # AM, ST
        return "Att"
    return "Mid"


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


def simulate_series(team_a: Team, team_b: Team, n_matches: int) -> Tuple[float, float, float, Dict[Tuple[int,int], int]]:
    win_a = draw = win_b = 0
    scores: Dict[Tuple[int,int], int] = {}
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
        100 * draw  / n_matches,
        100 * win_b / n_matches,
        scores
    )

# ============================
#   UI – TIM / SASTAV / STATS
# ============================

POS_OPTIONS = ["GK", "DL", "DCL", "DCR", "DR",
               "DML", "DMC", "DMR",
               "ML", "MCL", "MCR", "MR",
               "AML", "AMC", "AMR",
               "STL", "STR", "ST"]


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


def inputs_for_line(side: str, label: str, count: int, default_pos_list: List[str], start_index: int) -> List[Player]:
    """Jedan horizontalni red na terenu (def/mid/att)."""
    players: List[Player] = []
    if count <= 0:
        return players

    st.markdown(f"**{side} – {label} ({count})**")
    cols = st.columns(count)

    for i in range(count):
        with cols[i]:
            pos_default = default_pos_list[i] if i < len(default_pos_list) else default_pos_list[-1]
            pos = st.selectbox(
                "Pozicija",
                POS_OPTIONS,
                index=POS_OPTIONS.index(pos_default),
                key=f"{side}_{label}_pos_{start_index+i}"
            )
            q  = st.number_input("Q", 0, 100, 95, key=f"{side}_{label}_q_{start_index+i}")
            kp = st.number_input("Kp", 0, 100, 80, key=f"{side}_{label}_kp_{start_index+i}")
            tk = st.number_input("Tk", 0, 100, 80, key=f"{side}_{label}_tk_{start_index+i}")
            pa = st.number_input("Pa", 0, 100, 80, key=f"{side}_{label}_pa_{start_index+i}")
            sh = st.number_input("Sh", 0, 100, 80, key=f"{side}_{label}_sh_{start_index+i}")
            he = st.number_input("He", 0, 100, 80, key=f"{side}_{label}_he_{start_index+i}")
            sp = st.number_input("Sp", 0, 100, 80, key=f"{side}_{label}_sp_{start_index+i}")
            stg = st.number_input("St", 0, 100, 80, key=f"{side}_{label}_st_{start_index+i}")
            pe = st.number_input("Pe", 0, 100, 80, key=f"{side}_{label}_pe_{start_index+i}")
            bc = st.number_input("Bc", 0, 100, 80, key=f"{side}_{label}_bc_{start_index+i}")

            role = pos_to_role(pos)
            players.append(Player(
                position=pos,
                role=role,
                q=q, kp=kp, tk=tk, pa=pa, sh=sh,
                he=he, sp=sp, st=stg, pe=pe, bc=bc
            ))
    st.markdown("---")
    return players


def build_team(side: str) -> Team:
    st.header(f"Tim: {side}")

    # TIM
    name = st.text_input(f"{side} – ime tima", value=side)

    # TAKTIKA
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

    # SASTAV – vizuelni teren
    st.subheader(f"{side} – Sastav na terenu")

    d_count, m_count, a_count = formation_to_lines(formation)

    # GK red
    gk_players = inputs_for_line(
        side, "GK", 1, ["GK"], 0
    )

    # DEF red
    def_defaults = ["DL"] + ["DC"] * (d_count - 2) + ["DR"] if d_count >= 2 else ["DC"]
    def_players = inputs_for_line(
        side, "Odbrana", d_count, def_defaults, 1
    )

    # MID red
    if m_count == 5:
        mid_defaults = ["ML", "MCL", "MC", "MCR", "MR"]
    elif m_count == 3:
        mid_defaults = ["ML", "MC", "MR"]
    else:
        mid_defaults = ["ML"] + ["MC"] * (m_count - 2) + ["MR"] if m_count >= 2 else ["MC"]
    mid_players = inputs_for_line(
        side, "Vezni red", m_count, mid_defaults, 1 + d_count
    )

    # ATT red
    if a_count == 1:
        att_defaults = ["ST"]
    else:
        att_defaults = ["STL", "STR"] + ["ST"] * (a_count - 2)
    att_players = inputs_for_line(
        side, "Napad", a_count, att_defaults, 1 + d_count + m_count
    )

    players = gk_players + def_players + mid_players + att_players

    # STATS
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
    st.title("ManagerLeague – taktički simulator (fan-made)")

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
        if len(team_a.players) == 0 or len(team_b.players) == 0:
            st.error("Moraš da uneseš igrače za oba tima.")
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
