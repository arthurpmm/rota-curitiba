"""Map-match URBS bus shapes onto OpenStreetMap roads so lines sit on the drawn streets."""
import json, math, sys, collections
osmf, dataf = sys.argv[1], sys.argv[2]
LAT0, LON0 = -25.4296, -49.2713
KX, KY = 111320*math.cos(math.radians(LAT0)), 110540
segs = []  # (ax,ay,bx,by,way)
for e in json.load(open(osmf, encoding="utf-8"))["elements"]:
    if e.get("type") != "way" or "highway" not in e.get("tags", {}): continue
    g = [((p["lon"]-LON0)*KX, (p["lat"]-LAT0)*KY) for p in e["geometry"]]
    for a, b in zip(g, g[1:]): segs.append((a[0], a[1], b[0], b[1], e["id"]))
C = 40; grid = collections.defaultdict(list)
for i, (ax, ay, bx, by, w) in enumerate(segs):
    for gx in range(int(min(ax,bx)//C)-1, int(max(ax,bx)//C)+2):
        for gy in range(int(min(ay,by)//C)-1, int(max(ay,by)//C)+2): grid[(gx,gy)].append(i)
MAXD = 15
def cands(x, y):
    out = []
    for i in grid.get((int(x//C), int(y//C)), ()):
        ax, ay, bx, by, w = segs[i]; vx, vy = bx-ax, by-ay; L = vx*vx+vy*vy or 1e-9
        t = max(0, min(1, ((x-ax)*vx+(y-ay)*vy)/L)); px, py = ax+t*vx, ay+t*vy; d = math.hypot(px-x, py-y)
        if d <= MAXD: out.append((d, px, py, w, math.atan2(vy, vx)))
    return out
def densify(pts, step=8):
    out = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(bx-ax, by-ay)//step))
        for k in range(1, n+1): out.append((ax+(bx-ax)*k/n, ay+(by-ay)*k/n))
    return out
def dp(pts, tol):
    if len(pts) < 3: return pts
    keep = [0]*len(pts); keep[0] = keep[-1] = 1; st = [(0, len(pts)-1)]
    while st:
        i, j = st.pop(); (x1,y1),(x2,y2) = pts[i], pts[j]; dx, dy = x2-x1, y2-y1; L = math.hypot(dx, dy)
        bi, bd = -1, tol
        for k in range(i+1, j):
            x, y = pts[k]; d = abs(dy*x-dx*y+x2*y1-y2*x1)/L if L else math.hypot(x-x1, y-y1)
            if d > bd: bi, bd = k, d
        if bi >= 0: keep[bi] = 1; st += [(i,bi),(bi,j)]
    return [p for p, k in zip(pts, keep) if k]
d = json.load(open(dataf, encoding="utf-8"))
moved = tot = 0; snapped_frac = []
for sh in d["shapes"]:
    enc = sh[1]; pts = []; x = y = 0
    for i in range(0, len(enc), 2): x += enc[i]; y += enc[i+1]; pts.append((x, y))
    P = densify(pts); out = []; prev_w = None; ok = 0
    for k, (x, y) in enumerate(P):
        hd = math.atan2(P[min(k+1,len(P)-1)][1]-P[max(k-1,0)][1], P[min(k+1,len(P)-1)][0]-P[max(k-1,0)][0])
        best = None
        for dd, px, py, w, ang in cands(x, y):
            da = abs(math.sin(ang-hd))            # road direction should match travel direction
            if da > 0.35: continue
            cost = dd + 40*da + (0 if w == prev_w else 10)
            if best is None or cost < best[0]: best = (cost, px, py, w)
        if best and best[0] < 26: out.append((best[1], best[2], best[3])); prev_w = best[3]; ok += 1
        else: out.append((x, y, None)); prev_w = None
    # remove spikes: short runs on another road between two runs on the same road -> keep raw points there
    runs = []; i = 0
    while i < len(out):
        j = i
        while j+1 < len(out) and out[j+1][2] == out[i][2]: j += 1
        runs.append((i, j)); i = j+1
    drop = set(); W = [p[2] for p in out]
    for r in range(1, len(runs)-1):
        a, b = runs[r]
        if b-a+1 <= 3 and W[runs[r-1][0]] is not None and W[runs[r-1][0]] == W[runs[r+1][0]]: drop.update(range(a, b+1))
    out = [(p[0], p[1]) for k, p in enumerate(out) if k not in drop]
    snapped_frac.append(ok/len(P))
    out = dp(out, 1.5); e2 = []; px = py = 0
    for x, y in out: X, Y = round(x), round(y); e2 += [X-px, Y-py]; px, py = X, Y
    sh[1] = e2
json.dump(d, open(dataf, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
sf = sorted(snapped_frac); print("shapes", len(sf), "median snapped", round(sf[len(sf)//2], 3), "p10", round(sf[len(sf)//10], 3))
