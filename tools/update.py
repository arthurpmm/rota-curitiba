"""Weekly URBS timetable refresh for Rota Curitiba.

Downloads the newest URBS open-data snapshot from dadosabertos.c3sl.ufpr.br,
rebuilds data.json with the same steps used to build the app, and bumps the app
version only when buses, stops or times actually changed.

Usage (from the repository root):  python3 tools/update.py
Exit code 0 always; prints CHANGED=1 or CHANGED=0 for the workflow.
"""
import datetime, json, lzma, os, re, shutil, subprocess, sys, tempfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
BASE = "https://dadosabertos.c3sl.ufpr.br/curitibaurbs/"
FILES = ["linhas", "pontosLinha", "shapeLinha", "tabelaLinha", "pois"]


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "rota-curitiba-updater"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def newest_date():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    for back in range(0, 10):
        d = today - datetime.timedelta(days=back)
        pref = d.strftime("%Y_%m_%d")
        try:
            req = urllib.request.Request(BASE + f"{pref}_tabelaLinha.json.xz", method="HEAD")
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status == 200:
                    return pref
        except Exception:
            continue
    return None


def content(d):
    """Everything that matters for routing, without the snapshot date."""
    return json.dumps({k: d[k] for k in ("routes", "stops", "pats")}, sort_keys=True)   # timetables, stops, lines


def main():
    pref = newest_date()
    if not pref:
        print("No URBS snapshot found in the last 10 days"); print("CHANGED=0"); return
    current = json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))
    cur_gen = current.get("gen", "")
    print("newest URBS snapshot:", pref, "| app has:", cur_gen)

    tmp = tempfile.mkdtemp()
    raw = os.path.join(tmp, "raw"); os.makedirs(raw)
    for f in FILES:
        xz = os.path.join(raw, f"{pref}_{f}.json.xz")
        fetch(BASE + f"{pref}_{f}.json.xz", xz)
        with lzma.open(xz, "rb") as s, open(xz[:-3], "wb") as o:
            shutil.copyfileobj(s, o)
    with lzma.open(os.path.join(TOOLS, "data", "osm_addresses.txt.xz"), "rb") as s, open(os.path.join(tmp, "addr.txt"), "wb") as o:
        shutil.copyfileobj(s, o)
    with lzma.open(os.path.join(TOOLS, "data", "roads.json.xz"), "rb") as s, open(os.path.join(tmp, "roads.json"), "wb") as o:
        shutil.copyfileobj(s, o)

    out = os.path.join(tmp, "data.json")
    run = lambda *a: subprocess.run([sys.executable, "-I", *a], check=True)
    run(os.path.join(TOOLS, "build.py"), raw, pref, out)
    run(os.path.join(TOOLS, "addr.py"), raw, pref, out, os.path.join(tmp, "addr.txt"))
    d = json.load(open(out, encoding="utf-8"))
    d["addr"]["pois"] = []                                   # places live in places.json
    for r in d["routes"]:
        r[1] = re.sub(r"/v\. ", "/V. ", r[1])
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    run(os.path.join(TOOLS, "snapshapes.py"), os.path.join(tmp, "roads.json"), out)
    new = json.load(open(out, encoding="utf-8"))

    if content(new) == content(current):
        print("Timetables unchanged since", cur_gen); print("CHANGED=0"); return

    shutil.copy(out, os.path.join(ROOT, "data.json"))
    # bump the app version so phones reload, and the snapshot date in the README
    idx = os.path.join(ROOT, "index.html"); h = open(idx, encoding="utf-8").read()
    ver = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d") + ".u"
    h = re.sub(r'const APP_VERSION="[^"]+";', f'const APP_VERSION="{ver}";', h)
    open(idx, "w", encoding="utf-8").write(h)
    rd = os.path.join(ROOT, "README.md")
    if os.path.exists(rd):
        t = open(rd, encoding="utf-8").read()
        t = re.sub(r"\(snapshot [0-9/]+\)", f"(snapshot {new['gen']})", t)
        open(rd, "w", encoding="utf-8").write(t)
    print("Updated to URBS data", new["gen"]); print("CHANGED=1")


if __name__ == "__main__":
    main()
