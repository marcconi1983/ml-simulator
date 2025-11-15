import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict

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
#   PARSER ZA PASTE IZ ML
# ============================

"""
Očekivan format (copy/paste iz ML Players tabele):

Role Name Age Q DQ Kp KpD Tk TkD Pa PaD Sh ShD He HeD Sp SpD St StD Pe PeD Bc BcD Tot TotD Fit SA

Parser koristi:
Q  = kolona 3
Kp = 5
Tk = 7
Pa = 9
Sh = 11
He = 13
Sp = 15
St = 17
Pe = 19
Bc = 21
"""

def parse_players_block_ml(text: str) -> List[Player]:
    players: List[Player] = []
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    for line in lines:
        # preskoči header
        if line.lower().startswith("role "):
            continue

        # delimiter: pre svega TAB, ili zarez, ili whitespace
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t")]
        elif "," in line:
            parts = [p.strip() for p in line.split(",")]
        else:
            parts = [p for p in line.split()]

        if len(parts) < 22:
            continue

        try:
            role = parts[0]
            name = parts[1]
            q  = float(parts[3])
            kp = float(parts[5])
            tk = float(parts[7])
            pa = float(parts[9])
            sh = float(parts[11])
            he = float(parts[13])
            sp = float(parts[15])
            stg = float(parts[17])
            pe = float(parts[19])
            bc = float(parts[21])
        except ValueError:
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

    # uzmi samo prvih 11, za startnu postavu
    if len(players) > 11:
        players = players[:11]

    return players


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
    Koristi sve atribute + team stats + pressure + home.
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


def simulate_series(team_a: Team, team_b: Team, n_matches: int = 500) -> Tuple[float, float, float, Dict[Tuple[int, int], int]]:
    win_a = draw = win_b = 0
    score_counts: Dict[Tuple[int, int], int] = {}
    for _ in range(n_matches):
        ga, gb = simulate_single_match(team_a, team_b)
        if ga > gb:
            win_a += 1
        elif gb > ga:
            win_b += 1
        else:
            draw += 1
        score_counts[(ga, gb)] = score_counts.get((ga, gb), 0) + 1

    return (100 * win_a / n_matches,
            100 * draw  / n_matches,
            100 * win_b / n_matches,
            score_counts)


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


def build_team_ui(side: str) -> Team:
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

    # SASTAV – PASTE IZ ML
    st.subheader(f"{side} – Sastav (paste direktno iz ML Players)")
    st.markdown(
        "Nalepi 11 igrača direktno iz ML Players tabele (kopiraš redove sa Role, Name, Age, Q, ...)."
    )
    players_block = st.text_area(f"{side} – paste igrača", value="", height=220)

    players = parse_players_block_ml(players_block)
    st.write(f"Detektovano igrača: {len(players)} (uzima se prvih 11 za simulaciju).")

    # Vizuelna tabela atributa + dropdown za poziciju
    if players:
        st.markdown(f"**{side} – tabela atributa i pozicija**")
        pos_options = ["GK", "DL", "DC", "DR", "DML", "DMC", "DMR", "ML", "MC", "MR", "AML", "AMC", "AMR", "ST"]

        for i, p in enumerate(players):
            cols = st.columns(8)
            with cols[0]:
                st.write(p.name)
            with cols[1]:
                st.write(p.role)
            with cols[2]:
                default_pos = "GK"
                if p.role.lower() == "def":
                    default_pos = "DC"
                elif p.role.lower() == "mid":
                    default_pos = "MC"
                elif p.role.lower() == "att":
                    default_pos = "ST"
                st.selectbox(
                    "Pozicija",
                    pos_options,
                    index=pos_options.index(default_pos),
                    key=f"{side}_pos_{i}"
                )
            with cols[3]:
                st.write(f"Q: {p.q:.0f}")
            with cols[4]:
                st.write(f"Kp/Tk: {p.kp:.0f}/{p.tk:.0f}")
            with cols[5]:
                st.write(f"Pa/Sh: {p.pa:.0f}/{p.sh:.0f}")
            with cols[6]:
                st.write(f"He/Sp: {p.he:.0f}/{p.sp:.0f}")
            with cols[7]:
                st.write(f"St/Pe/Bc: {p.st:.0f}/{p.pe:.0f}/{p.bc:.0f}")

    # STATS
    stats = team_stats_inputs(side)

    team = Team(
        name=name,
        players=players,
        formation=formation,
        style=style,
        pressure=pressure,
        stats=stats,
        home=False,   # biće postavljeno kasnije na osnovu terena
    )
    return team


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
        horizontal=True
    )

    colA, colB = st.columns(2)
    with colA:
        team_a = build_team_ui("Ja")
    with colB:
        team_b = build_team_ui("Protivnik")

    # postavi home flag prema izboru terena
    if ground == "Neutralno":
        team_a.home = False
        team_b.home = False
    elif ground == "Ja sam domaćin":
        team_a.home = True
        team_b.home = False
    else:  # Protivnik je domaćin
        team_a.home = False
        team_b.home = True

    # BROJ SIMULACIJA
    st.subheader("Simulacija")
    n_matches = st.number_input("Broj simulacija", 50, 5000, 500, step=50)

    if st.button("Pokreni simulacije"):
        if len(team_a.players) < 11 or len(team_b.players) < 11:
            st.error("Oba tima moraju imati bar 11 igrača (nalepi tačno startnu postavu).")
            return

        win_a, draw, win_b, score_counts = simulate_series(team_a, team_b, n_matches=int(n_matches))

        # REZULTATI %
        st.subheader("Rezultat simulacije (u %)")
        col1, col2, col3 = st.columns(3)
        col1.metric(f"Pobede {team_a.name}", f"{win_a:.1f} %")
        col2.metric("Nerešeno", f"{draw:.1f} %")
        col3.metric(f"Pobede {team_b.name}", f"{win_b:.1f} %")

        # 5 NAJČEŠĆIH REZULTATA
        st.subheader("5 najčešćih rezultata")

        if score_counts:
            total = float(n_matches)
            top5 = sorted(score_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            for (ga, gb), cnt in top5:
                proc = 100.0 * cnt / total
                st.write(f"{ga} : {gb}  –  {proc:.1f}%  ({cnt} puta)")
        else:
            st.write("Nema podataka o rezultatima.")


if __name__ == "__main__":
    main()
