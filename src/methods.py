"""
Can any other way of training beat the one-parameter rule?

The rule ranks a region by how far its speed sits above its own long-run level.
Before accepting that a single number is the best available ranking, five
alternatives were scored the same way, under purged rolling origin:

  random forest            the model this project started with
  gradient boosting        shallow boosted trees, the usual next step
  logistic, all features   a linear model over everything the forest sees
  logistic, rule + 2 terms the rule's own variable, its square and log tests
  blend                    the rule's ranks and the forest's ranks averaged

None of them finds more lasting declines than the rule inside a 15% inspection
budget. The forest and the blend rank better overall (average precision about
0.50 against 0.44), and at a tighter 10% budget the forest finds far more,
0.80 against 0.59. Which method to deploy therefore depends on the budget, not
on which one is "best": a forest when only a handful of regions can be
visited, the rule at 15% and above. That is the cost analysis's conclusion
arrived at from the other side.

This is recorded so the question does not have to be asked again; it is not a
case for more models. With two to five events a quarter there is not enough
signal for a more flexible learner to find anything the rule misses.

Usage:
    python src/methods.py --panel data/panel_nsw.csv
"""
import sys, warnings; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score
from compare import recall_at_budget
from model import FEATURES, LAG_FEATURES, add_area_type, add_history, add_lags, add_target
from shrink import add_persistent, purge, shrink_speed, shrinkage_constant

raw = pd.read_csv(sys.argv[sys.argv.index("--panel")+1] if "--panel" in sys.argv else "data/panel_nsw.csv")
raw = add_area_type(add_lags(add_history(add_target(raw))))
df = add_persistent(shrink_speed(raw, shrinkage_constant(raw, 2021)))
feats = FEATURES + LAG_FEATURES
d = df.dropna(subset=feats); ok = d.fwd_1.notna() & d.fwd_2.notna()

def rf(tr,te,s):  return RandomForestClassifier(n_estimators=400,class_weight="balanced",min_samples_leaf=5,random_state=s,n_jobs=-1).fit(tr[feats],tr.persistent.astype(int)).predict_proba(te[feats])[:,1]
def gb(tr,te,s):  return HistGradientBoostingClassifier(max_depth=3,learning_rate=0.05,max_iter=200,class_weight="balanced",random_state=s).fit(tr[feats],tr.persistent.astype(int)).predict_proba(te[feats])[:,1]
def lr(tr,te,s):  return make_pipeline(SimpleImputer(),StandardScaler(),LogisticRegression(C=0.1,class_weight="balanced",max_iter=2000)).fit(tr[feats],tr.persistent.astype(int)).predict_proba(te[feats])[:,1]
def lr1(tr,te,s): # logistic on the rule's own variable plus its square and test count: a calibrated rule
    X=lambda f: np.c_[f.speed_vs_own_mean, f.speed_vs_own_mean**2, np.log(f.tests)]
    return make_pipeline(StandardScaler(),LogisticRegression(class_weight="balanced",max_iter=2000)).fit(X(tr),tr.persistent.astype(int)).predict_proba(X(te))[:,1]
rule = lambda tr,te,s: te.speed_vs_own_mean.values
def blend(tr,te,s): # average of ranks: rule + forest
    return rankdata(rule(tr,te,s)) + rankdata(rf(tr,te,s))

methods = {"simple rule":(rule,1), "random forest":(rf,3), "gradient boosting":(gb,3),
           "logistic, all features":(lr,1), "logistic, rule + 2 terms":(lr1,1),
           "blend: rule + forest ranks":(blend,3)}
res = {m:{"ap":[],"r15":[],"r10":[]} for m in methods}
nq=0; ev=0
for t in sorted(d[d.year>=2021].t.unique()):
    now = d[(d.t==t)&ok]; known = purge(d[(d.t<t)&ok], t)
    y = now.persistent.astype(int)
    if y.sum()<2 or len(known)<400: continue
    nq+=1; ev+=int(y.sum())
    for name,(fn,seeds) in methods.items():
        P = np.mean([fn(known,now,s) for s in range(seeds)],axis=0)
        res[name]["ap"].append(average_precision_score(y,P))
        res[name]["r15"].append(recall_at_budget(y,P,.15))
        res[name]["r10"].append(recall_at_budget(y,P,.10))

base = res["simple rule"]
print(f"{nq} quarters, {ev} lasting declines, purged rolling origin\n")
print(f"{'method':28} {'AP':>6} {'r@10':>6} {'r@15':>6}   {'beats rule on r@15':>18}")
for name,r in res.items():
    w = sum(a>b for a,b in zip(r["r15"],base["r15"])); l = sum(a<b for a,b in zip(r["r15"],base["r15"]))
    tag = "" if name=="simple rule" else f"{w} won, {l} lost"
    print(f"{name:28} {np.mean(r['ap']):>6.3f} {np.mean(r['r10']):>6.3f} {np.mean(r['r15']):>6.3f}   {tag:>18}")
