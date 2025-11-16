import math
import random
import re
from dataclasses import dataclass
from typing import List, Tuple, Dict

import requests
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


@dataclass
class PlayerSlot:
    position: str
    url: str


@dataclass
class TeamInput:
    name: str
    formation: str
    style: str
    pressure: str
    stats: TeamStats
    home: bool
    slots: List[PlayerSlot]


# ============================
#   POMOĆNE FUNKCIJE
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
#   UČITAVANJE IGRAČA SA LINKA
# ============================

ATTR_LABELS = [
    ("Q", "q"),
    ("Kp", "kp"),
    ("Tk", "tk"),
    ("Pa", "pa"),
    ("Sh", "sh"),
    ("He", "he"),
    ("Sp", "sp"),
    ("St", "st"),
    ("Pe", "pe"),
    ("Bc", "bc"),
]


def _extract_attr(text: str, label: str) -> float:
    """
    Pokušava da nađe npr. 'Q 96', 'Q: 96', 'Q=96' u tekstu HTML stranice.
    Ako ne nađe, baca ValueError.
    """
    # normalizuj whitespace
    t = re.sub(r"\s+", " ", text)

    # prvo probaj label + :/=/space + broj
    m = re.search(rf"{label}\s*[:=]?\s*([0-9]{{1,3}})", t)
    if m:
        return float(m.group(1))

    # fallback: label, pa u narednih par karaktera broj
    m = re.search(rf"{label}[^\d]{{0,5}}([0-9]{{1,3}})", t)
    if m:
        return float(m.group(1))

    raise ValueError(f"Nije pronađen atribut {label} u tekstu")


def load_player_from_url(url: str) -> Dict[str, float]:
    """
    Vraća dict sa ključevima q,kp,tk,pa,sh,he,sp,st,pe,bc.
    Ako nešto ne uspe, baca ValueError.
    """
    if not url:
        raise ValueError("Prazan URL")

    try:
        resp = requests.get(url, timeout=10)
    except Exception as e:
        raise ValueError(f"Ne mogu da dohvatim URL: {e}")

    if resp.status_code != 200:
        raise ValueError(f"HTTP kod {resp.status_code}")

    text = resp.text

    attrs: Dict[str, float] = {}
    for label, key in ATTR_LABELS:
        try:
            attrs[key] = _extract_attr(text, label)
        except ValueError:
            # ako jedan atribut fali, obori sve – bolje nego polovično
            raise ValueError(f"Nisam uspeo da pročitam {label} sa stranice.")

    return attrs


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

POS_OPTIONS = [
    "GK",
    "DL", "DC", "DR",
    "DML", "DMC", "DMR",
    "ML", "MC", "MR",
    "AML", "AMC", "AMR",
    "STL", "STR", "ST",
]


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


def inputs_for_line_urls(side: str, label: str, count: int, default_pos_list: List[str], start_index: int) -> List[PlayerSlot]:
    slots: List[PlayerSlot] = []
    if count <= 0:
        return slots

    st.markdown(f"**{side} – {label} ({count})**")
    cols = st.columns(count)

    for i in range(count):
        with cols[i]:
            pos_default = default_pos_list[i] if i < len(default_pos_list) else default_pos_list[-1]
            if pos_default in POS_OPTIONS:
                default_index = POS_OPTIONS.index(pos_default)
            else:
                default_index = 0
            pos = st.selectbox(
                "Pozicija",
                POS_OPTIONS,
                index=default_index,
                key=f"{side}_{label}_pos_{start_index+i}"
            )
            url = st.text_input(
                "Player URL",
                value="",
                key=f"{side}_{label}_url_{start_index+i}"
            )
            slots.append(PlayerSlot(position=pos, url=url))

    st.markdown("---")
    return slots


def build_team_input(side: str) -> TeamInput:
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

    # SASTAV – vizuelni teren sa URL-ovima
    st.subheader(f"{side} – Sastav (pozicija + URL igrača)")
    d_count, m_count, a_count = formation_to_lines(formation)

    gk_slots = inputs_for_line_urls(side, "GK", 1, ["GK"], 0)

    def_defaults = ["DL"] + ["DC"] * max(0, d_count - 2) + (["DR"] if d_count >= 2 else [])
    if not def_defaults:
        def_defaults = ["DC"]
    def_slots = inputs_for_line_urls(side, "Odbrana", d_count, def_defaults, 1)

    if m_count == 5:
        mid_defaults = ["ML", "MC", "MC", "MC", "MR"]
    elif m_count == 3:
        mid_defaults = ["ML", "MC", "MR"]
    else:
        mid_defaults = ["ML"] + ["MC"] * max(0, m_count - 2) + (["MR"] if m_count >= 2 else [])
        if not mid_defaults:
            mid_defaults = ["MC"]
    mid_slots = inputs_for_line_urls(side, "Vezni red", m_count, mid_defaults, 1 + d_count)

    if a_count == 1:
        att_defaults = ["ST"]
    else:
        att_defaults = ["STL", "STR"] + ["ST"] * max(0, a_count - 2)
    att_slots = inputs_for_line_urls(side, "Napad", a_count, att_defaults, 1 + d_count + m_count)

    slots = gk_slots + def_slots + mid_slots + att_slots

    # STATS
    stats = inputs_for_team_stats(side)

    return TeamInput(
        name=name,
        formation=formation,
        style=style,
        pressure=pressure,
        stats=stats,
        home=False,
        slots=slots,
    )


def build_team_from_input(inp: TeamInput) -> Team:
    players: List[Player] = []
    errors: List[str] = []

    for idx, slot in enumerate(inp.slots):
        if not slot.url:
            errors.append(f"Slot {idx+1} ({slot.position}): nema URL-a.")
            continue
        try:
            attrs = load_player_from_url(slot.url)
        except ValueError as e:
            errors.append(f"{slot.position}: {e}")
            continue

        players.append(Player(
            position=slot.position,
            role=pos_to_role(slot.position),
            q=attrs["q"],
            kp=attrs["kp"],
            tk=attrs["tk"],
            pa=attrs["pa"],
            sh=attrs["sh"],
            he=attrs["he"],
            sp=attrs["sp"],
            st=attrs["st"],
            pe=attrs["pe"],
            bc=attrs["bc"],
        ))

    if errors:
        st.error("Greške pri čitanju igrača:\n" + "\n".join(errors))

    return Team(
        name=inp.name,
        players=players,
        formation=inp.formation,
        style=inp.style,
        pressure=inp.pressure,
        stats=inp.stats,
        home=inp.home,
    )


# ============================
#   MAIN
# ============================

def main():
    st.title("ManagerLeague – taktički simulator (fan-made)")

    st.markdown(
        """
        **Raspored:**
        1. Odaberi teren (neutralno / domaćin).
        2. Za svaki tim: Tim → Taktika → Sastav (pozicija + URL) → Team stats.
        3. Pokreni simulaciju i dobiješ procente + 5 najčešćih rezultata.

        U polje *Player URL* ubaciš link tipa  
        `https://football.managerleague.com/ml/player/87277941?ref=569380`  
        i simulator će pokušati da pročita Q, Kp, Tk, Pa, Sh, He, Sp, St, Pe, Bc iz stranice.
        """
    )

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
        team_inp_a = build_team_input("Ja")
    with colB:
        team_inp_b = build_team_input("Protivnik")

    if ground == "Neutralno":
        team_inp_a.home = False
        team_inp_b.home = False
    elif ground == "Ja sam domaćin":
        team_inp_a.home = True
        team_inp_b.home = False
    else:
        team_inp_a.home = False
        team_inp_b.home = True

    st.subheader("Simulacija")
    n_matches = st.number_input("Broj simulacija", 50, 5000, 500, step=50)

    if st.button("Pokreni simulacije"):
        team_a = build_team_from_input(team_inp_a)
        team_b = build_team_from_input(team_inp_b)

        if not team_a.players or not team_b.players:
            st.error("Moraš imati bar jednog validnog igrača u oba tima.")
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
