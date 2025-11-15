import math
import random
from dataclasses import dataclass
from typing import List, Tuple

import streamlit as st

# ============================
#   MODELI PODATAKA
# ============================

@dataclass
class Player:
    role: str   # "Gk", "Def", "Mid", "Att"
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
    players: List[Player]  # tačno 11 iz startne postave
    formation: str         # npr. "4-4-2"
    style: str             # "mixed", "continental", "longballs"
    pressure: str          # "attacking","normal","defending","counter-attacking"
    stats: TeamStats
    home: bool             # prednost domaćeg terena?


# ============================
#   TAKTIČKI BONUSI
# ============================

def style_match_bonus(my_style: str, opp_style: str) -> float:
    """
    Rock-paper-scissors logika:
      Longballs > Continental
      Continental > Mixed
      Mixed > Longballs
    Vraća bonus u +/− poenima.
    """
    my = my_style.lower()
    op = opp_style.lower()

    if my == op:
        return 0.0

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


# gruba tabela ko koga voli po formaciji – lako se proširi
FORMATION_MATCHUPS = {
    ("4-4-2", "3-5-2"):  +1.0,
    ("3-5-2", "4-4-2"):  -1.0,
    ("4-5-1", "3-4-3"):  +1.0,
    ("3-4-3", "4-5-1"):  -1.0,
    ("4-4-2", "4-3-3"):  -0.5,
    ("4-3-3", "4-4-2"):  +0.5,
}

def formation_match_bonus(my_form: str, opp_form: str) -> float:
    return FORMATION_MATCHUPS.get((my_form, opp_form), 0.0)


# ============================
#   REJTING NAPADA / ODBRANE
# ============================

def average_q(team: Team) -> float:
    return sum(p.q for p in team.players) / len(team.players)


def compute_line_ratings(team: Team) -> Tuple[float, float]:
    """
    Vraća (attack_rating, defense_rating).
    Koristi sve atribute + team stats + pressure.
    """

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
            def_raw += (
                0.15 * p.tk +
                0.10 * p.bc +
                0.05 * p.st
            )
        elif role == "mid":
            atk_raw += (
                0.25 * p.sh +
                0.30 * p.pa +
                0.15 * p.kp +
                0.10 * p.sp +
                0.05 * p.he +
                0.05 * p.q
            )
            def_raw += (
                0.25 * p.tk +
                0.10 * p.bc +
                0.05 * p.st
            )
        elif role == "def":
            def_raw += (
                0.35 * p.tk +
                0.20 * p.he +
                0.15 * p.st +
                0.15 * p.bc +
                0.05 * p.q
            )
            atk_raw += (
                0.05 * p.pa +
                0.05 * p.he
            )
        else:  # Gk
            def_raw += (
                0.40 * p.q +
                0.15 * p.bc +
                0.10 * p.st
            )

    atk_raw /= max(1, len(team.players))
    def_raw /= max(1, len(team.players))

    s = team.stats

    # team stats uticaj
    atk_mod  = 0.06 * (s.attacking - 50) / 50.0
    atk_mod += 0.03 * (s.teamplay - 50) / 50.0
    atk_mod += 0.03 * (s.understanding - 50) / 50.0
    atk_mod += 0.02 * (s.counter_attacking - 50) / 50.0
    atk_mod += 0.01 * (s.free_kick - 50) / 50.0
    atk_mod += 0.01 * (s.corner - 50) / 50.0

    def_mod  = 0.06 * (s.defending - 50) / 50.0
    def_mod += 0.03 * (s.offside - 50) / 50.0

    # domaći teren
    home_atk = 0.5 if team.home else 0.0
    home_def = 0.5 if team.home else 0.0

    attack_rating  = base_q + atk_raw * 0.15 + atk_mod * 5 + home_atk
    defense_rating = base_q + def_raw * 0.15 + def_mod * 5 + home_def

    # pressure efekat
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


# ============================
#   POISSON SIMULACIJA GOLOVA
# ============================

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

    lambda_a = 1.3 + diff_a * 0.05
    lambda_b = 1.3 + diff_b * 0.05

    lambda_a = max(0.1, lambda_a)
    lambda_b = max(0.1, lambda_b)

    goals_a = poisson_sample(lambda_a)
    goals_b = poisson_sample(lambda_b)
    return goals_a, goals_b


def simulate_series(team_a: Team, team_b: Team, n_matches: int = 500) -> Tuple[float, float, float]:
    win_a = draw = win_b = 0
    for _ in range(n_matches):
        ga, gb = simulate_single_match(team_a, team_b)
        if ga > gb:
            win_a += 1
        elif gb > ga:
            win_b += 1
        else:
            draw += 1

    return (100 * win_a / n_matches,
            100 * draw  / n_matches,
            100 * win_b / n_matches)


# ============================
#   UI POMOĆNE FUNKCIJE
# ============================

def team_stats_inputs(prefix: str) -> TeamStats:
    st.subheader(f"{prefix} – Team stats (0–100)")
    attacking = st.number_input(f"{prefix} Attacking", 0, 100, 50)
    defending = st.number_input(f"{prefix} Defending", 0, 100, 50)
    counter_attacking = st.number_input(f"{prefix} Counter-attacking", 0, 100, 50)
    offside = st.number_input(f"{prefix} Offside", 0, 100, 50)
    free_kick = st.number_input(f"{prefix} Free-kick", 0, 100, 50)
    corner = st.number_input(f"{prefix} Corner", 0, 100, 50)
    penalty = st.number_input(f"{prefix} Penalty", 0, 100, 50)
    understanding = st.number_input(f"{prefix} Understanding", 0, 100, 50)
    teamplay = st.number_input(f"{prefix} Teamplay", 0, 100, 50)

    return TeamStats(
        attacking=attacking,
        defending=defending,
        counter_attacking=counter_attacking,
        offside=offside,
        free_kick=free_kick,
        corner=corner,
        penalty=penalty,
        understanding=understanding,
        teamplay=teamplay,
    )


def parse_formation(formation: str) -> Tuple[int, int, int]:
    parts = formation.split("-")
    if len(parts) < 3:
        return 4, 4, 2
    try:
        d = int(parts[0])
        m = int(parts[1])
        a = int(parts[2])
        return d, m, a
    except ValueError:
        return 4, 4, 2


def players_inputs_for_role(side: str, role_label: str, role_code: str, count: int) -> List[Player]:
    players: List[Player] = []
    if count <= 0:
        return players

    st.markdown(f"**{side} – {role_label} ({count})**")

    for i in range(count):
        cols = st.columns(11)
        # Q, Kp, Tk, Pa, Sh, He, Sp, St, Pe, Bc
        q  = cols[0].number_input(f"{role_label}{i+1} Q", 0, 100, 90, key=f"{side}_{role_label}{i}_q")
        kp = cols[1].number_input("Kp", 0, 100, 80, key=f"{side}_{role_label}{i}_kp")
        tk = cols[2].number_input("Tk", 0, 100, 80, key=f"{side}_{role_label}{i}_tk")
        pa = cols[3].number_input("Pa", 0, 100, 80, key=f"{side}_{role_label}{i}_pa")
        sh = cols[4].number_input("Sh", 0, 100, 80, key=f"{side}_{role_label}{i}_sh")
        he = cols[5].number_input("He", 0, 100, 80, key=f"{side}_{role_label}{i}_he")
        sp = cols[6].number_input("Sp", 0, 100, 80, key=f"{side}_{role_label}{i}_sp")
        stg = cols[7].number_input("St", 0, 100, 80, key=f"{side}_{role_label}{i}_st")
        pe = cols[8].number_input("Pe", 0, 100, 80, key=f"{side}_{role_label}{i}_pe")
        bc = cols[9].number_input("Bc", 0, 100, 80, key=f"{side}_{role_label}{i}_bc")

        players.append(Player(
            role=role_code,
            q=q, kp=kp, tk=tk, pa=pa, sh=sh,
            he=he, sp=sp, st=stg, pe=pe, bc=bc
        ))

    st.markdown("---")
    return players


def build_team_ui(side: str) -> Team:
    st.header(f"Tim: {side}")

    name = st.text_input(f"{side} – ime tima", value=side)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        formation = st.selectbox(
            f"{side} – formacija",
            ["4-4-2", "4-5-1", "4-3-3", "3-5-2", "3-4-3", "5-4-1"],
            index=0
        )
    with col2:
        style = st.selectbox(
            f"{side} – stil igre",
            ["mixed", "continental", "longballs"],
            index=0
        )
    with col3:
        pressure = st.selectbox(
            f"{side} – pressure",
            ["normal", "attacking", "defending", "counter-attacking"],
            index=0
        )
    with col4:
        home = st.checkbox(f"{side} je domaćin?", value=(side == "Ja"))

    stats = team_stats_inputs(side)

    # formacija → broj def/mid/att
    d_count, m_count, a_count = parse_formation(formation)

    st.markdown(f"### {side} – igrači (1 Gk, {d_count} Def, {m_count} Mid, {a_count} Att)")

    # GK – uvek 1
    gk_players = players_inputs_for_role(side, "GK", "Gk", 1)
    def_players = players_inputs_for_role(side, "Def", "Def", d_count)
    mid_players = players_inputs_for_role(side, "Mid", "Mid", m_count)
    att_players = players_inputs_for_role(side, "Att", "Att", a_count)

    players = gk_players + def_players + mid_players + att_players

    if len(players) != 1 + d_count + m_count + a_count:
        st.warning(f"{side}: broj igrača ne odgovara formaciji.")

    team = Team(
        name=name,
        players=players,
        formation=formation,
        style=style,
        pressure=pressure,
        stats=stats,
        home=home,
    )
    return team


# ============================
#   MAIN
# ============================

def main():
    st.title("ManagerLeague – taktički simulator (fan-made)")

    st.markdown(
        """
        Ovo NIJE zvanični ML engine, ali koristi:

        - sve glavne atribute igrača (Q, Kp, Tk, Pa, Sh, He, Sp, St, Pe, Bc)
        - team stats (Attacking, Defending, Counter, Offside, FK, Corner, Penalty,
          Teamplay, Understanding)
        - stil igre (Mixed / Continental / Longballs) i njihov RPS odnos
        - formacija vs formacija (4-4-2 vs 3-5-2 itd.)
        - prednost domaćeg terena
        - taktički pressure (Attacking / Normal / Defending / Counter-attacking)

        Unesi svoje i protivnikove atribute, pa pokreni simulacije.
        """
    )

    colA, colB = st.columns(2)
    with colA:
        team_a = build_team_ui("Ja")
    with colB:
        team_b = build_team_ui("Protivnik")

    n_matches = st.number_input("Broj simulacija", 50, 5000, 500, step=50)

    if st.button("Pokreni simulacije"):
        if len(team_a.players) != len(team_b.players) or len(team_a.players) == 0:
            st.error("Oba tima moraju imati validan broj igrača za izabranu formaciju.")
            return

        win_a, draw, win_b = simulate_series(team_a, team_b, n_matches=int(n_matches))

        st.subheader("Rezultati")
        st.write(f"Simulirano mečeva: {int(n_matches)}")
        col1, col2, col3 = st.columns(3)
        col1.metric(f"Pobede {team_a.name}", f"{win_a:.1f} %")
        col2.metric("Nerešeno", f"{draw:.1f} %")
        col3.metric(f"Pobede {team_b.name}", f"{win_b:.1f} %")


if __name__ == "__main__":
    main()
