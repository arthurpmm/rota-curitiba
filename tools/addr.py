"""Build an offline address index from URBS stop names ('Rua X, 123 - Bairro') and URBS points of interest."""
import json, re, math, sys, unicodedata, collections
raw, pref, datafile = sys.argv[1], sys.argv[2], sys.argv[3]
LAT0, LON0 = -25.4296, -49.2713
KX, KY = 111320*math.cos(math.radians(LAT0)), 110540
f = lambda s: float(s.replace(",", "."))
xy = lambda la, lo: (round((lo-LON0)*KX), round((la-LAT0)*KY))
def strip(s): return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()
TYPES = {"r":"rua","rua":"rua","av":"avenida","avenida":"avenida","al":"alameda","alameda":"alameda","tv":"travessa","trav":"travessa","travessa":"travessa",
         "pca":"praca","pc":"praca","praca":"praca","rod":"rodovia","rodovia":"rodovia","estr":"estrada","estrada":"estrada","lgo":"largo","largo":"largo","lad":"ladeira","ladeira":"ladeira","via":"via","linha":"linha","br":"br","viaduto":"viaduto"}
TITLES = {"prof":"professor","profa":"professora","dr":"doutor","dra":"doutora","cel":"coronel","gen":"general","dep":"deputado","sen":"senador","eng":"engenheiro","des":"desembargador","pe":"padre",
          "sta":"santa","sto":"santo","sao":"sao","mal":"marechal","cap":"capitao","ten":"tenente","maj":"major","pres":"presidente","gov":"governador","com":"comendador","brig":"brigadeiro","alm":"almirante","min":"ministro","cons":"conselheiro","ver":"vereador","vig":"vigario","frei":"frei","d":"dom","nsa":"nossa","sra":"senhora","n":"nossa","s":"sao"}
STOP = {"de","da","do","das","dos","e"}
def key(street):
    w = re.findall(r"[a-z0-9]+", strip(street))
    if not w: return None
    t = TYPES.get(w[0]); rest = w[1:] if t else w
    rest = [TITLES.get(x, x) for x in rest if x not in STOP]
    return (t or "rua") + " " + " ".join(rest)
d = json.load(open(datafile, encoding="utf-8"))
P = json.load(open(f"{raw}/{pref}_pontosLinha.json", encoding="utf-8"))
seen = set(); streets = collections.defaultdict(lambda: {"names": collections.Counter(), "pts": set(), "bairros": collections.Counter()})
bairro_pts = collections.defaultdict(list)
for p in P:
    if p["NUM"] in seen: continue
    seen.add(p["NUM"])
    nm = re.sub(r"\s+", " ", p["NOME"]).strip()
    if re.match(r"^(Terminal|Esta[cç])", nm): continue
    m = re.match(r"^(.*?)(?:,\s*|\s+)(\d{1,5})\s*(?:-\s*(.+))?$", nm) or re.match(r"^(.*?)\s*-\s*(\d{1,5})?\s*(.+)$", nm)
    street, num, bairro = (m.group(1), m.group(2), m.group(3)) if m else (nm, None, None)
    if bairro: bairro = re.sub(r"\s*\(.*$", "", re.split(r"\s*[-,]\s*", bairro)[0]).strip()
    if not re.match(r"^(R\.?|Rua|Av\.?|Avenida|Al\.?|Alameda|Tv\.?|Trav\.?|Travessa|P[cç]a\.?|Pra[cç]a|Rod\.?|Rodovia|Estr\.?|Estrada|Largo|Linha)\b", street, re.I): continue
    street = re.split(r",", street)[0].strip()
    k = key(street)
    if not k: continue
    x, y = xy(f(p["LAT"]), f(p["LON"]))
    S = streets[k]; S["names"][street.strip(" ,-")] += 1
    S["pts"].add((int(num) if num else -1, x, y))
    if bairro and len(bairro) > 2 and not re.search(r"\d", bairro):
        S["bairros"][bairro] += 1; bairro_pts[strip(bairro)].append((bairro, x, y))
def nice(names):
    def score(n): return (n.split(" ")[0] in ("Rua","Avenida","Alameda","Travessa","Praça","Rodovia","Estrada"), -n.count("."), names[n])
    n = max(names, key=score)
    return re.sub(r"^R\.\s*", "Rua ", re.sub(r"^Av\.\s*", "Avenida ", n))
out_st = []
for k, S in streets.items():
    pts = sorted(S["pts"])
    flat = [v for p in pts for v in p]
    out_st.append([nice(S["names"]), ", ".join(b for b, _ in S["bairros"].most_common(3)), flat])
# neighbourhoods: centroid of stops, display name most common spelling
out_b = []
for k, L in bairro_pts.items():
    if len(L) < 3: continue
    nm = collections.Counter(b for b, _, _ in L).most_common(1)[0][0]
    out_b.append([nm, round(sum(x for _, x, _ in L)/len(L)), round(sum(y for _, _, y in L)/len(L))])
POI = json.load(open(f"{raw}/{pref}_pois.json", encoding="utf-8"))
CAT = lambda c: {"SAUDE HOSPITAL":"Hospital","ECON SHOPPING":"Shopping","IGREJA":"Church","HOTEL":"Hotel","ESPACO CULTURAL":"Culture","TERMINAL DE TRANSPORTE":"Transport"}.get(c, (c or "").split(" ")[0].title() if c else "")
CATN = {"EDUC":"School","ABAST":"Market","SAUDE":"Health","ESPORTE":"Sport","ADM":"City office","BIB":"Library","SEG":"Public safety"}
out_p = []
for q in POI:
    try: x, y = xy(f(q["POI_LAT"]), f(q["POI_LON"]))
    except Exception: continue
    c = q.get("POI_CATEGORY_NAME") or ""
    lab = CAT(c); lab = CATN.get(lab.upper(), lab)
    out_p.append([q["POI_NAME"].strip(), lab, x, y])
d["addr"] = {"streets": out_st, "bairros": out_b, "pois": out_p}
json.dump(d, open(datafile, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("streets", len(out_st), "with numbers", sum(1 for s in out_st if any(s[2][i] >= 0 for i in range(0, len(s[2]), 3))), "bairros", len(out_b), "pois", len(out_p))
import random; random.seed(3)
for s in random.sample(out_st, 8): print(s[0], "|", s[1], "|", s[2][:9])
print(sorted(b[0] for b in out_b)[:200:6])

# ---------- merge OpenStreetMap export (CSV: name|addr:street|addr:housenumber|lat|lon) ----------
if len(sys.argv) > 4:
    osm = sys.argv[4]
    # nearest-stop neighbourhood lookup
    G = 500; grid = collections.defaultdict(list)
    for L in bairro_pts.values():
        for b, x, y in L: grid[(x // G, y // G)].append((b, x, y))
    def bairro_at(x, y):
        best, bd = "", 700 ** 2
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for b, bx, by in grid.get((x // G + dx, y // G + dy), []):
                    dd = (bx - x) ** 2 + (by - y) ** 2
                    if dd < bd: best, bd = b, dd
        return best
    O = collections.defaultdict(lambda: {"names": collections.Counter(), "num": collections.defaultdict(list), "geo": []})
    places = {}
    for ln in open(osm, encoding="utf-8"):
        p = ln.rstrip("\n").split("|")
        if len(p) != 5: continue
        try: la, lo = float(p[3]), float(p[4])
        except ValueError: continue
        if not (-25.7 < la < -25.3 and -49.45 < lo < -49.15): continue
        x, y = xy(la, lo)
        name, street, hn = p[0].strip(), p[1].strip(), p[2].strip()
        if hn and street:
            m = re.match(r"\d{1,5}", hn)
            k = key(street)
            if not m or not k: continue
            n = int(m.group()); S = O[k]; S["names"][street] += 1
            S["num"][n // 10 * 10].append((n, x, y))
            if name and len(name) > 2: places[(name, street)] = [name, f"{street}, {hn}", x, y]
        elif name:
            k = key(name)
            if k and re.match(r"^(rua|avenida|alameda|travessa|praca|rodovia|estrada|largo)\b", k):
                O[k]["names"][name] += 3; O[k]["geo"].append((x, y))
    merged = {}
    for s in out_st: merged[key(s[0])] = s
    added = upd = 0
    for k, S in O.items():
        if not S["names"]: continue
        pts = []
        for b, L in sorted(S["num"].items()):     # one averaged point per 10 house numbers
            n = round(sum(a for a, _, _ in L) / len(L))
            pts.append((n, round(sum(x for _, x, _ in L) / len(L)), round(sum(y for _, _, y in L) / len(L))))
        geo = S["geo"]
        if not pts and geo:
            step = max(1, len(geo) // 8)
            pts = [(-1, x, y) for x, y in geo[::step]]
        if not pts: continue
        flat = [v for p_ in pts for v in p_]
        mx, my = pts[len(pts) // 2][1:]
        if k in merged:
            old = merged[k]
            if any(v >= 0 for v in flat[0::3]): old[2] = flat; upd += 1   # OSM house numbers replace stop-based estimates
        else:
            merged[k] = [nice(S["names"]), bairro_at(mx, my), flat]; added += 1
    out_st = list(merged.values())
    out_p += [[nm, sub, x, y] for nm, sub, x, y in places.values()]
    d["addr"] = {"streets": out_st, "bairros": out_b, "pois": out_p}
    json.dump(d, open(datafile, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("OSM merged: streets", len(out_st), "added", added, "updated with house numbers", upd, "places", len(out_p))
