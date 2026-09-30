"""Rendu SVG animé (SMIL) des exercices, dans la DA de CoachLM."""

import math
from html import escape

from shapely.geometry import MultiPoint
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from model import SURFACE_Z, add, clamp, cross, dot, mul, normalize, body_tubes, muscle_tubes

# --------------------------------------------------------------------------
# DA CoachLM (frontend/src/assets/base.scss)
# --------------------------------------------------------------------------

ACCENT = "#f3722c"
ACCENT_DARK = "#a54d21"
INDIGO = "#2c3e50"
TEXT_1 = "#1a202c"
TEXT_2 = "#4a5568"
TEXT_3 = "#718096"
FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif"

MUSCLE_COLORS = {"red": "#d7263d", "yellow": "#f2b705", "teal": "#159a8c", "violet": "#7b5ea7"}

STYLE = """
.bg{fill:#ffffff}.card{fill:#f8f9fa}.frame{fill:none;stroke:rgba(0,0,0,.1)}
.pool{fill:#e4eef6}.pooltop{fill:#d6e6f2}.laneline{fill:#2c3e50;opacity:.12}
.t1{fill:#1a202c}.t2{fill:#4a5568}.t3{fill:#718096}.track{fill:#e9ecef}.div{stroke:rgba(0,0,0,.08)}
.chip{fill:#ffffff;stroke:rgba(0,0,0,.1)}.water{fill:#2f7fc1;opacity:.13}.surf{stroke:#2f7fc1}
.trail{stroke:#2c3e50}
@media (prefers-color-scheme: dark){
.bg{fill:#222222}.card{fill:#282828}.frame{stroke:rgba(84,84,84,.65)}
.pool{fill:#1d2b37}.pooltop{fill:#22364a}.laneline{fill:#e9ecef;opacity:.1}
.t1{fill:#ffffff}.t2{fill:#f8f9fa}.t3{fill:#c9ced6}.track{fill:#3a3a3a}.div{stroke:rgba(84,84,84,.65)}
.chip{fill:#222222;stroke:rgba(84,84,84,.65)}.water{fill:#3d8fd6;opacity:.22}.surf{stroke:#5aa6e6}
.trail{stroke:#e9ecef}}
"""

GRADIENTS = {
    "skinN": ("#f4d0b1", "#d49b76"),
    "skinF": ("#d9ad8c", "#ad7a58"),
    "suitN": ("#3f5a75", "#1f2d3b"),
    "suitF": ("#30465c", "#18222d"),
    "cap": ("#f68a4e", "#d85a1c"),
    "prop": ("#f79a63", "#e0601f"),
}
SKIN_STROKE = "#8a5a3f"
SUIT_STROKE = "#141d27"

VIEW_LABELS = {"side": "Vue de côté", "top": "Vue de dessus", "topv": "Vue de dessus", "front": "Vue de face"}
VIEW_HINTS = {"side": "sens de nage →", "top": "sens de nage →", "topv": "sens de nage ↑", "front": "le nageur arrive vers vous"}
CAM = {"side": (0, -1, 0), "top": (0, 0, 1), "topv": (0, 0, 1), "front": (1, 0, 0)}


def _cam(az, el):
    """Caméra libre : az = rotation depuis l'avant vers la droite du nageur, el = plongée (degrés)."""
    a, e = math.radians(az), math.radians(el)
    c = (math.cos(e) * math.cos(a), -math.cos(e) * math.sin(a), math.sin(e))
    right = normalize(cross(mul(c, -1), (0.0, 0.0, 1.0)))
    up = cross(right, mul(c, -1))
    return c, right, up


FREE_CAMS = {"front34": _cam(40, 0)}  # à hauteur d'eau : la surface reste une ligne
VIEW_LABELS["front34"] = "Vue 3/4 avant"
VIEW_HINTS["front34"] = "le nageur arrive vers vous"
CAM["front34"] = FREE_CAMS["front34"][0]


def project(view, p):
    x, y, z = p
    if view in FREE_CAMS:
        c, right, up = FREE_CAMS[view]
        return dot(p, right), -dot(p, up), dot(p, c)
    if view == "side":
        return x, -z, -y
    if view == "top":
        return x, -y, z
    if view == "topv":
        return -y, -x, z
    if view == "front":
        return y, -z, x
    raise ValueError(view)


def fmt(v):
    s = "%.1f" % v
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


class Anim:
    def __init__(self, dur):
        self.dur = dur

    def linear(self, attr, values):
        vals = list(values) + [values[0]]
        if len(set(vals)) == 1:
            return ""
        return '<animate attributeName="%s" dur="%ss" repeatCount="indefinite" values="%s"/>' % (attr, self.dur, ";".join(vals))

    def discrete(self, attr, values):
        n = len(values)
        kv, kt = [], []
        for i, v in enumerate(values):
            if not kv or kv[-1] != v:
                kv.append(v)
                kt.append("%.4f" % (i / n))
        if len(kv) == 1:
            return ""
        return (
            '<animate attributeName="%s" dur="%ss" repeatCount="indefinite" calcMode="discrete" keyTimes="%s" values="%s"/>'
            % (attr, self.dur, ";".join(kt), ";".join(kv))
        )


def wrap(text, max_chars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + len(w) + 1 > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + ([cur] if cur else [])


# --------------------------------------------------------------------------
# Silhouettes
# --------------------------------------------------------------------------


def section_points(view, c, axis, p, a, b, e, n=14):
    l = cross(axis, p)
    base = add(c, mul(p, e))
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n
        q = add(base, add(mul(p, a * math.cos(th)), mul(l, b * math.sin(th))))
        sx, sy, _ = project(view, q)
        pts.append((sx, sy))
    return pts


def silhouette(view, samples):
    prev, parts = None, []
    for s in samples:
        pts = section_points(view, *s)
        parts.append(MultiPoint(pts + (prev or [])).convex_hull)
        prev = pts
    g = unary_union(parts).buffer(0)
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda q: q.area)
    g = orient(g, 1.0)
    return list(g.exterior.coords)[:-1]


def resample(coords, m):
    segs, total = [], 0.0
    n = len(coords)
    for i in range(n):
        a, b = coords[i], coords[(i + 1) % n]
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        segs.append((a, b, total, d))
        total += d
    out, j = [], 0
    for k in range(m):
        s = total * k / m
        while j < n - 1 and segs[j][2] + segs[j][3] < s:
            j += 1
        a, b, s0, d = segs[j]
        t = (s - s0) / d if d else 0.0
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def align_contours(contours, m):
    """Rééchantillonne chaque contour sur m points et choisit le point de départ
    qui minimise le déplacement d'une image à l'autre (boucle comprise)."""
    dense_k = 4
    dense = [resample(c, m * dense_k) for c in contours]
    nd = m * dense_k
    shifts = [0]
    prev = [dense[0][i * dense_k] for i in range(m)]

    def best_shift(d, ref, around=None):
        cands = range(0, nd, dense_k) if around is None else range(around - 2 * dense_k, around + 2 * dense_k + 1)
        best, bs = None, 0
        for s in cands:
            cost = 0.0
            for i in range(0, m, 2):
                q = d[(s + i * dense_k) % nd]
                r = ref[i]
                cost += (q[0] - r[0]) ** 2 + (q[1] - r[1]) ** 2
            if best is None or cost < best:
                best, bs = cost, s
        return bs

    for f in range(1, len(dense)):
        s = best_shift(dense[f], prev)
        s = best_shift(dense[f], prev, s)
        shifts.append(s)
        prev = [dense[f][(s + i * dense_k) % nd] for i in range(m)]
    # correction de dérive pour boucler proprement
    s0 = best_shift(dense[0], prev)
    s0 = best_shift(dense[0], prev, s0)
    drift = ((s0 + nd // 2) % nd) - nd // 2
    out = []
    nf = len(dense)
    for f in range(nf):
        s = int(round(shifts[f] - drift * f / nf))
        out.append([dense[f][(s + i * dense_k) % nd] for i in range(m)])
    return out


# --------------------------------------------------------------------------
# Exercice
# --------------------------------------------------------------------------


class Exercise:
    slug = ""
    number = 0
    title = ""
    subtitle = ""
    period = 2.0
    frames = 48
    views = []  # (vue, x, largeur[, points à cadrer, étiquette])
    view_h = 320
    strip = None  # (vue, points à cadrer ou None, [(t, nom)], modulo)
    phases = []  # (début, fin, nom, description)
    muscles = []  # (clé, nom, couleur, note)
    tips = []
    muscle_items = []  # (tube musculaire, clé muscle, clé activation, groupe)
    props = []  # (tube, groupe/couche)
    trails = []  # (point, vues)
    arrows = []  # (a, b, clé activation, vues)
    n_bubbles = 0
    bubble_views = ("side", "front")

    def pose(self, t):
        raise NotImplementedError

    def prop_tubes(self, P):
        return {}

    def muscle_color(self, key):
        for k, _, col, _ in self.muscles:
            if k == key:
                return MUSCLE_COLORS[col]
        return MUSCLE_COLORS["red"]

    # ----------------------------------------------------------------------
    def render(self):
        self.an = Anim(self.period)
        self.data = [self.pose(i / self.frames) for i in range(self.frames)]
        self.tubes = [self.tubes_of(P) for P, _ in self.data]

        W = 1000
        self.vy, self.vh = 92, self.view_h
        self.sy = self.vy + self.vh + 14
        self.sh = 150 if self.strip else 0
        self.y0 = self.sy + self.sh + (34 if self.strip else 20)
        self.ky = self.y0 + max(132, 26 + 36 * len(self.muscles)) + 22
        H = self.ky + 24 + 38 * 2
        o = [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" font-family="%s" role="img" aria-labelledby="t d">'
            % (W, H, W, H, FONT),
            "<title id=\"t\">%s</title><desc id=\"d\">%s</desc>" % (escape(self.title), escape(self.subtitle)),
            "<style>%s</style>" % STYLE.replace("\n", ""),
            "<defs>",
        ]
        for gid, (c1, c2) in GRADIENTS.items():
            o.append(
                '<linearGradient id="%s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>'
                % (gid, c1, c2)
            )
        for name, col in MUSCLE_COLORS.items():
            o.append(
                '<radialGradient id="mg-%s" cx=".5" cy=".5" r=".55"><stop offset="0" stop-color="%s" stop-opacity=".95"/>'
                '<stop offset=".65" stop-color="%s" stop-opacity=".7"/><stop offset="1" stop-color="%s" stop-opacity=".25"/></radialGradient>'
                % (name, col, col, col)
            )
        o.append("</defs>")
        o.append('<rect class="bg" width="%d" height="%d"/>' % (W, H))
        o.append('<rect width="%d" height="6" fill="%s"/>' % (W, ACCENT))
        o.append('<text x="28" y="46" font-size="25" font-weight="700" class="t1">%s</text>' % escape(self.title))
        o.append('<text x="28" y="71" font-size="14.5" class="t2">%s</text>' % escape(self.subtitle))
        pill = "Natation · Éducatif %d" % self.number
        pw = 26 + 7.4 * len(pill)
        o.append('<rect x="%s" y="24" width="%s" height="32" rx="5" fill="%s" stroke="%s"/>' % (fmt(W - 28 - pw), fmt(pw), ACCENT, ACCENT_DARK))
        o.append(
            '<text x="%s" y="45" font-size="13.5" font-weight="600" fill="#ffffff" text-anchor="middle">%s</text>' % (fmt(W - 28 - pw / 2), pill)
        )
        for v in self.views:
            view, vx, vw = v[:3]
            o.extend(self.render_view(view, vx, self.vy, vw, self.vh, *v[3:]))
        if self.strip:
            o.extend(self.render_strip(W))
        o.extend(self.render_info(W))
        o.append("</svg>")
        return "\n".join(o)

    # ----------------------------------------------------------------------
    def render_strip(self, W):
        view, fit, thumbs, mod = self.strip
        n = len(thumbs)
        gap = 10
        tw = (W - 40 - gap * (n - 1)) / n
        full_data, full_tubes = self.data, self.tubes
        o = []
        # cadrage commun à toutes les vignettes
        poses = [self.pose(t) for t, _ in thumbs]
        tubes = [self.tubes_of(P) for P, _ in poses]
        box = self.fit_box(view, poses, tubes, fit)
        for i, ((t, name), pose, tb) in enumerate(zip(thumbs, poses, tubes)):
            x = 20 + i * (tw + gap)
            self.data, self.tubes = [pose], [tb]
            o.extend(self.render_view(view, x, self.sy, tw, self.sh, fit, "%d · %s" % (i + 1, name), box=box, thumb=True))
            self.data, self.tubes = full_data, full_tubes
            # vignette active
            def cyc(a, b):
                d = abs(a - b) % mod
                return min(d, mod - d)
            vis = []
            for f in range(self.frames):
                tf = (f / self.frames) % mod
                best = min(range(n), key=lambda j: cyc(tf, thumbs[j][0] % mod))
                vis.append("1" if best == i else "0")
            o.append(
                '<rect x="%s" y="%d" width="%s" height="%d" rx="5" fill="none" stroke="%s" stroke-width="2.5" opacity="%s">%s</rect>'
                % (fmt(x), self.sy, fmt(tw), self.sh, ACCENT, vis[0], self.an.discrete("opacity", vis))
            )
        return o

    def tubes_of(self, P):
        T = body_tubes(P)
        MT = muscle_tubes(P)
        T.update({k: v[0] for k, v in MT.items()})
        T.update(self.prop_tubes(P))
        return (T, {k: v[1] for k, v in MT.items()})

    def tube_keys(self):
        keys = set(["torso", "neck", "head", "cap", "armL", "armR", "legL", "legR", "suitL", "suitR"])
        return keys | {m[0] for m in self.muscle_items} | {p[0] for p in self.props}

    def fit_box(self, view, data, tubes, fit):
        if fit:
            xs = [project(view, P[k])[0] for P, _ in data for k in fit]
            ys = [project(view, P[k])[1] for P, _ in data for k in fit]
            pad = 0.1
        else:
            xs, ys = [], []
            for T, _ in tubes:
                for k in self.tube_keys():
                    for c, ax, p, a, b, e in T[k]:
                        sx, sy, _ = project(view, c)
                        r = max(a, b) + abs(e)
                        xs += [sx - r, sx + r]
                        ys += [sy - r, sy + r]
            pad = 0.03
        return min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad

    def render_view(self, view, vx, vy, vw, vh, fit=None, label=None, box=None, thumb=False):
        an = self.an
        nf = len(self.data)
        o = []
        cid = "clip-%s-%d-%d" % (view, vx, vy)

        # silhouettes (unités monde projetées)
        keys = self.tube_keys()
        sil = {k: [silhouette(view, T[k]) for T, _ in self.tubes] for k in keys}

        # cadrage
        minx, maxx, miny, maxy = box or self.fit_box(view, self.data, self.tubes, fit)
        top, bottom = (38, 8) if thumb else (40, 16)
        sc = min((vw - 30) / (maxx - minx), (vh - top - bottom) / (maxy - miny))
        cx = vx + vw / 2 - sc * (minx + maxx) / 2
        cy = vy + top + (vh - top - bottom) / 2 - sc * (miny + maxy) / 2

        def S(p):
            sx, sy, _ = project(view, p)
            return cx + sx * sc, cy + sy * sc

        def D(p):
            return project(view, p)[2]

        def poly_path(pts, close=True):
            return "M" + " ".join("%s %s" % (fmt(x), fmt(y)) for x, y in pts) + (" Z" if close else "")

        def smooth_path(pts):
            n = len(pts)
            mids = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
            d = ["M%s %s" % (fmt(mids[-1][0]), fmt(mids[-1][1]))]
            for i in range(n):
                d.append("Q%s %s %s %s" % (fmt(pts[i][0]), fmt(pts[i][1]), fmt(mids[i][0]), fmt(mids[i][1])))
            return "".join(d) + "Z"

        def shape(key, m, attrs, ops=None):
            conts = align_contours([[(cx + x * sc, cy + y * sc) for x, y in c] for c in sil[key]], m)
            ds = [smooth_path(c) for c in conts]
            extra = ""
            if ops is not None:
                attrs += ' opacity="%s"' % ops[0]
                extra = an.linear("opacity", ops)
            return '<path d="%s" %s>%s%s</path>' % (ds[0], attrs, an.linear("d", ds), extra)

        def body_attrs(kind, near):
            if kind == "skin":
                return 'fill="url(#skin%s)" stroke="%s" stroke-opacity=".55" stroke-width="1" stroke-linejoin="round"' % (
                    "N" if near else "F",
                    SKIN_STROKE,
                )
            return 'fill="url(#suit%s)" stroke="%s" stroke-opacity=".7" stroke-width="1" stroke-linejoin="round"' % ("N" if near else "F", SUIT_STROKE)

        def muscle_svg(item):
            key, muscle, act, _ = item
            col = self.muscle_color(muscle)
            ops = []
            for (P, A), (_, vis_dirs) in zip(self.data, self.tubes):
                vd = vis_dirs.get(key)
                vis = 1.0 if vd is None else clamp(0.55 + 1.3 * dot(normalize(vd), CAM[view]))
                ops.append("%.2f" % ((0.1 + 0.78 * clamp(A[act])) * vis))
            gid = "mg-" + [k for k, c in MUSCLE_COLORS.items() if c == col][0]
            return shape(key, 26, 'fill="url(#%s)" stroke="%s" stroke-width=".8" stroke-opacity=".5"' % (gid, col), ops)

        def prop_svg(key):
            return shape(key, 30, 'fill="url(#prop)" stroke="%s" stroke-width="1.2" stroke-linejoin="round"' % ACCENT_DARK)

        o.append('<clipPath id="%s"><rect x="%d" y="%d" width="%d" height="%d" rx="5"/></clipPath>' % (cid, vx, vy, vw, vh))
        o.append('<g clip-path="url(#%s)">' % cid)
        surf_y = cy - SURFACE_Z * sc
        if view in ("top", "topv"):
            o.append('<rect class="pool" x="%d" y="%d" width="%d" height="%d"/>' % (vx, vy, vw, vh))
            if view == "top":
                o.append('<rect class="laneline" x="%d" y="%s" width="%d" height="%s"/>' % (vx, fmt(cy - 0.08 * sc), vw, fmt(0.16 * sc)))
            else:
                o.append('<rect class="laneline" x="%s" y="%d" width="%s" height="%d"/>' % (fmt(cx - 0.08 * sc), vy, fmt(0.16 * sc), vh))
        else:
            o.append('<rect class="card" x="%d" y="%d" width="%d" height="%d"/>' % (vx, vy, vw, vh))
            o.append('<rect class="pool" x="%d" y="%s" width="%d" height="%s"/>' % (vx, fmt(surf_y), vw, fmt(vy + vh - surf_y)))

        for pt, views in self.trails:
            if view in views:
                pts = [S(P[pt]) for P, _ in self.data]
                o.append(
                    '<path class="trail" d="%s" fill="none" stroke-width="1.6" stroke-dasharray="1 5" stroke-linecap="round" opacity=".55"/>'
                    % poly_path(pts)
                )

        torso_depth = [sum(D(P[k]) for k in ("shL", "shR", "hipL", "hipR")) / 4 for P, _ in self.data]
        groups = {
            "armL": ["shL", "elbowL", "wristL", "handL"],
            "armR": ["shR", "elbowR", "wristR", "handR"],
            "legL": ["hipL", "kneeL", "ankleL", "toeL"],
            "legR": ["hipR", "kneeR", "ankleR", "toeR"],
        }
        gdepth = {g: [sum(D(P[k]) for k in pts) / len(pts) for P, _ in self.data] for g, pts in groups.items()}
        near_side = {}
        for g in groups:
            s = g[-1]
            near_side[g] = sum(gdepth[g]) >= sum(gdepth[g[:-1] + ("R" if s == "L" else "L")])

        def group_svg(g, front):
            vis = ["1" if (gdepth[g][f] >= torso_depth[f] - 1e-3) == front else "0" for f in range(nf)]
            if all(v == "0" for v in vis):
                return []
            near = near_side[g]
            out = ['<g opacity="%s">%s' % (vis[0], an.discrete("opacity", vis))]
            out.append(shape(g, 44, body_attrs("skin", near)))
            if g.startswith("leg"):
                out.append(shape("suit" + g[-1], 24, body_attrs("suit", near)))
            for item in self.muscle_items:
                if item[3] == g:
                    out.append(muscle_svg(item))
            for key, layer in self.props:
                if layer == g:
                    out.append(prop_svg(key))
            out.append("</g>")
            return out

        order = sorted(groups, key=lambda g: sum(gdepth[g]))
        for g in order:
            o.extend(group_svg(g, False))
        for key, layer in self.props:
            if layer == "back":
                o.append(prop_svg(key))
        o.append(shape("torso", 44, body_attrs("suit", True)))
        for item in self.muscle_items:
            if item[3] == "torso":
                o.append(muscle_svg(item))
        o.append(shape("neck", 18, body_attrs("skin", True)))
        for item in self.muscle_items:
            if item[3] == "neck":
                o.append(muscle_svg(item))
        o.append(shape("head", 30, body_attrs("skin", True)))
        o.append(shape("cap", 30, 'fill="url(#cap)" stroke="%s" stroke-width="1" stroke-linejoin="round"' % ACCENT_DARK))
        o.extend(self.goggles(view, S))
        for key, layer in self.props:
            if layer == "mid":
                o.append(prop_svg(key))
        for g in order:
            o.extend(group_svg(g, True))
        for key, layer in self.props:
            if layer == "front":
                o.append(prop_svg(key))

        if view in self.bubble_views:
            for i in range(0 if thumb else self.n_bubbles):
                cs = [S(P["bub%d" % i]) for P, _ in self.data]
                ops = ["%.2f" % (0.85 * A["bub%d" % i]) for _, A in self.data]
                rs = [fmt(A["bubr%d" % i] * sc) for _, A in self.data]
                o.append(
                    '<circle cx="%s" cy="%s" r="%s" fill="#ffffff" fill-opacity=".55" stroke="#4a90c8" stroke-width="1.2" opacity="%s">%s%s%s%s</circle>'
                    % (fmt(cs[0][0]), fmt(cs[0][1]), rs[0], ops[0], an.linear("cx", [fmt(c[0]) for c in cs]),
                       an.linear("cy", [fmt(c[1]) for c in cs]), an.linear("r", rs), an.linear("opacity", ops))
                )

        if view not in ("top", "topv"):
            o.append('<rect class="water" x="%d" y="%s" width="%d" height="%s"/>' % (vx, fmt(surf_y), vw, fmt(vy + vh - surf_y)))
            n = int(vw / 24) + 2
            o.append(
                '<path class="surf" d="M%d %s%s" fill="none" stroke-width="1.8" stroke-linecap="round"/>'
                % (vx - 6, fmt(surf_y), " q6 -2.6 12 0 t12 0" * n)
            )

        for a, b, act, views in self.arrows:
            if view not in views:
                continue
            ds, ops = [], []
            for P, A in self.data:
                p0, p1 = S(P[a]), S(P[b])
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                L = math.hypot(dx, dy) or 1.0
                ux, uy = dx / L, dy / L
                hl = min(9.0, L * 0.5)
                h1 = (p1[0] - ux * hl - uy * hl * 0.6, p1[1] - uy * hl + ux * hl * 0.6)
                h2 = (p1[0] - ux * hl + uy * hl * 0.6, p1[1] - uy * hl - ux * hl * 0.6)
                ds.append(poly_path([p0, p1], False) + " " + poly_path([h1, p1, h2], False))
                ops.append("%.2f" % clamp(A[act]))
            o.append(
                '<path d="%s" stroke="%s" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="%s">%s%s</path>'
                % (ds[0], INDIGO, ops[0], an.linear("d", ds), an.linear("opacity", ops))
            )
        o.append("</g>")

        o.append('<rect class="frame" x="%d" y="%d" width="%d" height="%d" rx="5"/>' % (vx, vy, vw, vh))
        lab = label or VIEW_LABELS[view]
        o.append('<rect class="chip" x="%d" y="%d" width="%s" height="24" rx="5"/>' % (vx + 10, vy + 10, fmt(18 + 7.3 * len(lab))))
        o.append('<text class="t1" x="%d" y="%d" font-size="12.5" font-weight="600">%s</text>' % (vx + 19, vy + 26, escape(lab)))
        hint = VIEW_HINTS[view]
        if not thumb:
            o.append('<text class="t3" x="%d" y="%d" font-size="12" text-anchor="end">%s</text>' % (vx + vw - 12, vy + vh - 10, escape(hint)))
        return o

    def goggles(self, view, S):
        o = []
        for sgn in (1, -1):
            ds, ops = [], []
            for P, _ in self.data:
                h, f = P["v_headaxis"], P["v_face"]
                lat = cross(h, f)
                n = normalize(add(mul(f, 0.92), mul(lat, 0.38 * sgn)))
                c = add(add(P["head"], mul(h, 0.012)), add(mul(f, 0.088), mul(lat, 0.036 * sgn)))
                u = normalize(cross(n, h))
                v = cross(n, u)
                pts = []
                for i in range(12):
                    th = 2 * math.pi * i / 12
                    pts.append(S(add(c, add(mul(u, 0.024 * math.cos(th)), mul(v, 0.017 * math.sin(th))))))
                ds.append("M" + " ".join("%s %s" % (fmt(x), fmt(y)) for x, y in pts) + " Z")
                ops.append("%.2f" % clamp((dot(n, CAM[view]) + 0.15) * 4))
            o.append(
                '<path d="%s" fill="#1a202c" stroke="%s" stroke-width="1.6" stroke-linejoin="round" opacity="%s">%s%s</path>'
                % (ds[0], ACCENT, ops[0], self.an.linear("d", ds), self.an.linear("opacity", ops))
            )
        return o

    # ----------------------------------------------------------------------
    def render_info(self, W):
        an, nf = self.an, self.frames
        o = []
        y0 = self.y0
        x0, pw = 28, 572
        o.append('<text class="t3" x="%d" y="%d" font-size="12" font-weight="700" letter-spacing=".08em">PHASE EN COURS</text>' % (x0, y0))
        for i, (a, b, name, desc) in enumerate(self.phases):
            vis = ["1" if a <= f / nf < b else "0" for f in range(nf)]
            o.append('<g opacity="%s">%s' % (vis[0], an.discrete("opacity", vis)))
            o.append(
                '<text x="%d" y="%d" font-size="21" font-weight="700" class="t1"><tspan fill="%s">%d/%d</tspan>  %s</text>'
                % (x0, y0 + 30, ACCENT, i + 1, len(self.phases), escape(name))
            )
            for li, line in enumerate(wrap(desc, 78)[:2]):
                o.append('<text class="t2" x="%d" y="%d" font-size="14">%s</text>' % (x0, y0 + 54 + li * 19, escape(line)))
            o.append("</g>")
        ty = y0 + 102
        o.append('<rect class="track" x="%d" y="%d" width="%d" height="8" rx="4"/>' % (x0, ty, pw))
        for i, (a, b, name, desc) in enumerate(self.phases):
            sx, ex = x0 + a * pw, x0 + b * pw
            vis = ["1" if a <= f / nf < b else "0" for f in range(nf)]
            o.append(
                '<rect x="%s" y="%d" width="%s" height="8" rx="4" fill="%s" opacity="%s">%s</rect>'
                % (fmt(sx + 1), ty, fmt(max(1, ex - sx - 2)), ACCENT, vis[0], an.discrete("opacity", vis))
            )
            if i:
                o.append('<rect class="bg" x="%s" y="%d" width="2" height="8"/>' % (fmt(sx - 1), ty))
            o.append('<text class="t3" x="%s" y="%d" font-size="11" text-anchor="middle">%d</text>' % (fmt((sx + ex) / 2), ty + 24, i + 1))
        o.append(
            '<g><animateTransform attributeName="transform" type="translate" dur="%ss" repeatCount="indefinite" values="0 0;%d 0"/>'
            '<rect x="%s" y="%d" width="4" height="16" rx="2" fill="%s"/></g>' % (self.period, pw, fmt(x0 - 2), ty - 4, INDIGO)
        )
        o.append(
            '<text class="t3" x="%d" y="%d" font-size="12" text-anchor="end">cycle complet : %s s (ralenti)</text>'
            % (x0 + pw, y0, ("%g" % self.period).replace(".", ","))
        )

        lx = 636
        o.append('<text class="t3" x="%d" y="%d" font-size="12" font-weight="700" letter-spacing=".08em">MUSCLES SOLLICITÉS</text>' % (lx, y0))
        for i, (k, name, col, note) in enumerate(self.muscles):
            c = MUSCLE_COLORS[col]
            yy = y0 + 24 + i * 36
            acts = [clamp(A.get(k, 0)) for _, A in self.data]
            ws = [fmt(3 + 37 * a) for a in acts]
            o.append('<rect x="%d" y="%d" width="40" height="8" rx="4" class="track"/>' % (lx, yy - 1))
            o.append('<rect x="%d" y="%d" width="%s" height="8" rx="4" fill="%s">%s</rect>' % (lx, yy - 1, ws[0], c, an.linear("width", ws)))
            o.append('<text class="t1" x="%d" y="%d" font-size="14" font-weight="600">%s</text>' % (lx + 52, yy + 7, escape(name)))
            o.append('<text class="t3" x="%d" y="%d" font-size="12.5">%s</text>' % (lx + 52, yy + 23, escape(note)))

        ky = self.ky
        o.append('<line class="div" x1="28" y1="%d" x2="%d" y2="%d" stroke-width="1"/>' % (ky - 24, W - 28, ky - 24))
        o.append('<text class="t3" x="28" y="%d" font-size="12" font-weight="700" letter-spacing=".08em">POINTS CLÉS</text>' % ky)
        colw = (W - 56) / 2
        for i, tip in enumerate(self.tips[:4]):
            tx = 28 + (i % 2) * colw
            tyy = ky + 24 + (i // 2) * 38
            o.append('<rect x="%s" y="%d" width="6" height="6" rx="1.5" fill="%s"/>' % (fmt(tx), tyy - 8, ACCENT))
            for li, line in enumerate(wrap(tip, 66)[:2]):
                o.append('<text class="t1" x="%s" y="%d" font-size="13">%s</text>' % (fmt(tx + 16), tyy + li * 16, escape(line)))
        return o
