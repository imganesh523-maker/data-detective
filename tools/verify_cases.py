"""Runs every case through real Python using the same runtime the browser uses (js/runtime.py).

For every step it checks that:
  * the reference solution PASSES (with earlier steps replayed first, exactly like the game),
  * the untouched starter code does NOT pass,
  * hand-written wrong answers do NOT pass (and get a helpful message),
and that every briefing example runs without errors, and common errors get plain-English tips.

Run:  python tools/verify_cases.py      (exit code 1 on any failure)
"""
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "js"))
import runtime  # noqa: E402

os.chdir(ROOT / "data")
CASES = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))["cases"]

# Wrong answers: (case id, step index) -> list of code snippets that must FAIL
WRONG = {
    ("mango", 0): ["trucks = 12\ncrates_each = 400\ntotal_crates = trucks + crates_each\nprint(total_crates)",
                   "trucks = 12\ncrates_each = 400\ntotal_crates = trucks * crates_each"],
    ("mango", 1): ["trucks_left=[]\ncrates_arrived=[400]*11\ntotal_arrived = 0\nfor c in crates_arrived:\n    pass\nmissing_crates = 4800"],
    ("mango", 2): ["missing_truck = trucks_left[0]",
                   "missing_truck = None\nfor truck in trucks_left:\n    if truck in trucks_arrived:\n        missing_truck = truck"],
    ("reviews", 0): ["import csv\nreviews = list(csv.DictReader(open('case2_reviews.csv', encoding='utf-8')))\nphrase_count = 0\nfor r in reviews:\n    if 'best product ever' in r['text']:\n        phrase_count += 1"],
    ("reviews", 1): ["reviewer_counts = {}\nfor r in reviews:\n    reviewer_counts[r['reviewer']] = 1\ntop_reviewer = 'x'",
                     "from collections import Counter\nreviewer_counts = dict(Counter(r['reviewer'] for r in reviews))\ntop_reviewer = min(reviewer_counts, key=reviewer_counts.get)"],
    ("reviews", 2): ["def is_fake(r):\n    return 'best product ever' in r['text'].lower()\nfake_ids=[r['review_id'] for r in reviews if is_fake(r)]",
                     "def is_fake(r):\n    return r['stars'] == 5 and 'best product ever' in r['text'].lower()\nfake_ids=[r['review_id'] for r in reviews if is_fake(r)]"],
    ("railway", 0): ["import pandas as pd\ndf = pd.read_csv('case3_tickets.csv')\nn_tickets = df.shape[1]"],
    ("railway", 1): ["suspects = df[df['seconds_after_open'] < 20]",
                     "suspects = df[(df['quota'] == 'Tatkal') & (df['seconds_after_open'] <= 20)]"],
    ("railway", 2): ["fastest_pnr = suspects.sort_values('seconds_after_open', ascending=False)['pnr'].iloc[0]",
                     "fastest_pnr = suspects['pnr']"],
    ("railway", 3): ["racket_agent = suspects['agent_id'].value_counts().max()",
                     "racket_agent = 'SELF'"],
    ("power", 0): ["df = pd.read_csv('case4_meter_readings.csv')\nmissing_readings = df['units_billed'].isna()",
                   "df = pd.read_csv('case4_meter_readings.csv')\nmissing_readings = len(df)"],
    ("power", 1): ["df['area'] = df['area'].str.title()\ndf = df.dropna(subset=['units_billed'])",
                   "df['area'] = df['area'].str.strip().str.title()"],
    ("power", 2): ["billed = df.groupby('area')['units_billed'].mean()"],
    ("power", 3): ["supply = pd.read_csv('case4_feeder_supply.csv').set_index('area')['units_supplied']\nloss_pct = (supply - billed) / supply * 100\ntheft_area = loss_pct.idxmin()",
                   "supply = pd.read_csv('case4_feeder_supply.csv').set_index('area')['units_supplied']\nloss_pct = (supply - billed) / supply * 100\ntheft_area = loss_pct.max()"],
    ("cricket", 0): ["calls = pd.read_csv('case5_calls.csv')\nlate_calls = calls",
                     "calls = pd.read_csv('case5_calls.csv')\ncalls['call_time']=pd.to_datetime(calls['call_time'])\nlate_calls = calls[calls['call_time'].dt.hour <= 5]"],
    ("cricket", 1): ["players = pd.read_csv('case5_players.csv')\nlate_player_calls = calls.merge(players, left_on='to_number', right_on='phone')\nbookie_number = late_player_calls['from_number'].value_counts().idxmax()"],
    ("cricket", 2): ["bookie_calls = late_player_calls\npivot = bookie_calls.pivot_table(index='player_name', columns='team', values='duration_sec', aggfunc='sum', fill_value=0)\nmole = pivot.sum(axis=1).idxmin()"],
    ("cricket", 3): ["daily = bookie_calls.groupby(bookie_calls['call_time'].dt.date).size()\npeak_day = daily.idxmax()",
                     "import matplotlib.pyplot as plt\ndaily = bookie_calls.groupby(bookie_calls['call_time'].dt.date).size()\ndaily.plot(kind='bar')\npeak_day = daily.idxmin()"],
    ("heist", 0): ["tx = pd.read_csv('case6_transactions.csv')"],
    ("heist", 1): ["amounts = tx['amount'].to_numpy()\nz = (amounts - amounts.mean()) / amounts.std()\nsuspicious = tx[np.abs(z) > 0.5]"],
    ("heist", 2): ["accounts = pd.read_csv('case6_accounts.csv')\nlinked = suspicious.merge(accounts, left_on='to_acct', right_on='acct_id')\nmastermind = linked['holder_name'].iloc[-1] if linked['holder_name'].iloc[-1] != 'Jamnadas Holdings' else 'Riya Gupta'"],
    ("heist", 3): ["heist_total = linked['amount'].sum()"],
}

ERRORS = [  # code, exception name expected in title, phrase expected in the tip
    ("print(totl)", "NameError", "doesn't know anything called `totl`"),
    ("for i in range(3)\n    print(i)", "SyntaxError", "grammar"),
    ("if True:\nprint(1)", "IndentationError", "spaces"),
    ("x = '5' + 3", "TypeError", "mixed up types"),
    ("import pandas as pd\ndf = pd.DataFrame({'a':[1]})\ndf['b']", "KeyError", "column"),
    ("int('₹500')", "ValueError", "₹"),
    ("pd = 1\nopen('nope.csv')", "FileNotFoundError", "evidence locker"),
    ("[1,2][5]", "IndexError", "index 0"),
    ("import pandas as pd\ndf = pd.DataFrame({'q':['T','G'],'s':[1,30]})\ndf[df['q'] == 'T' & df['s'] < 20]", "Error", "EACH condition"),
    ("import pandas as pd\ndf = pd.DataFrame({'q':['T','G'],'s':[1,30]})\ndf[(df['q'] == 'T') and (df['s'] < 20)]", "ValueError", "use &"),
]

fails = 0
passes = 0


def ok(cond, label):
    global fails, passes
    if cond:
        passes += 1
        print("  PASS", label)
    else:
        fails += 1
        print("  FAIL", label)


for case in CASES:
    print(f"\nCase {case['num']}: {case['title']}")
    ex = runtime.run_example(case["briefing"]["example"])
    ok(ex["error"] is None, f"briefing example runs ({(ex['error'] or {}).get('title', 'ok')})")
    if case["id"] == "cricket":
        ok(len(ex["figures"]) == 1, "briefing example produces a chart image")
    prelude = []
    for i, step in enumerate(case["steps"]):
        res = runtime.run_step(prelude, step["solution"], step["check"])
        good = res["error"] is None and res["check"] and res["check"]["passed"]
        ok(good, f"step {i + 1} '{step['title']}' reference solution passes -> {res['check'] and res['check']['message']}"
           + (f" ERROR {res['error']}" if res["error"] else ""))
        st = runtime.run_step(prelude, step["starter"], step["check"])
        ok(not (st["check"] and st["check"]["passed"]), f"step {i + 1} starter code does not pass "
           f"({(st['error'] or {}).get('title') or st['check']['message'][:70]})")
        for w in WRONG.get((case["id"], i), []):
            if i == 0 and case["packages"]:
                w = "import pandas as pd\nimport numpy as np\n" + w
            wr = runtime.run_step(prelude, w, step["check"])
            msg = (wr["error"] or {}).get("title") or (wr["check"] or {}).get("message", "")
            ok(not (wr["check"] and wr["check"]["passed"]), f"step {i + 1} wrong answer rejected: {msg[:90]}")
        if case["id"] == "cricket" and i == 3:
            ok(len(res["figures"]) == 1, "step 4 chart rendered to PNG")
        prelude.append(step["solution"])

print("\nError explanations")
for code, name, phrase in ERRORS:
    r = runtime.run_step([], code, None)
    e = r["error"] or {}
    ok(name in e.get("title", "") and phrase in e.get("tip", ""), f"{name}: {e.get('tip', '')[:80]}")

# last-expression display
r = runtime.run_step([], "import pandas as pd\npd.DataFrame({'a':[1,2]})", None)
ok(r["display"] and r["display"]["kind"] == "html" and "<table" in r["display"]["html"], "DataFrame shown as HTML table")

print(f"\n{passes} passed, {fails} failed")
sys.exit(1 if fails else 0)
