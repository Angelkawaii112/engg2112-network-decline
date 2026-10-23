# Where Will the Network Fail Next?

Mobile connectivity in New South Wales, studied from public data: where it will
get worse, what changes it, who it serves badly, and where it does not reach.

**ENGG2112 · Semester 2, 2026 · TUT05**
Renyu Yang · Jingwei Qiu · Ying Xiao · Xiangbin Chen

**Live site:** https://yangrenrr.github.io/engg2112-network-decline/

---

## The question

How healthy is mobile connectivity across New South Wales, where is it failing
its users, and where should limited resources go?

Carriers can see their own networks; regulators, councils and the public
cannot. This project asks what public, crowdsourced speed tests can tell them.

| | Objective | Question | Status |
| --- | --- | --- | --- |
| **O1** | Predict | Which regions face a lasting decline, and how far can that ranking be trusted? | done |
| **O2** | Change | How did new towers, the 3G switch-off, and bushfires and floods change performance? | [done](experiments/events/README.md) |
| **O3** | Quality and fairness | Is the network good enough, and who is served worst? | in progress |
| **O4** | Resilience | Which regions depend on a single carrier, with no fallback in an emergency? | in progress |
| **O5** | Gaps | Where is there no terrestrial coverage, and can satellite fill it? | in progress |

Data, methods, owners and limits for each: **[PLAN.md](PLAN.md)**.
Full results with every table: **[RESULTS.md](RESULTS.md)**.

## O1 in brief

The system ranks NSW regions by the risk of a **lasting decline**: median
mobile download speed falling at least 20% and still down a quarter later. The
output is a list of places to **investigate**, not a list of faults.

```
Ookla quarterly tiles, clipped to NSW
  -> ~8 km regions
  -> each region's speed shrunk toward its own history, by test count
  -> ranked by how far it sits above its own long-run level
  -> random forest flags steep falls and predicts which will recover
  -> inspection list, sized by what a missed decline costs
```

**What we found**, scored quarter by quarter (13 quarters, 43 lasting declines):

- Inspecting the top 15% of regions finds **86%** of lasting declines, against 15% at random.
- A **one-parameter rule beats the random forest** at that budget. Five other model types were tried; none did better. The forest wins only at tighter budgets (10%).
- **68% of falls recover on their own** within two quarters. The ones that do not, stay down. The forest predicts which will recover better than any simple rule.
- Declines are **real link degradations** (upload falls too in 86% of cases), not congestion and not tied to income.
- **Regional NSW is excluded**: 94% of its data lacks the history the model needs. O3 to O5 study those areas instead.
- Weather, neighbouring regions and census population **add nothing**.

## Limits

- **Few events.** 43 lasting declines across 13 quarters; figures are indicative, not precise.
- **Test years reused.** Many methods were compared on the same quarters, so this is an evaluation on available data, not an independent validation.
- **Measured, not confirmed.** A lasting decline is a drop in a crowdsourced median; only an on-site check confirms a fault.

## Data

| Data | Source | Licence |
| --- | --- | --- |
| Mobile speed, latency, tests, devices | [Ookla Open Data](https://github.com/teamookla/ookla-open-data), quarterly, 2019 Q1 – 2026 Q1 | CC BY-NC-SA 4.0 |
| State and SA2 boundaries, SEIFA, population | Australian Bureau of Statistics | CC BY 4.0 |
| Weather (tested, not used) | [Open-Meteo](https://open-meteo.com/) | open |
| Daily speed tests (robustness check) | [M-Lab NDT](https://www.measurementlab.net/) | CC0 |

Data sources for O2 to O5 are listed in [PLAN.md](PLAN.md).

## Run it

```bash
python3 -m pip install -r requirements.txt     # versions are pinned; results depend on them

python src/build_panel.py                       # rebuild the panel from Ookla (takes hours)
python src/boundary.py --panel data/panel.csv   # clip to NSW -> data/panel_nsw.csv

python src/pipeline.py                          # panel to inspection list, one command
python src/verify_claims.py                     # re-derive the published figures (20 of 20)
python src/build_site.py                        # refresh the site's data
```

Each analysis in RESULTS.md has its own script in `src/`, named after what it
tests (`walkforward.py`, `recovery.py`, `equity.py`, ...).

## Repository

```
src/            pipeline, models and every analysis
experiments/    teammates' studies (one folder per objective)
docs/           the published site: index.html + data.json
figures/        report figures (PDF)
notes/          related work
PLAN.md         objectives, owners, rules
RESULTS.md      all results
```
