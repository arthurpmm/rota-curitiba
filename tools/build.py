"""Convert URBS open data (dadosabertos.c3sl.ufpr.br/curitibaurbs) into the compact data.json used by the app.

Usage: python3 -I build.py <raw_dir> <date_prefix> <out.json>
"""
import json, math, sys, collections, re

raw, pref, out = sys.argv[1], sys.argv[2], sys.argv[3]
ld = lambda n: json.load(open(f"{raw}/{pref}_{n}.json", encoding="utf-8"))
LIN, PTS, TAB, SHP = ld("linhas"), ld("pontosLinha"), ld("tabelaLinha"), ld("shapeLinha")

LAT0, LON0 = -25.4296, -49.2713
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110540
f = lambda s: float(s.replace(",", "."))
xy = lambda la, lo: ((lo - LON0) * KX, (la - LAT0) * KY)

SKIP = {"SERVIÇO AOS OPERADORES"}
CAT_COL = {
    "EXPRESSO": ("#d0312d", "#fff"), "LIGEIRÃO": ("#1f5fbf", "#fff"), "LINHA DIRETA": ("#8a9298", "#fff"),
    "INTERBAIRROS": ("#2f9d57", "#fff"), "ALIMENTADOR": ("#ef7d1a", "#fff"), "TRONCAL": ("#e0ad00", "#1b1f1d"),
    "CONVENCIONAL": ("#e0ad00", "#1b1f1d"), "MADRUGUEIRO": ("#3b3f8f", "#fff"), "JARDINEIRA": ("#2b7a78", "#fff"),
}
SPEED = {"EXPRESSO": 21, "LIGEIRÃO": 24, "LINHA DIRETA": 25, "INTERBAIRROS": 19, "MADRUGUEIRO": 24}  # km/h defaults

def title(s):
    small = {"de", "da", "do", "das", "dos", "e"}
    w = s.lower().split(" ")
    roman = re.compile(r"^\(?(i{1,3}|iv|v|vi{1,3}|ix|x)\)?[.,]?$")
    return " ".join(x.upper() if roman.match(x) else (x if (x in small and i) else x[:1].upper() + x[1:]) for i, x in enumerate(w))

import re
def clean(n):
    n = re.sub(r"\s+", " ", n).strip()
    n = re.sub(r",\s*Curitiba\s*-\s*PR.*$", "", n)
    n = re.sub(r"\s+-\s+\d{3}\b.*$", "", n)
    m = re.match(r"^(Terminal\s+[^-\d(]+?)\s*(?:[-\d(].*)?$", n)
    if m: n = m.group(1)
    n = re.sub(r"^Terminal Cic$", "Terminal CIC", n)
    n = n.replace("Estaçaõ", "Estação")
    if n.startswith("Estação"): n = re.sub(r"\s+-\s+.*$", "", n).rstrip(".")
    return n.strip(" -,")

routes, rindex = [], {}
for l in sorted(LIN, key=lambda l: l["COD"]):
    if l["CATEGORIA_SERVICO"] in SKIP: continue
    cat = l["CATEGORIA_SERVICO"]
    col, ink = CAT_COL.get(cat, ("#7a7f86", "#fff"))
    if l["NOME_COR"] == "TURISMO": col, ink = "#2b7a78", "#fff"
    rindex[l["COD"]] = len(routes)
    routes.append([l["COD"], title(l["NOME"]), col, cat, ink])

# ---- stops
stops, sidx = {"n": [], "la": [], "lo": []}, {}
SX, SY = [], []
for p in PTS:
    if p["COD"] not in rindex or p["NUM"] in sidx: continue
    la, lo = f(p["LAT"]), f(p["LON"])
    sidx[p["NUM"]] = len(stops["n"])
    nm = clean(p["NOME"])
    stops["n"].append(nm); stops["la"].append(round(la * 1e5)); stops["lo"].append(round(lo * 1e5))
    x, y = xy(la, lo); SX.append(x); SY.append(y)

# ---- itineraries
itins = collections.defaultdict(list)
for p in PTS:
    if p["COD"] in rindex: itins[(p["COD"], p["ITINERARY_ID"])].append(p)
ITIN = {}
for (cod, iid), ps in itins.items():
    ps.sort(key=lambda p: int(p["SEQ"]))
    seq = [sidx[p["NUM"]] for p in ps]
    # drop immediate duplicates
    s2 = [s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]]
    if len(s2) < 2: continue
    cum = [0.0]
    for a, b in zip(s2, s2[1:]): cum.append(cum[-1] + 1.15 * math.hypot(SX[a] - SX[b], SY[a] - SY[b]))
    head = ps[0]["SENTIDO"].strip() or ""
    head = head.replace("Sentido ", "").strip()
    nums = [p["NUM"] for p in ps if True]
    nums = [n for i, n in enumerate(nums) if i == 0 or n != nums[i - 1]]
    pos = collections.defaultdict(list)
    for i, n in enumerate(nums): pos[n].append(i)
    ITIN[(cod, iid)] = dict(cod=cod, stops=s2, cum=cum, head=head, pos=pos, n=len(s2))
by_line = collections.defaultdict(list)
for k, v in ITIN.items(): by_line[v["cod"]].append(v)

# ---- events per vehicle
tm = lambda h: int(h[:2]) * 3600 + int(h[3:5]) * 60
veh = collections.defaultdict(list)
for t in TAB:
    if t["COD"] not in rindex: continue
    veh[(t["COD"], t["DIA"], t["TABELA"])].append((tm(t["HORA"]), t["NUM"]))
DAYK = {"1": "u", "2": "s", "3": "d"}

patterns = {}   # key -> dict(route, itin, a, b, anchors(tuple of pos), trips{day:[[times...]]})
stats = collections.Counter()
for (cod, dia, tab), ev in veh.items():
    if dia not in DAYK: continue
    ev.sort()
    if ev and ev[-1][0] >= 20 * 3600:
        ev = sorted([(t + 86400 if t < 4 * 3600 else t, s) for t, s in ev])
    cands = by_line.get(cod, [])
    cat = routes[rindex[cod]][3]
    i = 0
    while i < len(ev):
        best = None
        for it in cands:
            if ev[i][1] not in it["pos"]: continue
            for p0 in it["pos"][ev[i][1]]:
                if p0 == it["n"] - 1: continue
                run, last, j = [(p0, ev[i][0])], p0, i + 1
                while j < len(ev):
                    t, s = ev[j]
                    nxt = [p for p in it["pos"].get(s, []) if p > last]
                    if not nxt or nxt[0] == it["n"] - 1 or t - run[-1][1] > 3 * 3600 or t < run[-1][1]: break
                    run.append((nxt[0], t)); last = nxt[0]; j += 1
                score = (len(run), -p0)
                if best is None or score > best[0]: best = (score, it, run, j)
        if best is None:
            stats["unmatched_event"] += 1; i += 1; continue
        _, it, run, j = best
        prev_t = ev[i - 1][0] if i > 0 else None
        next_t = ev[j][0] if j < len(ev) else None
        cum = it["cum"]
        # speed (m/s)
        if len(run) >= 2 and run[-1][1] > run[0][1]:
            v = (cum[run[-1][0]] - cum[run[0][0]]) / (run[-1][1] - run[0][1])
        else:
            v = SPEED.get(cat, 18) / 3.6
        v = min(max(v, 8 / 3.6), 45 / 3.6)
        # forward extension to itinerary end
        anchors = list(run)
        end = it["n"] - 1
        if anchors[-1][0] < end:
            tend = anchors[-1][1] + (cum[end] - cum[anchors[-1][0]]) / v
            if next_t is not None and next_t > anchors[-1][1]:
                tend = min(tend, next_t - 60) if next_t - 60 > anchors[-1][1] else anchors[-1][1] + (next_t - anchors[-1][1]) * 0.9
            anchors.append((end, round(tend)))
        # backward extension if first anchor is not the itinerary start
        if anchors[0][0] > 0:
            tst = anchors[0][1] - cum[anchors[0][0]] / v
            first_tp = min(min(ps) for n, ps in it["pos"].items() if any(n == e[1] for e in ev))
            if anchors[0][0] <= first_tp and (prev_t is None or tst > prev_t):
                anchors.insert(0, (0, round(tst)))
        a, b = anchors[0][0], anchors[-1][0]
        if b <= a: i = j; continue
        key = (id(it), a, b, tuple(p for p, _ in anchors))
        P = patterns.get(key)
        if P is None:
            P = patterns[key] = dict(it=it, a=a, b=b, anc=[p for p, _ in anchors], trips=collections.defaultdict(list))
        P["trips"][DAYK[dia]].append([t for _, t in anchors])
        stats["trips"] += 1
        i = j

# ---- emit patterns
pats = []
for P in patterns.values():
    it = P["it"]; a, b = P["a"], P["b"]
    st = it["stops"][a:b + 1]
    cum = [round(c - it["cum"][a]) for c in it["cum"][a:b + 1]]
    anc = [p - a for p in P["anc"]]
    tt = {}
    for d, trips in P["trips"].items():
        trips.sort()
        # dedupe identical trips
        uniq = []
        for tr in trips:
            if not uniq or uniq[-1] != tr: uniq.append(tr)
        tt[d] = [x for tr in uniq for x in tr]
    pats.append([rindex[it["cod"]], it["head"] or title(st and stops["n"][st[-1]] or ""), st, cum, anc, tt])

# ---- shapes (Douglas-Peucker, 12 m)
def dp(pts, tol):
    if len(pts) < 3: return pts
    keep = [0] * len(pts); keep[0] = keep[-1] = 1
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1e-9
        bi, bd = -1, tol
        for k in range(i + 1, j):
            x, y = pts[k]
            d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / L
            if d > bd: bi, bd = k, d
        if bi >= 0:
            keep[bi] = 1; stack += [(i, bi), (bi, j)]
    return [p for p, k in zip(pts, keep) if k]
sh = collections.defaultdict(list)
for r in SHP:
    if r["COD"] in rindex: sh[(r["COD"], r["SHP"])].append(xy(f(r["LAT"]), f(r["LON"])))
shapes = []
for (cod, s), pts in sh.items():
    pts = dp(pts, 3)
    enc, px, py = [], 0, 0
    for x, y in pts:
        X, Y = round(x), round(y); enc += [X - px, Y - py]; px, py = X, Y
    shapes.append([rindex[cod], enc])

data = dict(gen=f"{pref[8:10]}/{pref[5:7]}/{pref[:4]}", routes=routes, stops=stops, pats=pats, shapes=shapes)
json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(dict(stats), "patterns", len(pats), "stops", len(stops["n"]), "routes", len(routes), "shapes", len(shapes))
