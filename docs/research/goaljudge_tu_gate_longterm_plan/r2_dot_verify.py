"""Verify the trailing-punctuation theory; decompose fix contributions;
inspect residual V1 failures; binomial power of the 95% gate at n=30 vs 101."""
import json, math, re, sys
sys.path.insert(0, ".")
from components.task_understanding import _STOPWORDS, _TOKEN, validate_conditions

def base_tokens(text):
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS}

print("== A. trailing-punct tokens in the 5 failed TASK texts ==")
tasks = json.load(open("/tmp/shadow_2a_r2_tasks.json"))
for i in [1, 10, 14, 17, 18]:
    dotted = [t for t in base_tokens(tasks[i]) if t != t.strip("._/-")]
    print(f"[{i:02d}] dotted-tokens: {dotted}")

def strip_punct(toks):
    return {t.strip("._/-") for t in toks} - {""}

def stem(t):
    for suf in ("ing", "ed", "es", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)]
    return t

def path_seg(toks):
    out = set(toks)
    for t in toks:
        if "/" in t or "." in t:
            out |= {s for s in re.split(r"[/.]", t) if len(s) >= 2 and s not in _STOPWORDS}
    return out

def fails(conds, task, xform):
    tt = xform(base_tokens(task))
    return [i for i, c in enumerate(conds)
            if tt and not (xform(base_tokens(c)) & tt)]

def passes(conds, task, xform):
    if validate_conditions(conds, task_input=task, source="user_edited"):
        return False
    return not fails(conds, task, xform)

# decomposed variants
XF = {
    "V0 exact": lambda s: s,
    "P  punct-strip only": strip_punct,
    "PS punct+stem": lambda s: {stem(t) for t in strip_punct(s)},
    "PSG punct+stem+pathseg": lambda s: {stem(t) for t in path_seg(strip_punct(s))} | path_seg(strip_punct(s)),
}
data = json.load(open("/tmp/r2_local_samples.json"))
print("\n== B. decomposition: failed-case sample-accept rate per variant ==")
for name, xf in XF.items():
    accs, tot = 0, 0
    percase = []
    for i, rec in sorted(data["failed"].items(), key=lambda kv: int(kv[0])):
        ok = sum(passes(c, rec["task"], xf) for c in rec["samples"]
                 if not (c and c[0].startswith("<unparsed")))
        n = sum(1 for c in rec["samples"] if not (c and c[0].startswith("<unparsed")))
        percase.append(f"{int(i):02d}:{ok}/{n}")
        accs += ok; tot += n
    print(f"  {name:26s} {accs}/{tot}   ({' '.join(percase)})")

print("\n== C. residual failures among PASSING-case samples under PSG ==")
xf = XF["PSG punct+stem+pathseg"]
for i, rec in sorted(data["passing"].items(), key=lambda kv: int(kv[0])):
    for s, conds in enumerate(rec["samples"]):
        if conds and conds[0].startswith("<unparsed"):
            continue
        f = fails(conds, rec["task"], xf)
        other = validate_conditions(conds, rec["task"], source="user_edited") if False else []
        if f:
            print(f"[P{int(i):02d}] s{s} task: {rec['task'][:80]}")
            for j in f:
                print(f"      cond[{j}]: {conds[j][:95]}")

print("\n== D. binomial power: P(pass >=95% gate) for true rate p ==")
def p_pass(n, p, bar):
    need = math.ceil(bar * n)
    return sum(math.comb(n, k) * p**k * (1-p)**(n-k) for k in range(need, n+1))
for n in (30, 101):
    row = "  ".join(f"p={p:.2f}:{p_pass(n, p, 0.95):.2f}" for p in (0.93, 0.95, 0.97, 0.98, 0.99))
    print(f"  n={n:3d}  need>={math.ceil(0.95*n)}  {row}")
