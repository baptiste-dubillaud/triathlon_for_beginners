"""Modèle 3D du nageur : géométrie, interpolation et volumes anatomiques.

Repère monde : x = sens de nage, y = gauche du nageur, z = vers le haut.
Chaque partie du corps est un « tube » : une suite de sections elliptiques
(demi-profondeur `a` selon l'axe postérieur, demi-largeur `b` selon l'axe
latéral, décalage `e` vers l'arrière). La silhouette vue sous n'importe quel
angle est l'union des enveloppes convexes de deux sections consécutives.
"""

import math

# --------------------------------------------------------------------------
# Vecteurs
# --------------------------------------------------------------------------


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def normalize(a):
    n = length(a) or 1.0
    return mul(a, 1.0 / n)


def lerp(a, b, t):
    return add(a, mul(sub(b, a), t))


def mid(a, b):
    return lerp(a, b, 0.5)


def orthogonal(v, axis, fallback=(0.0, 0.0, 1.0)):
    """Composante de `v` perpendiculaire à `axis`, normalisée."""
    w = sub(v, mul(axis, dot(v, axis)))
    if length(w) < 1e-4:
        w = sub(fallback, mul(axis, dot(fallback, axis)))
        if length(w) < 1e-4:
            w = cross(axis, (0.0, 1.0, 0.0))
    return normalize(w)


def rotx(p, deg):
    """Rotation autour de x (roulis). deg > 0 : le côté gauche monte."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c)


def ang_dir(deg, backward=False):
    """Direction dans le plan sagittal ; deg > 0 = vers le fond."""
    r = math.radians(deg)
    return ((-1.0 if backward else 1.0) * math.cos(r), 0.0, -math.sin(r))


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def smooth_step(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def two_bone_ik(root, target, l1, l2, pole):
    d = sub(target, root)
    dist = clamp(length(d), 1e-6, l1 + l2 - 1e-6)
    dn = normalize(d)
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    return add(add(root, mul(dn, a)), mul(orthogonal(pole, dn), h))


def periodic(keys, t):
    """Interpolation d'Hermite périodique. keys = [(t, valeur), ...], t dans [0, 1)."""
    t %= 1.0
    n = len(keys)
    ts = [k[0] for k in keys]
    tup = isinstance(keys[0][1], tuple)
    vs = [k[1] if tup else (k[1],) for k in keys]

    def tt(i):
        return ts[i % n] + math.floor(i / n)

    i = max(j for j in range(n) if ts[j] <= t) if t >= ts[0] else -1
    t0, t1, tm, tp = tt(i), tt(i + 1), tt(i - 1), tt(i + 2)
    v0, v1, vm, vp = vs[i % n], vs[(i + 1) % n], vs[(i - 1) % n], vs[(i + 2) % n]
    dt = t1 - t0
    u = (t - t0) / dt
    h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
    h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    out = []
    for c in range(len(v0)):
        m0 = (v1[c] - vm[c]) / (t1 - tm)
        m1 = (vp[c] - v0[c]) / (tp - t0)
        out.append(h00 * v0[c] + h10 * dt * m0 + h01 * v1[c] + h11 * dt * m1)
    return tuple(out) if tup else out[0]


# --------------------------------------------------------------------------
# Squelette
# --------------------------------------------------------------------------

SH_X = 0.50  # bassin -> épaules
SH_W = 0.19  # demi-largeur d'épaules
HIP_W = 0.095  # demi-largeur de bassin
UA, FA, HAND = 0.30, 0.27, 0.18
TH, SHIN, FOOT = 0.44, 0.42, 0.17
HEAD_X = SH_X + 0.22
SURFACE_Z = 0.07

SIDES = {"L": 1.0, "R": -1.0}


class Body:
    """Repère du tronc : origine au centre du bassin, roulis autour de x."""

    def __init__(self, origin=(0.0, 0.0, -0.02), roll=0.0):
        self.origin, self.roll = origin, roll

    def w(self, p):
        return add(self.origin, rotx(p, self.roll))

    def d(self, v):
        return rotx(v, self.roll)


def torso_points(P, body, leg_body=None):
    leg_body = leg_body or body
    for s, sy in SIDES.items():
        P["sh" + s] = body.w((SH_X, sy * SH_W, 0.0))
        P["hip" + s] = leg_body.w((0.0, sy * HIP_W, 0.0))
    P["neck"] = body.w((SH_X, 0.0, 0.0))
    P["v_back"] = body.d((0.0, 0.0, 1.0))
    P["v_legback"] = leg_body.d((0.0, 0.0, 1.0))
    P["v_left"] = body.d((0.0, 1.0, 0.0))


# Battement : (angle de cuisse, flexion du genou) en degrés, > 0 = vers le fond
KICK = [
    (0.00, (-6.0, 4.0)),
    (0.15, (-1.0, 25.0)),
    (0.38, (10.0, 6.0)),
    (0.50, (11.0, 0.0)),
    (0.75, (2.0, 0.0)),
]
QUAD_ACT = [(0.0, 0.25), (0.15, 0.75), (0.32, 1.0), (0.5, 0.3), (0.75, 0.05)]
HAM_ACT = [(0.0, 0.3), (0.15, 0.05), (0.4, 0.05), (0.62, 0.85), (0.82, 0.8)]


def leg_points(P, A, body, s, p, amp=1.0, still=None):
    sy = SIDES[s]
    th, k = still if still is not None else periodic(KICK, p)
    th, k = th * amp, k * amp
    hip = (0.0, sy * HIP_W, 0.0)
    knee = add(hip, mul(ang_dir(th, True), TH))
    ankle = add(knee, mul(ang_dir(th - k, True), SHIN))
    toe = add(ankle, mul(ang_dir(th - k + 14, True), FOOT))
    P["knee" + s], P["ankle" + s], P["toe" + s] = body.w(knee), body.w(ankle), body.w(toe)
    if still is None:
        A["quad" + s] = clamp(periodic(QUAD_ACT, p)) * amp
        A["ham" + s] = clamp(periodic(HAM_ACT, p)) * amp
    else:
        A["quad" + s] = A["ham" + s] = 0.0


def straight_arm(P, body, s, direction):
    sy = SIDES[s]
    sh = (SH_X, sy * SH_W, 0.0)
    d = normalize((direction[0], sy * direction[1], direction[2]))
    el = add(sh, mul(d, UA))
    wr = add(el, mul(d, FA))
    P["elbow" + s], P["wrist" + s], P["hand" + s] = body.w(el), body.w(wr), body.w(add(wr, mul(d, HAND)))


def set_head(P, center, face, axis=(1.0, 0.0, 0.0)):
    P["head"] = center
    P["v_headaxis"] = normalize(axis)
    P["v_face"] = orthogonal(face, P["v_headaxis"])


def bubbles(P, A, n, t, on=1.0, speed=1.0):
    face, head = P["v_face"], P["head"]
    mouth = add(add(head, mul(face, 0.09)), mul(P["v_headaxis"], -0.05))
    for i in range(n):
        ph = (t * speed + i / n) % 1.0
        rise = ph * max(0.05, SURFACE_Z - mouth[2] + 0.02)
        P["bub%d" % i] = add(mouth, (-0.22 * ph, 0.03 * math.sin(ph * 11 + i * 2), rise))
        A["bub%d" % i] = on * smooth_step(0.0, 0.08, ph) * (1 - smooth_step(0.78, 1.0, ph))
        A["bubr%d" % i] = 0.011 + 0.016 * ph


# --------------------------------------------------------------------------
# Volumes
# --------------------------------------------------------------------------

# profils (u, a, b, e) le long d'un segment ; a = demi-profondeur, b = demi-largeur,
# e = décalage vers l'arrière (e < 0 : vers l'avant du corps)
PROF_TORSO = [
    (0.00, 0.105, 0.160, 0.018),
    (0.18, 0.100, 0.150, 0.004),
    (0.45, 0.092, 0.132, -0.004),
    (0.70, 0.112, 0.158, -0.014),
    (0.88, 0.106, 0.180, -0.006),
    (1.00, 0.080, 0.150, 0.000),
]
PROF_NECK = [(0.0, 0.055, 0.058, 0.0), (1.0, 0.048, 0.048, 0.0)]
PROF_HEAD = [
    (0.00, 0.050, 0.046, -0.012),
    (0.20, 0.080, 0.066, -0.014),
    (0.45, 0.098, 0.076, -0.008),
    (0.70, 0.097, 0.077, 0.002),
    (0.90, 0.074, 0.064, 0.006),
    (1.00, 0.036, 0.036, 0.004),
]
PROF_UA = [(0.0, 0.056, 0.062, 0.0), (0.22, 0.052, 0.057, 0.0), (0.5, 0.045, 0.047, 0.004), (0.85, 0.037, 0.04, 0.0), (1.0, 0.035, 0.037, 0.0)]
PROF_FA = [(0.0, 0.035, 0.038, 0.0), (0.25, 0.04, 0.045, 0.0), (0.65, 0.03, 0.034, 0.0), (1.0, 0.019, 0.029, 0.0)]
PROF_HAND = [(0.0, 0.016, 0.029, 0.0), (0.35, 0.016, 0.042, 0.0), (0.72, 0.012, 0.039, 0.0), (1.0, 0.007, 0.02, 0.0)]
PROF_TH = [(0.0, 0.086, 0.09, 0.0), (0.3, 0.078, 0.08, -0.006), (0.7, 0.062, 0.062, -0.004), (1.0, 0.05, 0.05, 0.0)]
PROF_SHIN = [(0.0, 0.05, 0.05, 0.0), (0.28, 0.056, 0.048, 0.014), (0.6, 0.042, 0.038, 0.006), (1.0, 0.029, 0.03, 0.0)]
PROF_FOOT = [(0.0, 0.034, 0.033, 0.012), (0.35, 0.025, 0.04, 0.0), (1.0, 0.01, 0.03, 0.0)]


def _interp_prof(prof, u):
    if u <= prof[0][0]:
        return prof[0][1:]
    for (u0, *v0), (u1, *v1) in zip(prof, prof[1:]):
        if u <= u1:
            k = (u - u0) / (u1 - u0)
            return tuple(v0[i] + (v1[i] - v0[i]) * k for i in range(3))
    return prof[-1][1:]


def segment(A, B, prof, pA, pB=None, u0=0.0, u1=1.0, scale=1.0, shift=0.0, step=0.1):
    """Sections d'un segment A->B entre u0 et u1.

    `scale` réduit la section, `shift` la décale vers l'arrière (en fraction de a).
    """
    pB = pB or pA
    axis = normalize(sub(B, A))
    us = sorted({u0, u1} | {u for u, *_ in prof if u0 < u < u1} | {u0 + (u1 - u0) * k * step for k in range(1, int(1 / step))})
    out = []
    for u in us:
        a, b, e = _interp_prof(prof, u)
        p = orthogonal(lerp(pA, pB, u), axis)
        out.append((lerp(A, B, u), axis, p, a * scale, b * scale, e * scale + shift * a))
    return out


def capped(samples, start=True, end=True):
    """Arrondit les extrémités d'un tube."""
    out = list(samples)
    if start:
        c, ax, p, a, b, e = out[0]
        out.insert(0, (sub(c, mul(ax, 0.55 * min(a, b))), ax, p, a * 0.6, b * 0.6, e))
    if end:
        c, ax, p, a, b, e = out[-1]
        out.append((add(c, mul(ax, 0.55 * min(a, b))), ax, p, a * 0.6, b * 0.6, e))
    return out


def hand_back(P, s):
    """Dos de la main : vers le haut et l'avant (paume vers l'arrière pendant la traction)."""
    key = "v_handback" + s
    if key in P:
        return P[key]
    ax = normalize(sub(P["hand" + s], P["wrist" + s]))
    return orthogonal(add(P["v_back"], mul((1.0, 0.0, 0.0), 0.8)), ax)


def body_tubes(P):
    """Tubes standard du nageur : clé -> liste de sections."""
    T = {}
    pc = mid(P["hipL"], P["hipR"])
    sc = P["neck"]
    T["torso"] = capped(segment(pc, sc, PROF_TORSO, P["v_legback"], P["v_back"]), True, False)
    hb = sub(P["head"], mul(P["v_headaxis"], 0.10))
    T["neck"] = segment(sub(sc, mul(normalize(sub(sc, pc)), 0.03)), hb, PROF_NECK, P["v_back"], mul(P["v_face"], -1))
    crown = add(P["head"], mul(P["v_headaxis"], 0.125))
    back_head = mul(P["v_face"], -1)
    T["head"] = segment(hb, crown, PROF_HEAD, back_head)
    # bonnet : couvre le haut et l'arrière du crâne, laisse le visage et les oreilles
    T["cap"] = segment(hb, crown, PROF_HEAD, back_head, u0=0.1, u1=0.5, scale=0.78, shift=0.34) + segment(
        hb, crown, PROF_HEAD, back_head, u0=0.5, scale=1.06, shift=0.03
    )
    for s in "LR":
        sh, el, wr, hd = P["sh" + s], P["elbow" + s], P["wrist" + s], P["hand" + s]
        ua = normalize(sub(el, sh))
        fa = normalize(sub(wr, el))
        bend = sub(fa, mul(ua, dot(fa, ua)))
        p_ua = orthogonal(mul(bend, -1), ua, P["v_back"]) if length(bend) > 0.25 else orthogonal(P["v_back"], ua)
        hb_ = hand_back(P, s)
        T["arm" + s] = capped(
            segment(sh, el, PROF_UA, p_ua)
            + segment(el, wr, PROF_FA, p_ua, hb_)
            + segment(wr, hd, PROF_HAND, hb_),
            True,
            True,
        )
        hp, kn, an, to = P["hip" + s], P["knee" + s], P["ankle" + s], P["toe" + s]
        lb = P["v_legback"]
        T["leg" + s] = capped(
            segment(hp, kn, PROF_TH, lb) + segment(kn, an, PROF_SHIN, lb) + segment(an, to, PROF_FOOT, lb),
            True,
            True,
        )
        # jambe de la trifonction
        T["suit" + s] = capped(segment(hp, kn, PROF_TH, lb, u1=0.42, scale=1.04), True, False)
    return T


def muscle_tubes(P):
    """Volumes musculaires (sous-parties des tubes), avec leur direction visible."""
    M = {}
    lb, back = P["v_legback"], P["v_back"]
    pc = mid(P["hipL"], P["hipR"])
    axis = normalize(sub(P["neck"], pc))
    M["core"] = (segment(pc, P["neck"], PROF_TORSO, lb, back, u0=0.12, u1=0.74, scale=0.78, shift=-0.18), mul(back, -1))
    hb = sub(P["head"], mul(P["v_headaxis"], 0.10))
    M["neck"] = (segment(P["neck"], hb, PROF_NECK, back, scale=1.02), None)
    for s, sy in SIDES.items():
        hp, kn = P["hip" + s], P["knee" + s]
        th = normalize(sub(kn, hp))
        M["quad" + s] = (capped(segment(hp, kn, PROF_TH, lb, u0=0.1, u1=0.86, scale=0.74, shift=-0.27)), mul(lb, -1))
        M["ham" + s] = (capped(segment(hp, kn, PROF_TH, lb, u0=0.05, u1=0.82, scale=0.74, shift=0.27)), lb)
        glute_a = add(add(hp, mul(axis, 0.1)), mul(lb, 0.035))
        glute_b = add(add(hp, mul(th, 0.1)), mul(lb, 0.03))
        M["glute" + s] = (capped(segment(glute_a, glute_b, [(0, 0.06, 0.075, 0.0), (1, 0.05, 0.065, 0.0)], lb)), lb)
        sh, el, wr = P["sh" + s], P["elbow" + s], P["wrist" + s]
        ua = normalize(sub(el, sh))
        fa = normalize(sub(wr, el))
        bend = sub(fa, mul(ua, dot(fa, ua)))
        p_ua = orthogonal(mul(bend, -1), ua, back) if length(bend) > 0.25 else orthogonal(back, ua)
        M["delt" + s] = (capped(segment(sh, el, PROF_UA, p_ua, u0=0.0, u1=0.42, scale=1.05), True, False), None)
        M["tri" + s] = (capped(segment(sh, el, PROF_UA, p_ua, u0=0.3, u1=0.95, scale=0.72, shift=0.28)), p_ua)
        M["fore" + s] = (capped(segment(el, wr, PROF_FA, p_ua, u0=0.04, u1=0.72, scale=0.95)), None)
        lat = mul(P["v_left"], sy)
        la = add(add(sub(P["sh" + s], mul(axis, 0.07)), mul(back, 0.02)), mul(lat, -0.04))
        lbk = add(add(pc, mul(axis, 0.16)), add(mul(lat, 0.07), mul(back, 0.05)))
        M["lat" + s] = (capped(segment(la, lbk, [(0, 0.045, 0.06, 0.0), (0.4, 0.045, 0.065, 0.0), (1, 0.03, 0.035, 0.0)], back)), add(lat, mul(back, 0.6)))
        st = add(sub(P["neck"], mul(axis, 0.1)), mul(back, -0.07))
        pa = add(sub(P["sh" + s], mul(axis, 0.05)), mul(back, -0.045))
        M["pec" + s] = (capped(segment(pa, st, [(0, 0.04, 0.05, 0.0), (1, 0.035, 0.05, 0.0)], back)), mul(back, -1))
    return M
