# School final-report mapping and remaining team work

This is a contribution checklist, not a grade guarantee. Requirements were taken from the assignment/rubric screenshots supplied by the student.

| School criterion | Evidence from this experiment | What is still required in the group report |
| --- | --- | --- |
| Objectives, motivation, background (4) | Explicit download-only blind-spot and assessability questions; official Ookla/ABS sources | Integrate with the group's original motivation, related research and actual proposal |
| Methods (4) | Independent acquisition, data preparation, geography, fixed definitions, sensitivity, reproducible scripts | Explain the group's full ML training/validation/testing separately; this experiment is descriptive, not a new model |
| Findings, analysis and evidence (4) | Numerators/denominators, four figures, bootstrap, same-quarter contrasts, record-level outputs, independent verification | Select useful figures, explain errors/limitations and connect findings to group objectives |
| Recommendations, stakeholders, impact and ethics (3) | Measurement-first handling of sparse regions, human review, uncertainty, privacy, proposed downstream use | Critically compare realistic costs, users, deployment responsibilities and findings across all project components |
| Proposal-to-final development | Scope and base commit recorded; comparison with current PLAN.md below | Check the actual submitted proposal, which this experiment does not claim to have reviewed |
| End-to-end system discussion | Proposed data → quality audit → human review / further measurement → possible integration with prediction | Clearly separate implemented modules from proposed deployment and integration |
| PDF + public code link | Reproducible source and report figures prepared for a separate branch | Confirm successful repository publication; add its final URL to the PDF |
| <=10 pages of main body | Two main figures recommended; extra figures/diagnostics can go to appendix | Check final assembled PDF; excluded front matter/references/appendices follow school instructions |
| Substantive AI use appendix | AI assistance disclosure; local log framework records actual prompts/output/verifications | Preserve full actual session export, and add only human checks/modifications actually performed |

## Scope relative to current team plan

Implemented here: independent mobile-data acquisition; disjoint download/upload/latency deterioration patterns; official RA2021 grouping; denominator and sampling audit; threshold/sampling/boundary sensitivity; tested outputs.

Not implemented here: fixed-versus-mobile dual-poor analysis; long-term absolute service-adequacy classes; new SEIFA analysis; individual demographic fairness; carrier resilience; changing the production inspection ranking; new predictive models; a deployed end-to-end service. The team plan's full O3 must therefore not be marked complete just because this experiment exists.

## Evidence-backed recommendations

| Finding | Action for whom | Constraint / risk |
| --- | --- | --- |
| 259 additional upload/latency records in the primary sample | Analysts: include all three metrics in retrospective review | Not confirmed faults; not a model recall measurement |
| Sparse Remote/Very Remote eligibility | Researchers/regulators: prioritize targeted, consent-based measurement before ranking | Low evidence is not evidence of poor service or no coverage |
| Threshold-dependent counts | Operators: show threshold and denominator alongside each flag | Do not equate project rules with regulatory standards |
| Mixed cells and selective testing | Team: display geographic/sampling uncertainty and use field verification | Region averages cannot establish household conditions |
| Future data needed for outcome labels | Model team: use these only as future outcomes in a separately designed forecasting study | Future values/labels must never enter historical predictor features; training splits require temporal separation/purging |

Resource savings, maintenance benefits and environmental benefits have not been measured. They may be discussed as potential benefits of a future system, not as achieved outcomes. No team member's existing files or main-branch outputs are modified by this contribution.
