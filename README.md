# Rota Curitiba

Bus trip planner for Curitiba: plans trips on real URBS timetables with transfers, shows next departures at every stop, searches addresses, and follows your location live.

- Bus data: URBS open data via dadosabertos.c3sl.ufpr.br (snapshot 23/11/2026)
- Streets, places and addresses: © OpenStreetMap contributors (ODbL)
- Places: Foursquare Open Source Places (Apache License 2.0)

Open `index.html` from GitHub Pages (https) and allow location when the browser asks.

## Automatic timetable updates

Every Monday morning a GitHub Action (`.github/workflows/update-timetables.yml`) downloads the newest URBS
snapshot, rebuilds `data.json` with the scripts in `tools/`, and commits it only if timetables, stops or lines
changed. You can also run it any time from the repository's **Actions** tab → *Update URBS timetables* → **Run workflow**.
