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
    name: str
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
    morale: float


@dataclass
class Team:
    name: str
    players: List[Player]  # tačno 11 iz startne postave
    formation: str         # npr. "4-4-2"
    style: str             # "mixed", "continental", "longballs"
    stats: TeamStats
    home: bool             # prednost domaćeg terena?


# ============================
#   PARSER ZA IGRAČE
# ============================

"""
Očekivan format po liniji (CSV, bez zaglavlja):

Ime,Role,Q,Kp,Tk,Pa,Sh,He,Sp,St,Pe,Bc

Role mora biti jedno od:
- Gk
- Def
- Mid
- Att

Primer jedne linije:
Predrag Rajkovic,Gk,96,98,79,86,71,74,97,94,96,95
"""

def parse_players_block(text: str) -> List[Player]:
    players = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 12:
            st.warning(f"Linija nema 12 polja, preskačem: {line}")
            continue
        name, role = parts[0], parts[1]
        try:
            q  = float(parts[2])
            kp = float(parts[3])
            tk = float(parts[4])
            pa = float(parts[5])
            sh = float(parts[6])
            he = float(parts[7])
            sp = float(parts[8])
            stg = float(parts[9])
            pe = float(parts[10])
            bc = float(parts[11])
        except ValueError:
            st.warning(f"Ne mogu da parsiram broj u liniji: {line}")
            continue

        players.append(Player(
            name=name,
            role=role,
            q=q,
            kp=kp,
            tk=tk,
            pa=pa,
            sh=sh,
            he=he,
            sp=sp,
            st=stg,
            pe=pe,
            bc=bc,
        ))
    return players


# ============================
#   TAKTIČKI BONUSI
# ============================

def style_match_bonus(my_style: str, opp_style: str) -> float:
    """
    RPS logika:
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


# gruba tabela ko koga voli po formaciji – možeš kasnije da proširiš
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
    Koristi sve atribute + team stats.
    """

    base_q = average_q(team)

    atk_raw = 0.0
    def_raw = 0.0

    for p in team.players:
        role = p.role.lower()
        if role in ("att", "a"):
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
        elif role in ("mid", "m"):
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
        elif role in ("def", "d"):
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
    def_mod += 0.02 * (s.morale - 50) / 50.0

    # domaći teren
    home_atk = 0.5 if team.home else 0.0
    home_def = 0.5 if team.home else 0.0

    attack_rating  = base_q + atk_raw * 0.15 + atk_mod * 5 + home_atk
    defense_rating = base_q + def_raw * 0.15 + def_mod * 5 + home_def

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
#   STREAMLIT GUI
# ============================

def team_stats_inputs(prefix: str) -> TeamStats:
    st.subheader(f"{prefix} – Team stats")
    attacking = st.slider(f"{prefix} Attacking", 0, 100, 50)
    defending = st.slider(f"{prefix} Defending", 0, 100, 50)
    counter_attacking = st.slider(f"{prefix} Counter-attacking", 0, 100, 50)
    offside = st.slider(f"{prefix} Offside", 0, 100, 50)
    free_kick = st.slider(f"{prefix} Free-kick", 0, 100, 50)
    corner = st.slider(f"{prefix} Corner", 0, 100, 50)
    penalty = st.slider(f"{prefix} Penalty", 0, 100, 50)
    understanding = st.slider(f"{prefix} Understanding", 0, 100, 50)
    teamplay = st.slider(f"{prefix} Teamplay", 0, 100, 50)
    morale = st.slider(f"{prefix} Morale", 0, 100, 50)

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
        morale=morale,
    )


def build_team_ui(side: str) -> Team:
    st.header(f"Tim: {side}")

    name = st.text_input(f"{side} – ime tima", value=side)

    col1, col2, col3 = st.columns(3)
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
        home = st.checkbox(f"{side} je domaćin?", value=(side == "Ja"))

    st.markdown(
        f"**{side} – Unesi TAČNO 11 igrača (CSV, po liniji):**  \n"
        "`Ime,Role,Q,Kp,Tk,Pa,Sh,He,Sp,St,Pe,Bc`"
    )
    players_block = st.text_area(f"{side} – igrači", value="", height=220)

    stats = team_stats_inputs(side)

    players = parse_players_block(players_block)
    if len(players) != 11:
        st.warning(f"{side}: trenutno imaš {len(players)} igrača. Simulator traži tačno 11.")

    team = Team(
        name=name,
        players=players,
        formation=formation,
        style=style,
        stats=stats,
        home=home,
    )
    return team


def main():
    st.title("ManagerLeague – taktički simulator (fan made)")

    st.markdown(
        """
        Ovo NIJE zvanični ML engine, ali:
        - koristi sve glavne atribute igrača (Q, Kp, Tk, Pa, Sh, He, Sp, St, Pe, Bc)
        - koristi team stats (Attacking, Defending, Counter, Offside, FK, Corner, Penalty, Teamplay, Understanding, Morale)
        - uzima u obzir stil igre (Mixed / Continental / Longballs) i njihov RPS odnos
        - formacija vs formacija (4-4-2 vs 3-5-2 itd.)
        - prednost domaćeg terena

        Možeš da upoređuješ bilo koje dve postave i vidiš procenat pobeda / nerešenih / poraza.
        """
    )

    colA, colB = st.columns(2)
    with colA:
        team_a = build_team_ui("Ja")
    with colB:
        team_b = build_team_ui("Protivnik")

    n_matches = st.slider("Broj simulacija", 50, 2000, 500, step=50)

    if st.button("Pokreni simulacije"):
        if len(team_a.players) != 11 or len(team_b.players) != 11:
            st.error("Oba tima moraju imati TAČNO 11 igrača.")
            return

        win_a, draw, win_b = simulate_series(team_a, team_b, n_matches=n_matches)

        st.subheader("Rezultati")
        st.write(f"Simulirano mečeva: {n_matches}")
        col1, col2, col3 = st.columns(3)
        col1.metric(f"Pobede {team_a.name}", f"{win_a:.1f} %")
        col2.metric("Nerešeno", f"{draw:.1f} %")
        col3.metric(f"Pobede {team_b.name}", f"{win_b:.1f} %")


if __name__ == "__main__":
    main()
