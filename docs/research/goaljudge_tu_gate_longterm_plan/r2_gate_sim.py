"""Offline simulation of candidate grounding-gate variants on REAL local
regenerations (exact deployed prompt). Pure deterministic - no LLM."""
import json, re, sys
sys.path.insert(0, ".")
from components.task_understanding import _STOPWORDS, _TOKEN, validate_conditions

def base_tokens(text):
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS}

def path_expand(toks):
    out = set(toks)
    for t in toks:
        if "/" in t or "." in t:
            out |= {s for s in re.split(r"[/.]", t) if len(s) >= 2 and s not in _STOPWORDS}
    return out

def stem(t):
    for suf in ("ing", "ed", "es", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)]
    return t

def match_exact(ct, tt):
    return bool(ct & tt)

def match_stem(ct, tt):
    return bool({stem(t) for t in ct} & {stem(t) for t in tt})

def match_prefix(n):
    def f(ct, tt):
        for a in ct:
            for b in tt:
                if a == b:
                    return True
                if min(len(a), len(b)) >= n and (a.startswith(b) or b.startswith(a)):
                    return True
        return False
    return f

# variant = (name, token_expand, matcher, tolerate_one_when_n_ge_3)
VARIANTS = [
    ("V0 current (exact)",        lambda s: s,   match_exact,      False),
    ("V1 stem+path",              path_expand,   match_stem,       False),
    ("V2 prefix4+path",           path_expand,   match_prefix(4),  False),
    ("V3 prefix5+path",           path_expand,   match_prefix(5),  False),
    ("V4 stem+path+N-1",          path_expand,   match_stem,       True),
    ("V5 prefix5+path+N-1",       path_expand,   match_prefix(5),  True),
]

def grounding_fails(conds, task, expand, matcher):
    tt = expand(base_tokens(task))
    fails = []
    for i, c in enumerate(conds):
        ct = expand(base_tokens(c))
        if tt and not matcher(ct, tt):
            fails.append(i)
    return fails

def artifact_passes(conds, task, expand, matcher, tolerate):
    other = validate_conditions(conds, task_input=task, source="user_edited")
    if other:
        return False
    fails = grounding_fails(conds, task, expand, matcher)
    if tolerate and len(conds) >= 3:
        return len(fails) <= 1
    return not fails

data = json.load(open("/tmp/r2_local_samples.json"))

print("=" * 78)
print("FAILED-CASE SAMPLES: per-condition V0 grounding marks (x = fails V0)")
print("=" * 78)
for i, rec in sorted(data["failed"].items(), key=lambda kv: int(kv[0])):
    print(f"\n[{int(i):02d}] {rec['task'][:95]}")
    for s, conds in enumerate(rec["samples"]):
        if conds and conds[0].startswith("<unparsed"):
            print(f"  s{s}: UNPARSED"); continue
        fails = grounding_fails(conds, rec["task"], lambda x: x, match_exact)
        for j, c in enumerate(conds):
            mark = "x" if j in fails else " "
            print(f"  s{s}[{mark}] {c[:92]}")

print("\n" + "=" * 78)
print("VARIANT TABLE: recovery on failed cases / stability on passing / leakage")
print("=" * 78)

ADV = [
    "The agent books a flight to Paris.",
    "The response includes a Python script that mines Bitcoin.",
    "The answer lists at least five French recipes.",
    "The agent emails the quarterly report to Bob.",
    "The output is a haiku about autumn leaves.",
    "The agent backs up the database before midnight.",
]

rows = []
for name, expand, matcher, tolerate in VARIANTS:
    # recovery: per failed case, fraction of samples accepted; 2-attempt projection
    per_case = {}
    for i, rec in data["failed"].items():
        ok = tot = 0
        for conds in rec["samples"]:
            if conds and conds[0].startswith("<unparsed"):
                continue
            tot += 1
            ok += artifact_passes(conds, rec["task"], expand, matcher, tolerate)
        p = ok / tot if tot else 0.0
        per_case[i] = (p, 1 - (1 - p) ** 2)
    proj = (25 + sum(p2 for _, p2 in per_case.values())) / 30
    # stability: passing-case samples still accepted?
    stable = tot_p = 0
    for i, rec in data["passing"].items():
        for conds in rec["samples"]:
            if conds and conds[0].startswith("<unparsed"):
                continue
            tot_p += 1
            stable += artifact_passes(conds, rec["task"], expand, matcher, tolerate)
    # adversarial per-condition leakage: adv condition grounds vs any failed task
    leaks = []
    for adv in ADV:
        for i, rec in data["failed"].items():
            tt = expand(base_tokens(rec["task"]))
            ct = expand(base_tokens(adv))
            if tt and matcher(ct, tt):
                leaks.append((adv[:40], int(i)))
    rows.append((name, per_case, proj, stable, tot_p, leaks))
    print(f"\n{name}")
    for i in sorted(per_case, key=int):
        p, p2 = per_case[i]
        print(f"   case {int(i):02d}: sample-accept {p:.2f} -> 2-attempt {p2:.2f}")
    print(f"   PROJECTED ROUND GATE-PASS: {proj:.1%}   "
          f"(passing stability {stable}/{tot_p})")
    if leaks:
        for a, i in leaks:
            print(f"   LEAK: '{a}' grounds vs case {i:02d}")
    else:
        print("   leakage: none on adversarial set (per-condition)")
json.dump(
    {name: {"per_case": pc, "proj": pr, "stable": [s, t], "leaks": lk}
     for name, pc, pr, s, t, lk in rows},
    open("/tmp/r2_gate_sim_results.json", "w"), indent=2, default=str)
print("\nsaved -> /tmp/r2_gate_sim_results.json")
