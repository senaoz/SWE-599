"""Data card numbers and published-baseline losses for the Stelmakh et al. gold-standard dataset.

Usage: python3 -I research/audit/goldstandard_report.py research/data/external/goldstandard
"""
import json, sys, os, glob, collections
import pandas as pd, numpy as np
G = sys.argv[1]
df = pd.read_csv(f"{G}/data/evaluations.csv", sep="\t")
refs = {}
for _, r in df.iterrows():
    d = {}
    for i in range(1, 11):
        p, e = r[f"Paper{i}"], r[f"Expertise{i}"]
        if isinstance(p, str) and not pd.isna(e): d[p] = float(e)
    refs[str(r.ParticipantID)] = d
n = [len(v) for v in refs.values()]
print("participants", len(refs), "ratings", sum(n), "per participant min/median/max", min(n), np.median(n), max(n))
allv = [x for v in refs.values() for x in v.values()]
print("score distribution", collections.Counter(allv).most_common())
pc = collections.Counter(p for v in refs.values() for p in v)
print("rated papers", len(pc), "rated by >1 participant", sum(1 for c in pc.values() if c > 1))
spread = [max(v.values()) - min(v.values()) for v in refs.values() if v]
print("per-participant score range median", np.median(spread), "ties share", np.mean([len(set(v.values())) < len(v) for v in refs.values()]))
D = f"{G}/evaluation_datasets/d_20_1"
subs = json.load(open(f"{D}/submissions.json"))
print("submissions in d_20_1", len(subs))
sizes = []; own_overlap = 0; noabs = 0
for f in glob.glob(f"{D}/archives/*.jsonl"):
    rows = [json.loads(l) for l in open(f)]
    sizes.append(len(rows))
    rid = os.path.basename(f)[1:-6]
    own_overlap += len(set(r["id"] for r in rows) & set(refs.get(rid, {})))
    noabs += sum(1 for r in rows if not r["content"].get("abstract"))
print("archives", len(sizes), "profile sizes min/median/max", min(sizes), np.median(sizes), max(sizes), "rated papers inside own profile", own_overlap, "profile papers w/o abstract", noabs, "of", sum(sizes))
print("submission keys", list(next(iter(subs.values()))["content"].keys()))
print("subs w/o abstract", sum(1 for s in subs.values() if not s["content"].get("abstract")))
papers = [json.load(open(f)) for f in glob.glob(f"{G}/data/papers/*.json")]
yrs = [p.get("year") for p in papers if p.get("year")]
print("paper json keys", sorted(papers[0].keys())[:20], "years", min(yrs), max(yrs))
ry = [json.load(open(f"{G}/data/papers/{p}.json")).get("year") for p in pc if os.path.exists(f"{G}/data/papers/{p}.json")]
ry = [y for y in ry if y]; print("rated paper years: min/median/max", min(ry), np.median(ry), max(ry), "after 2023:", sum(y > 2023 for y in ry))

def ktl(preds, refs):
    from itertools import combinations
    mx = loss = 0
    for rv, d in refs.items():
        if rv not in preds: continue
        ps = sorted(d, key=lambda p: preds[rv][p], reverse=True)
        for a, b in combinations(ps, 2):
            pd_, td = preds[rv][a]-preds[rv][b], d[a]-d[b]
            mx += abs(td)
            if pd_*td == 0: loss += abs(td)/2
            elif pd_*td < 0: loss += abs(td)
    return loss/mx
algos = sorted({os.path.basename(f).rsplit("_d_20_",1)[0] for f in glob.glob(f"{G}/predictions/*_d_20_*_ta.json")})
for a in algos:
    vals = []
    for i in range(1, 11):
        f = f"{G}/predictions/{a}_d_20_{i}_ta.json"
        if os.path.exists(f):
            try: vals.append(ktl(json.load(open(f)), refs))
            except Exception as e: vals.append(None)
    ok = [v for v in vals if v is not None]
    print(f"{a:28s} files={len(vals):2d} ok={len(ok):2d} loss={np.mean(ok):.3f}" if ok else f"{a:28s} files={len(vals)} failed")
