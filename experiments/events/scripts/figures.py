"""Event-study figure for O2: four panels, greyscale, same style as figures/."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
INK, MID, PALE = "#111111", "#777777", "#c8c8c8"
plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200, "savefig.bbox": "tight",
    "font.size": 7.5, "axes.titlesize": 8, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MID, "xtick.color": MID,
    "ytick.color": MID, "legend.frameon": False, "legend.fontsize": 7,
})

PANELS = [
    ("towers, 10 km", "New Mobile Black Spot towers (22 regions)"),
    ("floods 2022", "2022 Northern Rivers floods (40 regions)"),
    ("3G off, Telstra/Optus 2024 Q4 (rest vs city)", "Telstra/Optus 3G switch-off, outside cities vs cities"),
    ("fires 2019-20", "2019-20 bushfires (31 regions) - pre-trend fails"),
]


def main():
    c = pd.read_csv(HERE / "results/coefficients.csv")
    pct = lambda b: 100 * (np.exp(b) - 1)
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.6), sharex=True)
    for ax, (event, title) in zip(axes.flat, PANELS):
        for outcome, color, style, label, off in (("log_speed", INK, "-", "average speed", -0.08),
                                                  ("log_tests", MID, (0, (4, 2)), "number of tests", 0.08)):
            g = c[(c.event == event) & (c.outcome == outcome)].sort_values("k")
            if g.empty:
                continue
            x = g.k + off
            ax.vlines(x, pct(g.lo), pct(g.hi), color=color, lw=0.9, alpha=0.6)
            ax.plot(x, pct(g.beta), color=color, ls=style, lw=1.6, marker="o", ms=3,
                    label=label)
        ax.axhline(0, color=PALE, lw=0.8)
        ax.axvline(-0.5, color=PALE, lw=0.8, ls=":")
        ax.set_title(title, loc="left")
        ax.set_ylim(-100, 200)
    for ax in axes[1]:
        ax.set_xlabel("quarters from event (-1 is the reference)")
    for ax in axes[:, 0]:
        ax.set_ylabel("difference vs control (%)")
    axes[0, 0].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(HERE / "results/event_study.pdf")
    fig.savefig(HERE / "results/event_study.png")
    print("wrote results/event_study.pdf and .png")


if __name__ == "__main__":
    main()
