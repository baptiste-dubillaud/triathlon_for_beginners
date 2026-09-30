"""Cinématique des quatre éducatifs."""

import math

from model import (
    FA, HAND, HEAD_X, HIP_W, SH_W, SH_X, SIDES, UA,
    Body, add, bubbles, capped, clamp, cross, leg_points, lerp, mul, normalize, orthogonal,
    periodic, rotx, segment, set_head, smooth_step, straight_arm, sub, torso_points, two_bone_ik,
)
from render import Exercise

PROF_BOARD = [(0.0, 0.022, 0.16, 0.0), (0.06, 0.026, 0.2, 0.0), (0.94, 0.026, 0.2, 0.0), (1.0, 0.022, 0.18, 0.0)]
PROF_BUOY = [(0.0, 0.06, 0.06, 0.0), (0.12, 0.075, 0.07, 0.0), (0.88, 0.075, 0.07, 0.0), (1.0, 0.06, 0.06, 0.0)]


def leg_muscles(quad="quad", ham="ham"):
    items = []
    for s in "LR":
        items.append(("quad" + s, quad, "quad" + s, "leg" + s))
        items.append(("ham" + s, ham, "ham" + s, "leg" + s))
    return items


# --------------------------------------------------------------------------
# 1. Battements avec planche
# --------------------------------------------------------------------------


class KickBoard(Exercise):
    slug = "01-battements-planche"
    number = 1
    title = "Battements de jambes avec planche"
    subtitle = "Un battement efficace part de la hanche : il propulse et maintient le corps à l'horizontale."
    period = 2.0
    frames = 40
    views = [("side", 20, 960)]
    view_h = 250
    strip = (
        "side",
        ["hipR", "kneeR", "ankleR", "toeR", "hipL", "kneeL", "ankleL", "toeL"],
        [(0.0, "Initiation"), (0.2, "Genou fléchi"), (0.4, "Fouetté"), (0.72, "Remontée")],
        1.0,
    )
    phases = [
        (0.00, 0.15, "Initiation par la hanche", "La cuisse droite (au premier plan) commence à descendre : c'est la hanche qui lance le mouvement."),
        (0.15, 0.50, "Battement descendant", "Le genou fléchit légèrement puis se tend d'un coup, comme un fouet. Le dessus du pied appuie sur l'eau."),
        (0.50, 1.00, "Battement remontant", "Jambe presque tendue, elle remonte jusqu'à ce que le talon affleure la surface, pendant que l'autre descend."),
    ]
    muscles = [
        ("quad", "Quadriceps & fléchisseurs de hanche", "red", "battement descendant"),
        ("ham", "Fessiers & ischio-jambiers", "yellow", "battement remontant"),
        ("core", "Abdominaux / gainage", "violet", "bassin stable, corps aligné"),
    ]
    tips = [
        "Le mouvement part de la hanche : jambes presque tendues, genoux souples.",
        "Chevilles relâchées, pointes de pieds tendues, comme des palmes.",
        "Amplitude réduite (30 à 40 cm) : les talons affleurent la surface.",
        "Bras tendus sur la planche, visage dans l'eau : souffler en continu.",
    ]
    muscle_items = leg_muscles() + [
        ("gluteL", "ham", "hamL", "torso"),
        ("gluteR", "ham", "hamR", "torso"),
        ("core", "core", "core", "torso"),
    ]
    props = [("board", "back")]
    trails = [("toeR", ("side",))]
    n_bubbles = 5
    bubble_views = ("side",)

    def pose(self, t):
        P, A = {}, {}
        body = Body(origin=(0.0, 0.0, -0.04))
        torso_points(P, body)
        for s in "LR":
            straight_arm(P, body, s, (1.0, -0.14, 0.07))
            P["v_handback" + s] = (0.0, 0.0, 1.0)
            leg_points(P, A, body, s, t + (0.5 if s == "L" else 0.0))
        A["quad"] = max(A["quadL"], A["quadR"])
        A["ham"] = max(A["hamL"], A["hamR"])
        A["core"] = 0.5 + 0.08 * math.sin(4 * math.pi * t)
        set_head(P, body.w((HEAD_X, 0.0, -0.01)), (0.3, 0.0, -1.0))
        bubbles(P, A, self.n_bubbles, t, 1.0, 1.0)
        return P, A

    def prop_tubes(self, P):
        hx = P["wristR"][0] - 0.02
        bz = P["handR"][2] - 0.04
        return {"board": capped(segment((hx, 0.0, bz), (hx + 0.46, 0.0, bz), PROF_BOARD, (0.0, 0.0, 1.0)))}


# --------------------------------------------------------------------------
# 2. Crawl rattrapé
# --------------------------------------------------------------------------

CRAWL_UA = [
    (0.00, (1.0, 0.0, -0.05)),
    (0.15, (0.95, 0.08, -0.32)),
    (0.35, (0.3, 0.3, -0.9)),
    (0.52, (-0.5, 0.22, -0.8)),
    (0.62, (-1.0, 0.08, -0.12)),
    (0.72, (-0.6, 0.55, 0.6)),
    (0.82, (0.0, 0.6, 0.8)),
    (0.92, (0.75, 0.2, 0.55)),
]
CRAWL_FA = [
    (0.00, (1.0, 0.0, -0.05)),
    (0.15, (0.45, -0.02, -0.9)),
    (0.35, (0.15, -0.35, -0.95)),
    (0.52, (-0.9, -0.08, -0.45)),
    (0.62, (-1.0, 0.0, 0.1)),
    (0.72, (-0.35, 0.15, -0.9)),
    (0.82, (0.35, 0.1, -0.93)),
    (0.92, (0.85, 0.0, -0.5)),
]
CRAWL_PULL = [(0.0, 0.1), (0.15, 0.5), (0.3, 1.0), (0.5, 0.9), (0.62, 0.15), (0.8, 0.0), (0.95, 0.0)]
CRAWL_TRI = [(0.0, 0.0), (0.3, 0.2), (0.48, 1.0), (0.6, 0.6), (0.7, 0.05), (0.9, 0.0)]
CRAWL_DELT = [(0.0, 0.25), (0.12, 0.45), (0.35, 0.2), (0.6, 0.3), (0.75, 0.95), (0.9, 0.8)]
CRAWL_ROLL = [(0.00, 10), (0.12, 5), (0.26, -25), (0.38, -35), (0.46, -12), (0.50, -10), (0.62, -5), (0.76, 25), (0.88, 35), (0.96, 12)]
CRAWL_PHASES = [
    (0.00, 0.15, "Appui", "Coude haut, l'avant-bras bascule vers le fond pour « accrocher » l'eau."),
    (0.15, 0.40, "Traction", "La main recule sous la poitrine, près de l'axe du corps, et le corps pivote."),
    (0.40, 0.62, "Poussée", "La main accélère jusqu'à la cuisse, le bras se tend vers l'arrière."),
    (0.62, 0.90, "Retour aérien", "Le coude sort en premier, reste haut et relâché ; la main frôle l'eau."),
    (0.90, 1.00, "Entrée & rattrapé", "La main entre devant l'épaule, s'allonge et rejoint l'autre main."),
]


def crawl_arm(P, A, body, s, tl):
    sy = SIDES[s]
    u = normalize(periodic(CRAWL_UA, tl))
    f = normalize(periodic(CRAWL_FA, tl))
    u, f = (u[0], sy * u[1], u[2]), (f[0], sy * f[1], f[2])
    sh = (SH_X, sy * SH_W, 0.0)
    el = add(sh, mul(u, UA))
    wr = add(el, mul(f, FA))
    tip = add(wr, mul(f, HAND))
    P["elbow" + s], P["wrist" + s], P["hand" + s] = body.w(el), body.w(wr), body.w(tip)
    # la paume regarde vers l'arrière pendant la traction
    P["v_handback" + s] = orthogonal(body.d(add((0.9, 0.0, 0.0), (0.0, 0.0, 1.0))), body.d(f))
    P["fA" + s] = body.w(lerp(wr, tip, 0.5))
    P["fB" + s] = add(P["fA" + s], (-0.3, 0.0, 0.0))
    pull = clamp(periodic(CRAWL_PULL, tl))
    A["lat" + s] = pull
    A["f" + s] = clamp((pull - 0.3) * 1.8)
    A["tri" + s] = clamp(periodic(CRAWL_TRI, tl))
    A["delt" + s] = clamp(periodic(CRAWL_DELT, tl))


class CatchUp(Exercise):
    slug = "02-crawl-rattrape"
    number = 2
    title = "Crawl rattrapé"
    subtitle = "Un bras attend devant que l'autre ait terminé son cycle : on décompose le mouvement de bras."
    period = 5.0
    frames = 40
    views = [("side", 20, 480), ("front", 510, 230), ("topv", 750, 230)]
    view_h = 330
    strip = ("side", None, [(0.04, "Appui"), (0.14, "Traction"), (0.26, "Poussée"), (0.38, "Retour aérien"), (0.475, "Entrée")], 0.5)
    phases = [
        (a / 2 + off, b / 2 + off, "%s · %s" % (side, n), d)
        for off, side in ((0.0, "Bras droit"), (0.5, "Bras gauche"))
        for a, b, n, d in CRAWL_PHASES
    ]
    muscles = [
        ("lat", "Grand dorsal", "red", "traction : le moteur du crawl"),
        ("tri", "Triceps", "yellow", "poussée finale vers la cuisse"),
        ("delt", "Deltoïdes (épaules)", "teal", "retour aérien et entrée"),
        ("core", "Gainage", "violet", "rotation épaules + bassin en bloc"),
    ]
    tips = [
        "Le bras devant reste allongé et « attend » : ne pas le laisser couler.",
        "Pendant la traction, garder le coude plus haut que la main.",
        "Le corps pivote d'un bloc (épaules + bassin) autour de la colonne.",
        "Regard vers le fond, battements réguliers pour garder l'équilibre.",
    ]
    muscle_items = [
        ("core", "core", "core", "torso"),
        ("latL", "lat", "latL", "torso"),
        ("latR", "lat", "latR", "torso"),
        ("deltL", "delt", "deltL", "armL"),
        ("deltR", "delt", "deltR", "armR"),
        ("triL", "tri", "triL", "armL"),
        ("triR", "tri", "triR", "armR"),
    ]
    trails = [("handR", ("side", "front", "topv"))]
    arrows = [("fAR", "fBR", "fR", ("side", "topv")), ("fAL", "fBL", "fL", ("side", "topv"))]
    n_bubbles = 4

    def pose(self, t):
        P, A = {}, {}
        roll = periodic(CRAWL_ROLL, t)
        body = Body(origin=(0.0, 0.0, -0.04), roll=roll)
        leg_body = Body(origin=(0.0, 0.0, -0.04), roll=roll * 0.6)
        torso_points(P, body, leg_body)
        crawl_arm(P, A, body, "R", t * 2.0 if t < 0.5 else 0.0)
        crawl_arm(P, A, body, "L", (t - 0.5) * 2.0 if t >= 0.5 else 0.0)
        for s in "LR":
            leg_points(P, A, leg_body, s, 3 * t + (0.5 if s == "L" else 0.0), amp=0.8)
        for k in ("lat", "tri", "delt"):
            A[k] = max(A[k + "L"], A[k + "R"])
        A["core"] = 0.45 + 0.35 * abs(math.sin(math.radians(roll * 2.4)))
        set_head(P, (HEAD_X, 0.0, -0.03), (0.3, 0.0, -1.0))
        bubbles(P, A, self.n_bubbles, t, 1.0, 2.5)
        return P, A


# --------------------------------------------------------------------------
# 3. Battements sur le côté + respiration
# --------------------------------------------------------------------------

HEAD_TURN = [(0.0, 0.0), (0.52, 0.0), (0.66, -100.0), (0.84, -100.0), (0.97, 0.0)]


class SideKickBreath(Exercise):
    slug = "03-battements-cote-respiration"
    number = 3
    title = "Battements sur le côté + respiration"
    subtitle = "Trouver l'équilibre sur le côté et inspirer en tournant la tête, sans jamais la lever."
    period = 6.0
    frames = 48
    views = [("front34", 20, 400), ("top", 430, 550)]
    view_h = 320
    strip = ("front34", None, [(0.25, "Expiration"), (0.59, "Rotation"), (0.75, "Inspiration"), (0.92, "Retour")], 1.0)
    phases = [
        (0.00, 0.52, "Expiration dans l'eau", "Visage tourné vers le fond, on souffle en continu par le nez et la bouche. Les jambes battent."),
        (0.52, 0.66, "Rotation de la tête", "La tête pivote dans l'axe du corps, comme sur une broche : elle ne se soulève pas."),
        (0.66, 0.84, "Inspiration", "La bouche sort au ras de l'eau, un œil reste dans l'eau. Inspiration courte et rapide."),
        (0.84, 1.00, "Retour du visage", "Le visage revient vers le fond ; le corps reste sur le côté, épaule du haut hors de l'eau."),
    ]
    muscles = [
        ("core", "Gainage latéral (obliques)", "violet", "tenir l'équilibre sur le côté"),
        ("quad", "Jambes (quadriceps, fessiers)", "red", "battements continus"),
        ("neck", "Cou (rotation de la tête)", "teal", "mobilité, sans crispation"),
    ]
    tips = [
        "Bras du bas tendu devant, la tête repose dessus ; bras du haut le long du corps.",
        "Tourner la tête avec le corps, sans la lever : un œil reste dans l'eau.",
        "Souffler tout l'air dans l'eau pour n'avoir plus qu'à inspirer.",
        "Changer de côté à chaque longueur pour préparer la respiration bilatérale.",
    ]
    muscle_items = [
        ("quadL", "quad", "legL_act", "legL"),
        ("quadR", "quad", "legR_act", "legR"),
        ("hamL", "quad", "legL_act", "legL"),
        ("hamR", "quad", "legR_act", "legR"),
        ("core", "core", "core", "torso"),
        ("neck", "neck", "neck", "neck"),
    ]
    n_bubbles = 6
    bubble_views = ("front34", "top")

    def pose(self, t):
        P, A = {}, {}
        body = Body(origin=(0.0, 0.0, -0.05), roll=-72.0)  # couché sur le côté gauche
        torso_points(P, body)
        # bras du bas tendu devant, sous la tête (direction donnée dans le repère monde)
        fwd = rotx(normalize((1.0, 0.03, -0.16)), 72.0)
        straight_arm(P, body, "L", (fwd[0], fwd[1], fwd[2]))
        straight_arm(P, body, "R", (-1.0, -0.02, 0.1))
        P["v_handbackR"] = body.d((0.0, -1.0, 0.0))
        for s in "LR":
            leg_points(P, A, body, s, 3 * t + (0.5 if s == "L" else 0.0))
            A["leg%s_act" % s] = max(A["quad" + s], A["ham" + s]) * 0.85
        gamma = periodic(HEAD_TURN, t)
        k = gamma / -100.0
        face = rotx(normalize((0.2, 0.0, -1.0)), gamma)
        head = add(body.w((HEAD_X, 0.0, 0.0)), (0.0, -0.02 * k, 0.07 + 0.02 * k))
        set_head(P, head, face)
        tm = t % 1.0
        bubbles(P, A, self.n_bubbles, t, (1.0 if gamma > -20 else 0.0) * (1 - smooth_step(0.46, 0.52, tm)), 3.0)
        A["quad"] = max(A["legL_act"], A["legR_act"])
        A["neck"] = 0.1 + 0.9 * max(
            smooth_step(0.5, 0.56, tm) * (1 - smooth_step(0.64, 0.7, tm)),
            smooth_step(0.84, 0.88, tm) * (1 - smooth_step(0.95, 1.0, tm)),
        )
        A["core"] = 0.8 + 0.1 * math.sin(6 * math.pi * t)
        return P, A


# --------------------------------------------------------------------------
# 4. Godille
# --------------------------------------------------------------------------


class Sculling(Exercise):
    slug = "04-godille"
    number = 4
    title = "Godille avant"
    subtitle = "Sentir l'appui de l'eau sur les mains : la base d'une bonne prise d'eau en crawl."
    period = 2.4
    frames = 40
    views = [("top", 20, 560), ("front", 590, 390)]
    view_h = 300
    strip = ("front", None, [(0.0, "Mains rapprochées"), (0.25, "Balayage extérieur"), (0.5, "Mains écartées"), (0.75, "Balayage intérieur")], 1.0)
    phases = [
        (0.00, 0.50, "Balayage vers l'extérieur", "Paumes inclinées d'environ 45° vers l'extérieur, les mains s'écartent jusqu'à la largeur des épaules."),
        (0.50, 1.00, "Balayage vers l'intérieur", "Les paumes pivotent vers l'intérieur et les mains se rapprochent. Les flèches montrent l'appui obtenu."),
    ]
    muscles = [
        ("fore", "Avant-bras & poignets", "red", "maintien de l'inclinaison des mains"),
        ("delt", "Deltoïdes & coiffe des rotateurs", "teal", "balayage vers l'extérieur"),
        ("pec", "Pectoraux", "yellow", "balayage vers l'intérieur"),
        ("core", "Gainage", "violet", "corps horizontal, jambes immobiles"),
    ]
    tips = [
        "Bras presque tendus devant, mains juste sous la surface, coudes souples.",
        "Les mains dessinent un « ∞ » aplati, paumes inclinées d'environ 45°.",
        "Chercher la sensation que l'eau « porte » les mains, comme une godille.",
        "Pull-buoy entre les cuisses pour isoler le travail des bras.",
    ]
    muscle_items = [
        ("core", "core", "core", "torso"),
        ("pecL", "pec", "pec", "torso"),
        ("pecR", "pec", "pec", "torso"),
        ("foreL", "fore", "fore", "armL"),
        ("foreR", "fore", "fore", "armR"),
        ("deltL", "delt", "delt", "armL"),
        ("deltR", "delt", "delt", "armR"),
    ]
    props = [("buoy", "mid")]
    trails = [("wristR", ("top", "front")), ("wristL", ("top", "front"))]
    arrows = [("liftAL", "liftBL", "lift", ("front",)), ("liftAR", "liftBR", "lift", ("front",))]

    def pose(self, t):
        P, A = {}, {}
        body = Body(origin=(0.0, 0.0, -0.03))
        torso_points(P, body)
        sweep = 0.5 - 0.5 * math.cos(2 * math.pi * t)
        pitch = math.radians(42.0 * clamp(math.sin(2 * math.pi * t) * 4, -1, 1))
        for s, sy in SIDES.items():
            sh = (SH_X, sy * SH_W, 0.0)
            wr = (SH_X + 0.5, sy * (0.07 + 0.25 * sweep), -0.16 + 0.03 * math.sin(2 * math.pi * t))
            el = two_bone_ik(sh, wr, UA, FA, (0.0, sy, 0.6))
            tip = add(wr, mul(normalize((1.0, sy * 0.1, 0.05)), HAND))
            P["elbow" + s], P["wrist" + s], P["hand" + s] = body.w(el), body.w(wr), body.w(tip)
            n = normalize((0.0, sy * math.sin(pitch), -math.cos(pitch)))  # direction de la paume
            P["v_handback" + s] = mul(n, -1)
            c = lerp(wr, tip, 0.45)
            P["liftA" + s] = body.w(c)
            P["liftB" + s] = body.w(add(c, mul(n, -0.26)))
        for s in "LR":
            leg_points(P, A, body, s, 0.0, still=(3.0, 2.0))
        out = math.sin(2 * math.pi * t)
        A["delt"] = clamp(0.25 + 0.75 * out)
        A["pec"] = clamp(0.25 - 0.75 * out)
        A["fore"] = 0.75 + 0.2 * abs(out)
        A["lift"] = 0.35 + 0.65 * abs(clamp(out * 2, -1, 1))
        A["core"] = 0.35
        set_head(P, body.w((HEAD_X, 0.0, 0.02)), (0.3, 0.0, -1.0))
        return P, A

    def prop_tubes(self, P):
        c = lerp(mid3(P["hipL"], P["hipR"]), mid3(P["kneeL"], P["kneeR"]), 0.3)
        return {"buoy": capped(segment(add(c, (0.0, -0.11, 0.0)), add(c, (0.0, 0.11, 0.0)), PROF_BUOY, (0.0, 0.0, 1.0)))}


def mid3(a, b):
    return lerp(a, b, 0.5)


EXERCISES = [KickBoard(), CatchUp(), SideKickBreath(), Sculling()]
