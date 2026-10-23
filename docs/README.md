# The published site

Served by GitHub Pages from `main` / `docs`:
https://yangrenrr.github.io/engg2112-network-decline/

```
index.html   the page: five tabs, one per objective. No build step.
data.json    O1, written by src/build_site.py
o2.json      O2, written by experiments/events/scripts/build_site_data.py
o3.json      O3 - add when ready
o4.json      O4 - add when ready
o5.json      O5 - add when ready
```

Until `oN.json` exists, that tab shows what the objective will cover. As soon
as it is committed, the tab renders it - **nobody needs to edit `index.html`**.

## Adding your objective (O3, O4, O5)

Write `docs/oN.json` from a script in your `experiments/` folder, so it can be
regenerated. Put any images next to it in `docs/` (e.g. `docs/o3_map.png`).

```json
{
  "id": "o3",
  "title": "Service quality and fairness",
  "question": "One sentence: the question this objective answers.",
  "owner": "Your Name",
  "status": "done",
  "answer": "One or two sentences: what you found.",
  "method": "One or two sentences: how.",
  "figures": [
    {"src": "o3_map.png", "caption": "What the reader should see in it.", "alt": "Short description"}
  ],
  "tables": [
    {"title": "Optional title", "columns": ["Group", "Regions", "Share"],
     "rows": [["Major cities", "152", "33%"], ["Remote", "12", "3%"]]}
  ],
  "limits": ["What this result cannot be used to claim."],
  "sources": [{"name": "Dataset name", "url": "https://..."}]
}
```

Every field except `id`, `title` and `question` is optional. `status` is
`"done"` or anything else for in progress. Figures should read in greyscale.
Keep `limits` honest: they are shown in a box headed *What this cannot tell you*.

Check it locally before pushing:

```bash
python3 -m http.server 8731 --directory docs   # then open http://localhost:8731/#o3
```
