"""Compare population growth with the unchanged demand baseline on paired rows."""
from settings import ROOT, SOURCE, check_source
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn

sys.path.insert(0, str(SOURCE / "src"))
from demand import DEMAND, add_demand, score
from model import FEATURES, LAG_FEATURES, add_area_type, add_history, add_lags, add_target
from shrink import add_persistent, shrink_speed, shrinkage_constant


def training_mask(frame, protocol, cutoff_t):
    mask = frame.year < 2024
    if protocol == "horizon_purged":
        # Both required outcome quarters must precede the first test feature quarter.
        mask &= frame.t + 2 < cutoff_t
    return mask


def check_original():
    return check_source()


def main():
    commit = check_original()
    raw = pd.read_csv(ROOT / "data/network/panel_nsw.csv", dtype={"region": str})
    raw = add_area_type(add_lags(add_history(add_target(raw))))
    constant = shrinkage_constant(raw, 2024)
    frame = add_demand(add_persistent(shrink_speed(raw, constant)))
    base = FEATURES + LAG_FEATURES
    frame = frame.dropna(subset=base + ["fwd_1", "fwd_2"])
    # Attach external features only after fixing the original eligible row population.
    population = pd.read_csv(ROOT / "data/derived/panel_population.csv", dtype={"region": str, "sa2": str})
    cols = ["region", "year", "quarter", "sa2", "growth_rate", "published", "vintage", "population_missing_reason"]
    frame = frame.merge(population[cols], on=["region", "year", "quarter"], how="left", validate="one_to_one", sort=False)
    frame["population_available"] = frame.growth_rate.notna().astype(int)
    test = frame[frame.year >= 2024].copy()
    cutoff_t = int(test.t.min())
    rows, audit = [], {}
    test_keys = test[["region", "year", "quarter", "t", "persistent", "sa2", "growth_rate", "published", "vintage", "population_missing_reason"]]
    test_keys.to_csv(ROOT / "results/test_rows.csv", index=False)
    key_digest = hashlib.sha256(test_keys[["region", "t", "persistent"]].to_csv(index=False).encode()).hexdigest()
    demand = base + DEMAND
    sets = {"baseline_devices": demand,
            "plus_population_growth": demand + ["growth_rate"],
            "population_availability_control": demand + ["population_available"]}
    for protocol in ("original", "horizon_purged"):
        mask = training_mask(frame, protocol, cutoff_t)
        train = frame[mask].copy()
        train[["region", "year", "quarter", "t", "persistent", "growth_rate", "published"]].to_csv(ROOT / f"results/train_rows_{protocol}.csv", index=False)
        info = dict(train_rows=len(train), test_rows=len(test), train_positives=int(train.persistent.sum()),
                    test_positives=int(test.persistent.sum()), train_population_available=int(train.growth_rate.notna().sum()),
                    test_population_available=int(test.growth_rate.notna().sum()),
                    removed_training_rows=int(((frame.year < 2024) & ~mask).sum()),
                    last_training_quarter_index=int(train.t.max()), latest_training_outcome_index=int((train.t + 2).max()),
                    first_test_quarter_index=cutoff_t, test_rows_sha256=key_digest)
        audit[protocol] = info
        print(protocol, json.dumps(info), flush=True)
        for name, features in sets.items():
            # The original repository's scoring function sets every model parameter,
            # missing-value sentinel, seed and inspection-budget rounding rule.
            aps, recalls, fitted = score(train, test, features, trees=400, seeds=10)
            for seed, (ap, recall) in enumerate(zip(aps, recalls)):
                rows.append(dict(sklearn_version=sklearn.__version__, protocol=protocol, model=name, seed=seed, average_precision=float(ap), recall_at_15=float(recall)))
            pd.Series(fitted.feature_importances_, index=features, name="importance_seed_9").sort_values(ascending=False).to_csv(ROOT / f"results/importance_{protocol}_{name}.csv")
            print(f"  {name}: AP {aps.mean():.6f} +/- {aps.std():.6f}; Recall@15 {recalls.mean():.6f} +/- {recalls.std():.6f}", flush=True)
            pd.DataFrame(rows).to_csv(ROOT / "results/per_seed_metrics.csv", index=False)
    metrics = pd.DataFrame(rows)
    summary_rows, differences = [], []
    for (protocol, model), group in metrics.groupby(["protocol", "model"], sort=False):
        summary_rows.append(dict(sklearn_version=sklearn.__version__, protocol=protocol, model=model, ap_mean=group.average_precision.mean(),
                                 ap_std=group.average_precision.std(ddof=0), recall15_mean=group.recall_at_15.mean(),
                                 recall15_std=group.recall_at_15.std(ddof=0), **audit[protocol]))
    for protocol in audit:
        subset = metrics[metrics.protocol == protocol].set_index(["model", "seed"])
        before = subset.loc["baseline_devices"]
        after = subset.loc["plus_population_growth"]
        for seed in range(10):
            differences.append(dict(sklearn_version=sklearn.__version__, protocol=protocol, seed=seed,
                                    ap_delta=after.loc[seed, "average_precision"] - before.loc[seed, "average_precision"],
                                    recall15_delta=after.loc[seed, "recall_at_15"] - before.loc[seed, "recall_at_15"]))
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(ROOT / "results/comparison.csv", index=False)
    pd.DataFrame(differences).to_csv(ROOT / "results/paired_seed_differences.csv", index=False)
    original = summary[(summary.protocol == "original") & (summary.model == "baseline_devices")].iloc[0]
    metadata = dict(sklearn_version=sklearn.__version__, commit=commit, shrinkage_constant=constant, features=sets, protocols=audit,
                    reported_baseline=dict(ap=0.598, ap_std=0.012, recall15=0.882, recall15_std=0.0),
                    reproduced_baseline=dict(ap=float(original.ap_mean), ap_std=float(original.ap_std),
                                             recall15=float(original.recall15_mean), recall15_std=float(original.recall15_std)),
                    baseline_matches_reported_rounding=bool(round(original.ap_mean, 3) == 0.598 and round(original.recall15_mean, 3) == 0.882),
                    settings=dict(trees=400, min_samples_leaf=5, class_weight="balanced", seeds=list(range(10)), std_ddof=0, missing_sentinel=-99),
                    label_definition="Unchanged shrink.add_persistent: both t+1 and t+2 smoothed speed <= 0.8 times t speed, with consecutive-quarter checks.",
                    prediction_date="End of feature quarter; population releases selected as-of this date, conservatively excluding releases between quarter end and Ookla publication.",
                    purging="Horizon-purged training includes only rows with t+2 < first test feature quarter. This removes 2023 Q3/Q4 rows when testing starts 2024 Q1.",
                    timing_limit="Horizon purging is audited at quarter granularity. Exact historic Ookla publication timestamps are not established; this is not a fully vintage-reconstructed operational backtest.")
    check_original()
    metadata["original_working_tree_unchanged"] = True
    (ROOT / "results/evaluation_audit.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    plot(summary)
    print(summary[["protocol", "model", "ap_mean", "ap_std", "recall15_mean", "recall15_std"]].to_string(index=False), flush=True)


def plot(summary):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    names = {"baseline_devices": "Devices baseline", "plus_population_growth": "+ population growth", "population_availability_control": "Availability control"}
    for ax, (metric, label) in zip(axes, [("ap", "Average precision"), ("recall15", "Recall at 15%")]):
        for i, protocol in enumerate(("original", "horizon_purged")):
            subset = summary[summary.protocol == protocol]
            x = np.arange(len(subset)) + (i - 0.5) * 0.32
            ax.bar(x, subset[f"{metric}_mean"], width=0.30, yerr=subset[f"{metric}_std"], capsize=3, label=protocol.replace("_", " "))
        ax.set_xticks(range(3), [names[n] for n in subset.model], rotation=18, ha="right")
        ax.set_ylabel(label)
        ax.set_ylim(0, 1)
        ax.grid(axis="y", alpha=0.2)
    axes[0].legend()
    fig.suptitle(f"NSW persistent mobile-speed decline: scikit-learn {sklearn.__version__}; mean +/- SD across 10 seeds")
    fig.tight_layout()
    fig.savefig(ROOT / "results/model_comparison.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
