# Error cases: what actually happened in these places?

Part of **O1** (how far the ranking can be trusted); see [PLAN.md](../../PLAN.md).

`cases.csv` lists every lasting decline in the 2024–2026 test years, sorted into
what the deployed ranker did with it at a 15% budget, plus the twelve strongest
false alarms:

| kind | count | meaning |
| --- | --- | --- |
| caught | 16 | flagged, and it really did fall and stay down |
| missed | 1 | not flagged, but it fell and stayed down |
| false alarm | 12 | flagged, but it did not stay down |

Columns: `place` is the ABS SA2 containing the region centre (`near ...` when
the centre is offshore and the nearest SA2 is given instead); `change_next_q`
and `change_two_q` are the shrunk speed's change one and two quarters later;
`rank` / `of` is where the ranker put it that quarter.

Regenerate with the snippet in the commit that added this folder, or ask for it.

## The task

The model can say a region's measured speed dropped. It cannot say why. For
each case, find out whether something real happened there in or just before
that quarter, and record it with a source.

Things worth checking, roughly in order of how likely they are:

- **3G shutdowns.** All three carriers switched off 3G in this window. Verify
  the dates from the carriers or ACMA; do not take them from memory. Does a
  cluster of falls line up with one carrier's switch-off?
- **Natural events.** Floods, bushfires, storms (Northern Rivers, Central Coast,
  Blue Mountains are all in the list).
- **Infrastructure changes.** Tower decommissioning, upgrades, new estates,
  NBN fixed-wireless changes. Local council and news sites are the best source.
- **Nothing.** A case where you look properly and find nothing is a result too.
  Say so rather than guessing.

## What to hand back

`findings.md` in this folder: one row per case with *place, quarter, what
happened, source link, confidence (confirmed / plausible / nothing found)*,
then two or three paragraphs on the pattern. Things worth saying if they are
true: do caught cases have real causes more often than false alarms? Are false
alarms mostly real falls that recovered (look at `change_next_q`)?

This becomes the *errors and case studies* part of the report, which the
findings criterion asks for by name.

## Rules

- Work on a branch and open a pull request, as `experiments/population_growth`
  did. Do not edit anything under `src/`.
- Every claim needs a link. No source, no claim.
