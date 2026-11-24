"""Builds data/cases.json -- the story, lessons, steps, hints and answer-checkers for every case.

Expected answers are computed here from the CSV files, so story data and checkers can never drift
apart. Run:  python tools/build_cases.py   (after tools/generate_data.py)
tools/verify_cases.py then runs every reference solution (and wrong answers) through real Python.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"


def T(src, **kw):
    """Template: replace @@NAME@@ tokens (avoids fighting with Python's {} braces)."""
    src = src.strip("\n")
    for k, v in kw.items():
        src = src.replace(f"@@{k}@@", str(v))
    return src


# ============================================================== expected answers from the data
g = pd.read_csv(D / "case1_gate_log.csv")
arrived = g.dropna(subset=["crates_arrived"]).sort_values("arrival_time")
TRUCKS_LEFT = list(g.truck_no)
TRUCKS_ARRIVED = list(arrived.truck_no)
CRATES_ARRIVED = [int(c) for c in arrived.crates_arrived]
MISSING_TRUCK = [t for t in TRUCKS_LEFT if t not in TRUCKS_ARRIVED][0]
MISSING_DRIVER = g[g.truck_no == MISSING_TRUCK].driver.iloc[0]
TOTAL_ARRIVED = sum(CRATES_ARRIVED)

r = pd.read_csv(D / "case2_reviews.csv")
has_phrase = r.text.str.lower().str.contains("best product ever")
PHRASE_COUNT = int(has_phrase.sum())
PHRASE_CASE_SENSITIVE = int(r.text.str.contains("best product ever").sum())
REVIEWER_COUNTS = {k: int(v) for k, v in r.reviewer.value_counts().items()}
TOP_REVIEWER = r.reviewer.value_counts().idxmax()
FAKE_IDS = sorted(int(i) for i in r[has_phrase & (r.stars == 5)].review_id)

t = pd.read_csv(D / "case3_tickets.csv")
N_TICKETS = len(t)
sus = t[(t.quota == "Tatkal") & (t.seconds_after_open < 20)]
N_SUSPECTS = len(sus)
N_SUSPECTS_ALLQ = int((t.seconds_after_open < 20).sum())
N_SUSPECTS_LE = int(((t.quota == "Tatkal") & (t.seconds_after_open <= 20)).sum())
FASTEST_PNR = int(sus.sort_values("seconds_after_open").pnr.iloc[0])
RACKET_AGENT = sus.agent_id.value_counts().idxmax()
RACKET_COUNT = int(sus.agent_id.value_counts().max())

m = pd.read_csv(D / "case4_meter_readings.csv")
MISSING_READINGS = int(m.units_billed.isna().sum())
MESSY_AREAS = int(m.area.nunique())
mc = m.dropna(subset=["units_billed"]).copy()
mc["area"] = mc.area.str.strip().str.title()
CLEAN_ROWS = len(mc)
BILLED = {k: float(v) for k, v in mc.groupby("area").units_billed.sum().items()}
sup = pd.read_csv(D / "case4_feeder_supply.csv").set_index("area").units_supplied
loss = (sup - pd.Series(BILLED)) / sup * 100
THEFT_AREA = loss.idxmax()
THEFT_LOSS = round(float(loss.max()), 1)
NORMAL_LOSS = round(float(loss.drop(THEFT_AREA).mean()), 1)

calls = pd.read_csv(D / "case5_calls.csv")
calls["call_time"] = pd.to_datetime(calls.call_time)
players = pd.read_csv(D / "case5_players.csv")
matches = pd.read_csv(D / "case5_matches.csv")
late = calls[calls.call_time.dt.hour < 5]
N_LATE = len(late)
N_LATE_LE5 = int((calls.call_time.dt.hour <= 5).sum())
lpc = late.merge(players, left_on="to_number", right_on="phone")
N_LATE_PLAYER = len(lpc)
BOOKIE = lpc.from_number.value_counts().idxmax()
bk = lpc[lpc.from_number == BOOKIE]
MOLE = bk.groupby("player_name").duration_sec.sum().idxmax()
MOLE_TEAM = players[players.player_name == MOLE].team.iloc[0]
daily = bk.groupby(bk.call_time.dt.date).size()
PEAK_DAY = str(daily.idxmax())
FINAL = matches[matches.stage == "Final"].iloc[0]

tx = pd.read_csv(D / "case6_transactions.csv")
tx["amount"] = (tx.amount.str.replace("₹", "", regex=False).str.replace("Rs.", "", regex=False)
                .str.replace(",", "", regex=False).str.strip().astype(float))
TX_TOTAL = round(float(tx.amount.sum()), 2)
a = tx.amount.to_numpy()
z = (a - a.mean()) / a.std()
susp = tx[np.abs(z) > 3]
N_SUSP = len(susp)
acc = pd.read_csv(D / "case6_accounts.csv")
linked = susp.merge(acc, left_on="to_acct", right_on="acct_id")
MASTERMIND = linked.holder_name.value_counts().idxmax()
HEIST_TOTAL = float(linked[linked.holder_name == MASTERMIND].amount.sum())


def inr(x):
    """Indian digit grouping: 395384 -> 3,95,384"""
    s = f"{int(round(x))}"
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:]); head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


# shared checker helpers, prepended to every checker
H = '''
def _num(v):
    try:
        return float(v)
    except Exception:
        return None

def _need(ns, *names):
    for n in names:
        if n not in ns:
            return f"I can't find a variable called `{n}`. Create it exactly with that name (capitals matter)."
    return None
'''


def check(body, **kw):
    return H.strip("\n") + "\n\n" + T(body, **kw)


CASES = []

# ============================================================== CASE 1
CASES.append({
    "id": "mango",
    "num": 1,
    "title": "The Missing Mango Truck",
    "location": "Vashi APMC Fruit Market, Navi Mumbai · 4:55 AM",
    "concepts": ["variables", "print", "lists", "for loops", "if"],
    "packages": [],
    "files": ["case1_gate_log.csv"],
    "icon": "truck",
    "character": {
        "name": "Seth Jamnadas Khatri", "role": "Alphonso wholesaler, Vashi mandi",
        "quote": "Twelve trucks of Ratnagiri Hapus, Inspector! Do you know what one crate is worth in April?",
        "facts": ["Biggest mango trader in the market", "Reported the loss at 4:40 AM", "Insured his stock last week"],
    },
    "story": [
        "Peak mango season. The air at Vashi smells of straw, diesel and Alphonso.",
        "Seth Jamnadas swears twelve trucks left Ratnagiri last night, 400 crates each. The gate guard wrote every arrival in his register. Somewhere between the Konkan ghats and the mandi, one truck simply… vanished.",
        "Chief Inspector Fatima Qureshi drops the register on your desk. \"Your first case, rookie. No guesswork. Let the data talk.\"",
    ],
    "briefing": {
        "title": "Variables, print, lists, loops & if",
        "points": [
            "A <b>variable</b> is a labelled box: <code>crates = 400</code> stores 400 under the name <code>crates</code>.",
            "<code>print()</code> shows values in the console. Separate several things with commas.",
            "A <b>list</b> keeps many values in order: <code>[\"A\", \"B\", \"C\"]</code>. <code>len(list)</code> counts them.",
            "A <b>for loop</b> visits every item of a list, one by one. Lines inside it are indented by 4 spaces.",
            "<b>if / else</b> makes decisions. <code>==</code> compares, <code>in</code> / <code>not in</code> checks membership.",
        ],
        "example": T('''
crates = 400
mangoes = ["Alphonso", "Kesar", "Langda"]
print("We have", len(mangoes), "varieties")

for m in mangoes:
    if m == "Alphonso":
        print(m, "is the king of mangoes")
    else:
        print(m, "is also tasty")

print("Kesar" in mangoes, "Dasheri" not in mangoes)
'''),
    },
    "steps": [
        {
            "title": "Count the cargo",
            "task": "Seth-ji says <b>12 trucks</b> left Ratnagiri with <b>400 crates</b> each. Make variables <code>trucks</code> and <code>crates_each</code>, multiply them into <code>total_crates</code>, and <b>print</b> it.",
            "starter": T('''
# Step 1: store the facts in variables, multiply, print.
trucks =
crates_each =

total_crates =
print("Total crates loaded:", total_crates)
'''),
            "solution": T('''
trucks = 12
crates_each = 400

total_crates = trucks * crates_each
print("Total crates loaded:", total_crates)
'''),
            "hints": [
                "A variable is created with <code>=</code>: write the number after it, e.g. <code>trucks = 12</code>.",
                "Multiplication in Python is <code>*</code>, so <code>total_crates = trucks * crates_each</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "trucks", "crates_each", "total_crates")
    if e: return False, e
    if ns["trucks"] != 12 or ns["crates_each"] != 400:
        return False, "Re-read the statement: 12 trucks, 400 crates each. Check `trucks` and `crates_each`."
    if ns["total_crates"] != 4800:
        return False, f"`total_crates` is {ns['total_crates']!r}, but 12 trucks × 400 crates should be more than that. Use `*`."
    if "4800" not in out:
        return False, "The number is right but you never printed it. Detectives show their work: use print()."
    return True, "4,800 crates left Ratnagiri. That's our baseline."
'''),
        },
        {
            "title": "Read the gate register",
            "task": "The guard's register is typed up below as three lists. Use a <b>for loop</b> to add up <code>crates_arrived</code> into <code>total_arrived</code> (start it at 0). Then work out <code>missing_crates = total_crates - total_arrived</code> and print both.",
            "starter": T('''
# Evidence: case1_gate_log.csv, typed up from the guard's register
trucks_left = @@LEFT@@

trucks_arrived = @@ARR@@
crates_arrived = @@CRATES@@

total_arrived = 0
for c in crates_arrived:
    # add c to total_arrived here
    pass

missing_crates =
print("Arrived:", total_arrived, "| Missing:", missing_crates)
''', LEFT=json.dumps(TRUCKS_LEFT, ensure_ascii=False).replace('", "', '",\n               "'),
       ARR=json.dumps(TRUCKS_ARRIVED).replace('", "', '",\n                  "'), CRATES=json.dumps(CRATES_ARRIVED)),
            "solution": T('''
trucks_left = @@LEFT@@

trucks_arrived = @@ARR@@
crates_arrived = @@CRATES@@

total_arrived = 0
for c in crates_arrived:
    total_arrived = total_arrived + c

missing_crates = total_crates - total_arrived
print("Arrived:", total_arrived, "| Missing:", missing_crates)
''', LEFT=json.dumps(TRUCKS_LEFT), ARR=json.dumps(TRUCKS_ARRIVED), CRATES=json.dumps(CRATES_ARRIVED)),
            "hints": [
                "Inside the loop, replace <code>pass</code> with a line that grows the total: <code>total_arrived = total_arrived + c</code> (or the short form <code>total_arrived += c</code>).",
                "<code>total_crates</code> still exists from Step 1, so <code>missing_crates = total_crates - total_arrived</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "total_arrived", "missing_crates")
    if e: return False, e
    if ns["total_arrived"] == 0:
        return False, "`total_arrived` is still 0 - the loop never added anything. Replace `pass` with an addition."
    if ns["total_arrived"] != @@TA@@:
        return False, f"`total_arrived` is {ns['total_arrived']!r}. Add every number in `crates_arrived` exactly once."
    if ns["missing_crates"] != @@MC@@:
        return False, f"`missing_crates` is {ns['missing_crates']!r}. It should be crates loaded minus crates arrived."
    return True, "@@MC@@ crates missing. That's one whole truck - plus a few crates crushed on the ghats."
''', TA=TOTAL_ARRIVED, MC=4800 - TOTAL_ARRIVED),
        },
        {
            "title": "Find the ghost truck",
            "task": "Loop over <code>trucks_left</code> and use <code>if … not in trucks_arrived</code> to find the truck that never reached Vashi. Store its number in <code>missing_truck</code> and print it.",
            "starter": T('''
# trucks_left and trucks_arrived still exist from Step 2
missing_truck = None

for truck in trucks_left:
    # if this truck is not in trucks_arrived, remember it
    pass

print("Missing truck:", missing_truck)
'''),
            "solution": T('''
missing_truck = None

for truck in trucks_left:
    if truck not in trucks_arrived:
        missing_truck = truck

print("Missing truck:", missing_truck)
'''),
            "hints": [
                "Inside the loop write an <code>if</code> with the condition <code>truck not in trucks_arrived</code>, and end the line with a colon <code>:</code>.",
                "Inside the if (indented one more level), save it: <code>missing_truck = truck</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "missing_truck")
    if e: return False, e
    v = ns["missing_truck"]
    if v is None:
        return False, "`missing_truck` is still None. Your `if` never matched - check the condition uses `not in`."
    if v in ns.get("trucks_arrived", []):
        return False, f"{v} DID reach the gate - it's in `trucks_arrived`. You want the one that is NOT there."
    if v != "@@MT@@":
        return False, f"`missing_truck` is {v!r}. That doesn't match any truck that went missing."
    return True, "@@MT@@ never reached Vashi. Found on paper - now let's find it on the road."
''', MT=MISSING_TRUCK),
        },
    ],
    "closing": [
        f"Truck {MISSING_TRUCK} is found parked behind a dhaba near Panvel, GPS switched off. Driver {MISSING_DRIVER} is drinking his fourth cutting chai.",
        "The cargo bay is empty. It was always empty - the 400 crates were only 'loaded' on paper.",
        "\"A man paid me to take a long tea break,\" the driver mumbles. \"Cash. He said: the Accountant sends his regards.\"",
        "Seth Jamnadas thanks you loudly and files his insurance claim the same afternoon. Case closed… for now.",
    ],
})

# ============================================================== CASE 2
CASES.append({
    "id": "reviews",
    "num": 2,
    "title": "The Fake Review Shop",
    "location": "Lamington Road electronics bazaar, Mumbai · 11:20 AM",
    "concepts": ["strings", "dictionaries", "functions"],
    "packages": [],
    "files": ["case2_reviews.csv"],
    "icon": "star",
    "character": {
        "name": "Prof. Dinesh Bhatia", "role": "Retired physics teacher, complainant",
        "quote": "4.9 stars, they said. The TV died before the India-Pakistan match even started!",
        "facts": ["Bought a 32-inch TV from Sharma Electronics online", "Shop rating: 4.9 / 5", "Refund refused twice"],
    },
    "story": [
        "Sharma Electronics has the best rating on Lamington Road. Suspiciously the best.",
        "Prof. Bhatia's TV gave up in two days. When he read the reviews again, he noticed they all sounded… the same. \"Best product ever!!!\" Over and over.",
        "You pull every review from the shop's page. Time to separate real customers from the bots.",
    ],
    "briefing": {
        "title": "Strings, dictionaries & functions",
        "points": [
            "A <b>string</b> is text. <code>.lower()</code> makes it lowercase, <code>.strip()</code> trims spaces, and <code>\"ever\" in text</code> checks if a phrase appears.",
            "A <b>dictionary</b> maps keys to values: <code>{\"ravi\": 3}</code>. Read with <code>d[\"ravi\"]</code>; <code>d.get(k, 0)</code> gives 0 if the key is missing - perfect for counting.",
            "A <b>function</b> packages logic you can reuse: <code>def name(input):</code> … <code>return answer</code>.",
            "Data from a CSV file arrives as text, so <code>\"5\"</code> is not <code>5</code>. Convert with <code>int()</code>.",
        ],
        "example": T('''
review = "  BEST product EVER!!! "
print(review.strip().lower())
print("ever" in review.lower())

counts = {}
for name in ["ravi", "anu", "ravi"]:
    counts[name] = counts.get(name, 0) + 1
print(counts)

def stars_label(stars):
    if int(stars) >= 4:
        return "happy"
    return "unhappy"

print(stars_label("5"), stars_label(2))
'''),
    },
    "steps": [
        {
            "title": "Spot the catchphrase",
            "task": "Each review is a dictionary (see the console). Count how many reviews contain the phrase <b>\"best product ever\"</b> in <i>any</i> capitalisation. Store the count in <code>phrase_count</code>.",
            "starter": T('''
import csv

# Evidence: every row of case2_reviews.csv becomes a dictionary
reviews = list(csv.DictReader(open("case2_reviews.csv", encoding="utf-8")))
print(len(reviews), "reviews loaded. First one:")
print(reviews[0])

phrase_count = 0
for r in reviews:
    text = r["text"]
    # make text lowercase, then check for the phrase

print("Reviews with the phrase:", phrase_count)
'''),
            "solution": T('''
import csv

reviews = list(csv.DictReader(open("case2_reviews.csv", encoding="utf-8")))

phrase_count = 0
for r in reviews:
    text = r["text"]
    if "best product ever" in text.lower():
        phrase_count += 1

print("Reviews with the phrase:", phrase_count)
'''),
            "hints": [
                "Some bots SHOUT it in capitals. Compare against <code>text.lower()</code>, not <code>text</code>.",
                "Inside the loop: <code>if \"best product ever\" in text.lower():</code> then <code>phrase_count += 1</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "phrase_count")
    if e: return False, e
    v = ns["phrase_count"]
    if v == @@CS@@ and v != @@PC@@:
        return False, f"You found {v}, but some reviews write it as 'BEST PRODUCT EVER' or 'Best Product Ever'. Lowercase the text first."
    if v != @@PC@@:
        return False, f"`phrase_count` is {v!r}. Count each review that contains the phrase once (any capitals)."
    return True, "@@PC@@ reviews use the exact same catchphrase. Real customers don't talk like that."
''', PC=PHRASE_COUNT, CS=PHRASE_CASE_SENSITIVE),
        },
        {
            "title": "Who writes the most?",
            "task": "Build a dictionary <code>reviewer_counts</code> that maps each reviewer to the number of reviews they wrote. Then find <code>top_reviewer</code> - the name with the biggest count.",
            "starter": T('''
reviewer_counts = {}
for r in reviews:
    name = r["reviewer"]
    # increase this reviewer's count by 1


# find the reviewer with the highest count
top_reviewer = None

print(top_reviewer, reviewer_counts.get(top_reviewer))
'''),
            "solution": T('''
reviewer_counts = {}
for r in reviews:
    name = r["reviewer"]
    reviewer_counts[name] = reviewer_counts.get(name, 0) + 1

top_reviewer = None
for name in reviewer_counts:
    if top_reviewer is None or reviewer_counts[name] > reviewer_counts[top_reviewer]:
        top_reviewer = name

print(top_reviewer, reviewer_counts.get(top_reviewer))
'''),
            "hints": [
                "Counting pattern: <code>reviewer_counts[name] = reviewer_counts.get(name, 0) + 1</code>.",
                "Shortcut for the biggest: <code>top_reviewer = max(reviewer_counts, key=reviewer_counts.get)</code>. Or loop and keep the best so far.",
            ],
            "check": check('''
EXPECTED = @@RC@@
def check(ns, out):
    e = _need(ns, "reviewer_counts", "top_reviewer")
    if e: return False, e
    rc = ns["reviewer_counts"]
    if not isinstance(rc, dict) or len(rc) == 0:
        return False, "`reviewer_counts` should be a dictionary filled with names → counts. It's empty or not a dict."
    if dict(rc) != EXPECTED:
        wrong = [k for k in EXPECTED if rc.get(k) != EXPECTED[k]][:2]
        return False, f"Some counts are off (e.g. {wrong}). Each review should add exactly 1 to its reviewer."
    if ns["top_reviewer"] != "@@TOP@@":
        return False, f"`top_reviewer` is {ns['top_reviewer']!r}, but someone else wrote more reviews. Look for the maximum count."
    return True, "@@TOP@@ wrote @@N@@ reviews - all on the same day. A bot account if ever there was one."
''', RC=repr(REVIEWER_COUNTS), TOP=TOP_REVIEWER, N=REVIEWER_COUNTS[TOP_REVIEWER]),
        },
        {
            "title": "Build the fake-detector",
            "task": "Write a function <code>is_fake(review)</code> that returns <code>True</code> when the review has <b>5 stars</b> AND contains \"best product ever\" (any case), else <code>False</code>. Use it to make <code>fake_ids</code>: a list of the <code>review_id</code>s of all fakes.",
            "starter": T('''
def is_fake(review):
    stars = int(review["stars"])      # CSV text -> number
    text = review["text"].lower()
    # return True only if both conditions hold
    return False

fake_ids = []
for r in reviews:
    # if is_fake(r), add r["review_id"] to fake_ids
    pass

print(len(fake_ids), "fake reviews:", fake_ids[:5], "...")
'''),
            "solution": T('''
def is_fake(review):
    stars = int(review["stars"])
    text = review["text"].lower()
    return stars == 5 and "best product ever" in text

fake_ids = []
for r in reviews:
    if is_fake(r):
        fake_ids.append(r["review_id"])

print(len(fake_ids), "fake reviews:", fake_ids[:5], "...")
'''),
            "hints": [
                "Combine two conditions with <code>and</code>: <code>return stars == 5 and \"best product ever\" in text</code>.",
                "Add to a list with <code>fake_ids.append(r[\"review_id\"])</code> inside <code>if is_fake(r):</code>.",
            ],
            "check": check('''
FAKE = @@IDS@@
def check(ns, out):
    e = _need(ns, "is_fake", "fake_ids")
    if e: return False, e
    f = ns["is_fake"]
    if not callable(f):
        return False, "`is_fake` should be a function (def is_fake(review): ...)."
    tests = [
        ({"stars": "5", "text": "BEST product ever!!"}, True),
        ({"stars": "4", "text": "best product ever"}, False),
        ({"stars": "5", "text": "Nice TV, works well"}, False),
        ({"stars": "1", "text": "worst purchase"}, False),
    ]
    for rev, want in tests:
        try:
            got = f(dict(rev, review_id="0", reviewer="x", product="x", date="x"))
        except Exception as ex:
            return False, f"is_fake crashed on a test review {rev}: {type(ex).__name__}: {ex}"
        if bool(got) != want:
            return False, f"is_fake({rev}) returned {got!r} but should return {want}. Both conditions must hold."
    try:
        ids = sorted(int(x) for x in ns["fake_ids"])
    except Exception:
        return False, "`fake_ids` should be a list of review ids."
    if len(ids) == len(FAKE) + 1:
        return False, "One of your 'fakes' is an honest 4-star customer who just used the phrase. Check the stars too."
    if ids != FAKE:
        return False, f"You have {len(ids)} ids, expected {len(FAKE)}. Every review where is_fake(r) is True, each id once."
    return True, f"{len(FAKE)} fake reviews identified - and one honest customer cleared."
''', IDS=repr(FAKE_IDS)),
        },
    ],
    "closing": [
        f"All {len(FAKE_IDS)} fake reviews were posted on the same day from three accounts registered to one phone number.",
        "The 'digital marketing agency' behind them charged ₹5 per review. Its invoices were paid by an account named only 'A.'",
        "Sharma Electronics' rating drops to 2.1 overnight. Prof. Bhatia gets his refund - and a new TV for the World Cup.",
        "Someone is funding small frauds all over the city. You pin a new card on the board: THE ACCOUNTANT?",
    ],
})

# ============================================================== CASE 3
CASES.append({
    "id": "railway",
    "num": 3,
    "title": "The Railway Ticket Racket",
    "location": "CSMT reservation office, Mumbai · 10:00:00 AM sharp",
    "concepts": ["pandas", "read_csv", "head", "filtering", "sort_values", "value_counts"],
    "packages": ["pandas"],
    "files": ["case3_tickets.csv"],
    "icon": "train",
    "character": {
        "name": "Albert D'Souza", "role": "Chief Reservation Supervisor, CSMT",
        "quote": "Tatkal opens at ten. By ten-oh-oh-twenty, Rajdhani is full. No human types that fast, men!",
        "facts": ["34 years with the railways", "Has never missed a 9:15 local", "Suspects auto-fill software"],
    },
    "story": [
        "Every morning at 10:00 sharp, Tatkal booking opens - and every morning honest passengers stare at WAITLIST.",
        "Mr. D'Souza has pulled the booking log for one day's trains. Each row is one ticket: who booked it, through which agent, and how many seconds after the window opened.",
        "Lists and loops won't cut it for hundreds of rows. Time to meet your new partner: pandas.",
    ],
    "briefing": {
        "title": "Pandas DataFrames: load, look, filter, sort",
        "points": [
            "<b>pandas</b> gives you a <b>DataFrame</b> - an Excel sheet inside Python. <code>pd.read_csv(\"file.csv\")</code> loads one.",
            "<code>df.head()</code> shows the first rows, <code>df.shape</code> is (rows, columns), <code>len(df)</code> is the row count.",
            "<code>df[\"fare\"]</code> picks a column. <code>df[df[\"fare\"] > 1500]</code> keeps only rows where the condition is True.",
            "Combine conditions with <code>&</code> (and) / <code>|</code> (or), each in brackets: <code>df[(a) & (b)]</code>.",
            "<code>df.sort_values(\"col\")</code> sorts; <code>df[\"col\"].value_counts()</code> counts each value, biggest first.",
            "Tip: if your <b>last line</b> is just a value, the console shows it as a table - no print needed.",
        ],
        "example": T('''
import pandas as pd

df = pd.DataFrame({
    "train": ["Rajdhani", "Duronto", "Shatabdi", "Garib Rath"],
    "fare":  [2550, 1900, 1200, 900],
    "quota": ["Tatkal", "General", "Tatkal", "General"],
})
print(df.shape)
print(df[(df["fare"] > 1000) & (df["quota"] == "Tatkal")])
df.sort_values("fare")
'''),
    },
    "steps": [
        {
            "title": "Open the booking log",
            "task": "Import pandas as <code>pd</code>, load <b>case3_tickets.csv</b> into <code>df</code>, and store the number of rows in <code>n_tickets</code>. End with <code>df.head()</code> to peek at the data.",
            "starter": T('''
import pandas as pd

df = pd.read_csv("")      # put the file name inside the quotes
n_tickets =

df.head()
'''),
            "solution": T('''
import pandas as pd

df = pd.read_csv("case3_tickets.csv")
n_tickets = len(df)

df.head()
'''),
            "hints": [
                "The file name goes inside the quotes: <code>pd.read_csv(\"case3_tickets.csv\")</code>.",
                "<code>len(df)</code> gives the number of rows (or <code>df.shape[0]</code>).",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "df", "n_tickets")
    if e: return False, e
    import pandas as pd
    if not isinstance(ns["df"], pd.DataFrame):
        return False, "`df` should be a DataFrame made by pd.read_csv(...)."
    if ns["n_tickets"] == @@C@@:
        return False, "That's the number of columns. You want the number of rows: len(df)."
    if ns["n_tickets"] != @@N@@:
        return False, f"`n_tickets` is {ns['n_tickets']!r}. Count the rows of df with len(df)."
    return True, "@@N@@ tickets in the log. Notice the seconds_after_open column…"
''', N=N_TICKETS, C=t.shape[1]),
        },
        {
            "title": "Too fast to be human",
            "task": "Make <code>suspects</code>: only rows where <code>quota</code> is <b>\"Tatkal\"</b> AND <code>seconds_after_open</code> is <b>less than 20</b>. Show how many there are.",
            "starter": T('''
suspects = df[ ]     # put two conditions inside, joined with &

print(len(suspects), "suspicious Tatkal bookings")
suspects.head()
'''),
            "solution": T('''
suspects = df[(df["quota"] == "Tatkal") & (df["seconds_after_open"] < 20)]

print(len(suspects), "suspicious Tatkal bookings")
suspects.head()
'''),
            "hints": [
                "Each condition looks like <code>(df[\"quota\"] == \"Tatkal\")</code> - note the brackets around it.",
                "Join them with <code>&</code>: <code>df[(cond1) & (cond2)]</code> with <code>cond2 = df[\"seconds_after_open\"] < 20</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "suspects")
    if e: return False, e
    import pandas as pd
    s = ns["suspects"]
    if not isinstance(s, pd.DataFrame):
        return False, "`suspects` should be a filtered DataFrame: df[ ...conditions... ]."
    n = len(s)
    if n == @@ALLQ@@ and n != @@N@@:
        return False, "Close! But some of those are General/Ladies quota. Add the condition quota == 'Tatkal'."
    if n == @@LE@@ and n != @@N@@:
        return False, "Use strictly less than 20 (<), not <= 20."
    if n != @@N@@ or set(s["quota"]) != {"Tatkal"} or s["seconds_after_open"].max() >= 20:
        return False, f"You have {n} rows. Keep only Tatkal rows with seconds_after_open < 20."
    return True, "@@N@@ tickets booked in under 20 seconds. Filling a passenger form takes a human about a minute."
''', N=N_SUSPECTS, ALLQ=N_SUSPECTS_ALLQ, LE=N_SUSPECTS_LE),
        },
        {
            "title": "The fastest finger",
            "task": "Sort <code>suspects</code> by <code>seconds_after_open</code> (smallest first) and store the <b>PNR</b> of the very first row in <code>fastest_pnr</code>.",
            "starter": T('''
ranked = suspects.sort_values( )

fastest_pnr =
print("Fastest booking PNR:", fastest_pnr)
ranked.head(3)
'''),
            "solution": T('''
ranked = suspects.sort_values("seconds_after_open")

fastest_pnr = ranked["pnr"].iloc[0]
print("Fastest booking PNR:", fastest_pnr)
ranked.head(3)
'''),
            "hints": [
                "<code>suspects.sort_values(\"seconds_after_open\")</code> sorts smallest to largest.",
                "Take the first value of the pnr column: <code>ranked[\"pnr\"].iloc[0]</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "fastest_pnr")
    if e: return False, e
    v = ns["fastest_pnr"]
    try:
        v = int(str(v).strip())
    except Exception:
        return False, f"`fastest_pnr` should be a single PNR number, but it's {type(v).__name__}. Use .iloc[0] to pick one value."
    if v != @@P@@:
        return False, "That's not the fastest booking. Sort ascending (smallest seconds first) and take row 0."
    return True, "PNR @@P@@ - booked 1 second after opening. Impossible by hand."
''', P=FASTEST_PNR),
        },
        {
            "title": "Name the agent",
            "task": "Which <code>agent_id</code> appears most often among the suspects? Use <code>value_counts()</code> and store the agent in <code>racket_agent</code>.",
            "starter": T('''
counts = suspects["agent_id"].value_counts()
print(counts)

racket_agent =
'''),
            "solution": T('''
counts = suspects["agent_id"].value_counts()
print(counts)

racket_agent = counts.index[0]
'''),
            "hints": [
                "value_counts() sorts biggest first, so the top agent is the first label: <code>counts.index[0]</code>.",
                "Or use <code>counts.idxmax()</code> - the label with the maximum count.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "racket_agent")
    if e: return False, e
    v = ns["racket_agent"]
    import numbers
    if isinstance(v, numbers.Number) and not isinstance(v, bool):
        return False, f"{v} is a count, not an agent. You want the label (index), e.g. counts.index[0]."
    if str(v).strip() != "@@A@@":
        return False, f"{v!r} isn't the agent with the most suspicious bookings. Check value_counts() again."
    return True, "@@A@@ - @@K@@ lightning-fast Tatkal tickets. Busted."
''', A=RACKET_AGENT, K=RACKET_COUNT),
        },
    ],
    "closing": [
        f"Agent {RACKET_AGENT} runs 'Lucky Travels' out of a one-room office in Kurla: three laptops, one illegal auto-fill bot, booking in under 2 seconds.",
        "Each ticket was resold at three times the fare to desperate families.",
        "In a drawer, a ledger of monthly 'software licence' payments - all to the same account. Initial: 'A.'",
        "Mr. D'Souza makes his 9:15 local on time. Tatkal is fair again. Your evidence board is getting crowded.",
    ],
})

# ============================================================== CASE 4
CASES.append({
    "id": "power",
    "num": 4,
    "title": "The Power Theft Grid",
    "location": "City Power Board, Ward Office · 9:40 PM, during a blackout",
    "concepts": ["missing values", "cleaning text", "groupby", "aggregation"],
    "packages": ["pandas"],
    "files": ["case4_meter_readings.csv", "case4_feeder_supply.csv"],
    "icon": "bolt",
    "character": {
        "name": "Er. Meenakshi Iyer", "role": "Executive Engineer, City Power Board",
        "quote": "We pump the power in, the meters say it never arrived. Electricity doesn't evaporate, Inspector.",
        "facts": ["Runs 5 neighbourhood feeders", "Normal line loss: under 10%", "Meter readers 'type creatively'"],
    },
    "story": [
        "Three blackouts this week. The transformers are overloaded, but the bills say people are using less than ever.",
        "Somewhere, someone has hooked a cable straight onto the line. Er. Iyer hands you three months of meter readings and the substation supply log.",
        "Warning: the readings are messy. Meter readers spelled area names five different ways, and some meters were never read.",
    ],
    "briefing": {
        "title": "Cleaning data, missing values & groupby",
        "points": [
            "Missing values show up as <code>NaN</code>. <code>df[\"col\"].isna().sum()</code> counts them; <code>df.dropna(subset=[\"col\"])</code> removes those rows.",
            "Text columns have string tools under <code>.str</code>: <code>df[\"area\"].str.strip().str.title()</code> trims spaces and fixes capitals.",
            "<code>df[\"area\"].nunique()</code> counts distinct values - great for spotting messy spellings.",
            "<b>groupby</b> = split, compute, combine: <code>df.groupby(\"area\")[\"units\"].sum()</code> gives one total per area.",
            "Two Series with the same labels can be combined directly: <code>(a - b) / a * 100</code> lines them up by label.",
        ],
        "example": T('''
import pandas as pd

df = pd.DataFrame({
    "area":  ["Powai", "powai ", "Juhu", " JUHU", "Juhu"],
    "units": [120, None, 300, 150, 90],
})
print("Missing:", df["units"].isna().sum(), "| Spellings:", df["area"].nunique())

df["area"] = df["area"].str.strip().str.title()
df = df.dropna(subset=["units"])
df.groupby("area")["units"].agg(["sum", "mean", "count"])
'''),
    },
    "steps": [
        {
            "title": "Count the blind spots",
            "task": "Load <b>case4_meter_readings.csv</b> into <code>df</code>. Count the missing values in <code>units_billed</code> and store it in <code>missing_readings</code>. Also print how many different area spellings there are.",
            "starter": T('''
import pandas as pd

df = pd.read_csv("case4_meter_readings.csv")

missing_readings =
print("Missing readings:", missing_readings)
print("Area spellings:", df["area"].nunique())
df["area"].unique()
'''),
            "solution": T('''
import pandas as pd

df = pd.read_csv("case4_meter_readings.csv")

missing_readings = df["units_billed"].isna().sum()
print("Missing readings:", missing_readings)
print("Area spellings:", df["area"].nunique())
df["area"].unique()
'''),
            "hints": [
                "<code>df[\"units_billed\"].isna()</code> gives True/False per row. True counts as 1 when you add them up.",
                "<code>missing_readings = df[\"units_billed\"].isna().sum()</code>",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "missing_readings")
    if e: return False, e
    v = _num(ns["missing_readings"])
    if v is None:
        return False, "`missing_readings` should be a single number. Did you forget .sum() at the end?"
    if v != @@M@@:
        return False, f"`missing_readings` is {ns['missing_readings']!r}. Count NaN values in units_billed with .isna().sum()."
    return True, "@@M@@ unread meters, and @@A@@ spellings for what should be 5 areas. Time to clean."
''', M=MISSING_READINGS, A=MESSY_AREAS),
        },
        {
            "title": "Clean the mess",
            "task": "Fix the <code>area</code> column with <code>.str.strip().str.title()</code> so each area has one spelling, and drop rows where <code>units_billed</code> is missing. Keep the result in <code>df</code>.",
            "starter": T('''
df["area"] =
df =                      # drop rows with missing units_billed

print("Areas now:", df["area"].nunique(), "| Rows:", len(df))
df["area"].value_counts()
'''),
            "solution": T('''
df["area"] = df["area"].str.strip().str.title()
df = df.dropna(subset=["units_billed"])

print("Areas now:", df["area"].nunique(), "| Rows:", len(df))
df["area"].value_counts()
'''),
            "hints": [
                "Chain string methods: <code>df[\"area\"].str.strip().str.title()</code> turns \" LOTUS colony \" into \"Lotus Colony\".",
                "<code>df = df.dropna(subset=[\"units_billed\"])</code> - and remember to assign it back to <code>df</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "df")
    if e: return False, e
    df = ns["df"]
    if "area" not in df or "units_billed" not in df:
        return False, "`df` lost its columns. Keep working on the same DataFrame."
    if df["area"].nunique() != 5:
        return False, f"There are still {df['area'].nunique()} area spellings. Use .str.strip() AND .str.title()."
    if df["units_billed"].isna().sum() > 0:
        return False, "There are still missing units_billed values. Use df = df.dropna(subset=['units_billed'])."
    if len(df) != @@R@@:
        return False, f"df has {len(df)} rows - expected @@R@@. Only drop rows where units_billed is missing."
    return True, "5 clean areas, @@R@@ trustworthy readings."
''', R=CLEAN_ROWS),
        },
        {
            "title": "Total by area",
            "task": "Use <code>groupby</code> to total <code>units_billed</code> for each area. Store the result (a Series) in <code>billed</code>.",
            "starter": T('''
billed =

billed
'''),
            "solution": T('''
billed = df.groupby("area")["units_billed"].sum()

billed
'''),
            "hints": [
                "Pattern: <code>df.groupby(\"column to group by\")[\"column to add\"].sum()</code>.",
                "<code>billed = df.groupby(\"area\")[\"units_billed\"].sum()</code>",
            ],
            "check": check('''
B = @@B@@
def check(ns, out):
    e = _need(ns, "billed")
    if e: return False, e
    b = ns["billed"]
    try:
        got = {str(k): float(v) for k, v in dict(b).items()}
    except Exception:
        return False, "`billed` should be a Series with one total per area (from groupby + sum)."
    if set(got) != set(B):
        return False, f"I expected the 5 areas as labels, but got {sorted(got)[:6]}. Group by 'area' after cleaning."
    for k in B:
        if abs(got[k] - B[k]) > 0.5:
            return False, f"The total for {k} is {got[k]:,.0f}; check you used .sum() on units_billed."
    return True, "Billed totals ready. Now compare them with what the substation actually sent."
''', B=repr(BILLED)),
        },
        {
            "title": "Follow the missing power",
            "task": "The supply log is loaded for you as <code>supply</code>. Compute <code>loss_pct = (supply - billed) / supply * 100</code>, then set <code>theft_area</code> to the area with the <b>biggest</b> loss.",
            "starter": T('''
supply = pd.read_csv("case4_feeder_supply.csv").set_index("area")["units_supplied"]

loss_pct =
print(loss_pct.round(1).sort_values())

theft_area =
'''),
            "solution": T('''
supply = pd.read_csv("case4_feeder_supply.csv").set_index("area")["units_supplied"]

loss_pct = (supply - billed) / supply * 100
print(loss_pct.round(1).sort_values())

theft_area = loss_pct.idxmax()
'''),
            "hints": [
                "pandas lines up the two Series by area name, so you can write the formula exactly as given.",
                "<code>loss_pct.idxmax()</code> returns the label (area) of the largest value.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "loss_pct", "theft_area")
    if e: return False, e
    try:
        lp = float(ns["loss_pct"]["@@T@@"])
    except Exception:
        return False, "`loss_pct` should be a Series with one percentage per area."
    if abs(lp - @@L@@) > 0.6:
        return False, f"Loss for @@T@@ came out as {lp:.1f}%. Formula: (supply - billed) / supply * 100."
    v = ns["theft_area"]
    if isinstance(v, (int, float)):
        return False, "That's a percentage, not an area. Use .idxmax() to get the label."
    if str(v) != "@@T@@":
        return False, f"{v!r} doesn't have the biggest loss. Use loss_pct.idxmax()."
    return True, "@@T@@ is losing @@L@@% of its power. Everyone else: about @@N@@%."
''', T=THEFT_AREA, L=THEFT_LOSS, N=NORMAL_LOSS),
        },
    ],
    "closing": [
        f"A night raid in {THEFT_AREA}. Behind a shuttered godown: a thick illegal cable hooked onto the main line.",
        "Inside, forty humming freezers - an unlicensed cold storage, stacked to the roof with mango crates.",
        "The godown's lease is in the name of a company you've seen before on a ledger: 'J. Holdings'.",
        "The lights come back on across the ward. Er. Iyer nods. \"Electricity doesn't evaporate. Told you.\"",
    ],
})

# ============================================================== CASE 5
CASES.append({
    "id": "cricket",
    "num": 5,
    "title": "The Cricket Betting Ring",
    "location": "Mumbai Monsoon League final, Shivaji Park · 11:58 PM",
    "concepts": ["datetime", "merge / join", "pivot_table", "matplotlib charts"],
    "packages": ["pandas", "matplotlib"],
    "files": ["case5_calls.csv", "case5_players.csv", "case5_matches.csv"],
    "icon": "bat",
    "character": {
        "name": "Coach Daisy Fernandes", "role": "Head coach, Bandra Blasters",
        "quote": "Three dropped catches and a run-out a child could avoid. In a FINAL. Somebody sold this match.",
        "facts": ["Undefeated in the league stage", "Lost the final by 4 runs", "Trusts her players. Mostly."],
    },
    "story": [
        "The Bandra Blasters cruised through the league, then collapsed in the final. The crowd at Shivaji Park went silent.",
        "Cyber Cell seized phone records from a number linked to a known bookie den. You also have the team rosters and the match schedule.",
        "Bookies call at night, when nobody is watching. Let's see who was awake.",
    ],
    "briefing": {
        "title": "Dates, joins, pivots & charts",
        "points": [
            "<code>pd.to_datetime(df[\"col\"])</code> turns text into real dates; then <code>.dt.hour</code>, <code>.dt.date</code>, <code>.dt.day_name()</code> unlock the parts.",
            "<b>merge</b> joins two tables on matching values: <code>a.merge(b, left_on=\"to_number\", right_on=\"phone\")</code> - like VLOOKUP, but better.",
            "<b>pivot_table</b> reshapes data into a grid: rows from one column, columns from another, cells aggregated.",
            "<b>matplotlib</b> draws charts. <code>series.plot(kind=\"bar\")</code> is the quickest way - the chart appears in the console.",
        ],
        "example": T('''
import pandas as pd
import matplotlib.pyplot as plt

calls = pd.DataFrame({"to": ["A", "B", "A", "A"],
                      "time": ["2026-08-01 01:15", "2026-08-01 14:00",
                               "2026-08-02 02:40", "2026-08-02 03:05"]})
people = pd.DataFrame({"phone": ["A", "B"], "name": ["Asha", "Sana"]})

calls["time"] = pd.to_datetime(calls["time"])
calls["hour"] = calls["time"].dt.hour
both = calls.merge(people, left_on="to", right_on="phone")
print(both)
both["name"].value_counts().plot(kind="bar", title="Calls per person")
plt.show()
'''),
    },
    "steps": [
        {
            "title": "Who calls after midnight?",
            "task": "Load <b>case5_calls.csv</b> into <code>calls</code>, convert <code>call_time</code> to datetime, and make <code>late_calls</code>: calls whose hour is <b>before 5 AM</b> (hour &lt; 5).",
            "starter": T('''
import pandas as pd

calls = pd.read_csv("case5_calls.csv")
calls["call_time"] =            # convert text -> datetime

late_calls =                    # hour < 5
print(len(late_calls), "calls between midnight and 5 AM")
late_calls.head()
'''),
            "solution": T('''
import pandas as pd

calls = pd.read_csv("case5_calls.csv")
calls["call_time"] = pd.to_datetime(calls["call_time"])

late_calls = calls[calls["call_time"].dt.hour < 5]
print(len(late_calls), "calls between midnight and 5 AM")
late_calls.head()
'''),
            "hints": [
                "<code>calls[\"call_time\"] = pd.to_datetime(calls[\"call_time\"])</code>",
                "Filter with the hour part: <code>calls[calls[\"call_time\"].dt.hour < 5]</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "calls", "late_calls")
    if e: return False, e
    import pandas as pd
    c = ns["calls"]
    if not pd.api.types.is_datetime64_any_dtype(c["call_time"]):
        return False, "`call_time` is still text. Convert it: calls['call_time'] = pd.to_datetime(calls['call_time'])."
    n = len(ns["late_calls"])
    if n == @@LE@@ and n != @@N@@:
        return False, "Use hour < 5 (midnight to 4:59 AM), not <= 5."
    if n != @@N@@:
        return False, f"`late_calls` has {n} rows. Keep rows where calls['call_time'].dt.hour < 5."
    return True, "@@N@@ late-night calls. Not all of them are to cricketers, though."
''', N=N_LATE, LE=N_LATE_LE5),
        },
        {
            "title": "Join the rosters",
            "task": "Load <b>case5_players.csv</b> as <code>players</code>. Merge it with <code>late_calls</code> (<code>to_number</code> ↔ <code>phone</code>) into <code>late_player_calls</code>. Then set <code>bookie_number</code> to the caller (<code>from_number</code>) who appears most.",
            "starter": T('''
players = pd.read_csv("case5_players.csv")

late_player_calls = late_calls.merge( )

print(len(late_player_calls), "late calls went to players")
bookie_number =
print("Most frequent caller:", bookie_number)
'''),
            "solution": T('''
players = pd.read_csv("case5_players.csv")

late_player_calls = late_calls.merge(players, left_on="to_number", right_on="phone")

print(len(late_player_calls), "late calls went to players")
bookie_number = late_player_calls["from_number"].value_counts().idxmax()
print("Most frequent caller:", bookie_number)
'''),
            "hints": [
                "<code>late_calls.merge(players, left_on=\"to_number\", right_on=\"phone\")</code> keeps only calls whose receiver is a player.",
                "Then <code>late_player_calls[\"from_number\"].value_counts().idxmax()</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "late_player_calls", "bookie_number")
    if e: return False, e
    lpc = ns["late_player_calls"]
    if "player_name" not in lpc:
        return False, "`late_player_calls` has no player_name column - did you merge with players?"
    if len(lpc) != @@N@@:
        return False, f"`late_player_calls` has {len(lpc)} rows, expected @@N@@. Join late_calls (not all calls) to players on to_number = phone."
    if str(ns["bookie_number"]) != "@@B@@":
        return False, f"{ns['bookie_number']!r} isn't the most frequent caller to players. Use value_counts() on from_number."
    return True, "@@B@@ - the same number the Cyber Cell flagged. That's our bookie."
''', N=N_LATE_PLAYER, B=BOOKIE),
        },
        {
            "title": "Pivot the evidence",
            "task": "Keep only the bookie's calls in <code>bookie_calls</code>. Build <code>pivot</code> with <code>pivot_table</code>: rows = <code>player_name</code>, columns = <code>team</code>, values = total <code>duration_sec</code>. Set <code>mole</code> to the player who spent the most time on the phone with the bookie.",
            "starter": T('''
bookie_calls = late_player_calls[late_player_calls["from_number"] == bookie_number]

pivot = bookie_calls.pivot_table(index=   , columns=   , values=   ,
                                 aggfunc="sum", fill_value=0)
print(pivot)

mole =
'''),
            "solution": T('''
bookie_calls = late_player_calls[late_player_calls["from_number"] == bookie_number]

pivot = bookie_calls.pivot_table(index="player_name", columns="team", values="duration_sec",
                                 aggfunc="sum", fill_value=0)
print(pivot)

mole = pivot.sum(axis=1).idxmax()
'''),
            "hints": [
                "Fill in with column names as text: <code>index=\"player_name\", columns=\"team\", values=\"duration_sec\"</code>.",
                "Total each row with <code>pivot.sum(axis=1)</code>, then <code>.idxmax()</code> gives the player.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "pivot", "mole", "bookie_calls")
    if e: return False, e
    import pandas as pd
    p = ns["pivot"]
    if not isinstance(p, pd.DataFrame) or "@@MOLE@@" not in list(p.index):
        return False, "`pivot` should be a pivot_table with player names as rows (index='player_name')."
    if "@@TEAM@@" not in list(p.columns):
        return False, "Put the team names as the pivot's columns (columns='team')."
    if str(ns["mole"]) != "@@MOLE@@":
        return False, f"{ns['mole']!r} isn't the player with the most talk time. Sum each row and take idxmax()."
    return True, "@@MOLE@@ of the @@TEAM@@ - hours on the phone with a bookie at 2 AM."
''', MOLE=MOLE, TEAM=MOLE_TEAM),
        },
        {
            "title": "Chart the countdown",
            "task": "Count the bookie's calls per day into <code>daily</code> (group by <code>call_time.dt.date</code>), draw it as a <b>bar chart</b>, and set <code>peak_day</code> to the busiest date. Compare it with the final in case5_matches.csv.",
            "starter": T('''
import matplotlib.pyplot as plt

daily = bookie_calls.groupby(bookie_calls["call_time"].dt.date).size()

# draw a bar chart of daily here


peak_day =
print("Busiest night:", peak_day)
pd.read_csv("case5_matches.csv").tail(2)
'''),
            "solution": T('''
import matplotlib.pyplot as plt

daily = bookie_calls.groupby(bookie_calls["call_time"].dt.date).size()

daily.plot(kind="bar", color="#c0392b", title="Bookie calls per night")
plt.ylabel("calls")
plt.tight_layout()

peak_day = daily.idxmax()
print("Busiest night:", peak_day)
pd.read_csv("case5_matches.csv").tail(2)
'''),
            "hints": [
                "<code>daily.plot(kind=\"bar\")</code> draws it. Titles and colours are optional style points.",
                "<code>peak_day = daily.idxmax()</code> - the date with the most calls.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "daily", "peak_day")
    if e: return False, e
    import matplotlib.pyplot as plt
    if not plt.get_fignums() or not plt.gcf().axes:
        return False, "No chart yet! Draw one with daily.plot(kind='bar')."
    if str(ns["peak_day"])[:10] != "@@D@@":
        return False, f"peak_day is {ns['peak_day']!r}. Use daily.idxmax() to get the busiest date."
    return True, "@@D@@ - the night before the @@F@@ final (@@M@@). The ring is exposed."
''', D=PEAK_DAY, F=FINAL.match_id, M=FINAL.start_time[:10]),
        },
    ],
    "closing": [
        f"{MOLE} confesses in the dressing room. ₹15 lakh to drop catches in the final, paid through a bookie on {BOOKIE}.",
        "The bookie talks fast once the handcuffs click. He was just the collector, he says. The money went upstream - to 'the Accountant', who never shows his face.",
        "\"He always pays in round sums,\" the bookie adds. \"Big ones. At night.\"",
        "Big transfers. At night. You finally know where to look: the money itself.",
    ],
})

# ============================================================== CASE 6
CASES.append({
    "id": "heist",
    "num": 6,
    "title": "The Final Heist",
    "location": "Sahyadri Co-operative Bank, Fort · 3:10 AM",
    "concepts": ["cleaning", "numpy", "z-score anomaly detection", "merge + value_counts"],
    "packages": ["pandas", "numpy"],
    "files": ["case6_transactions.csv", "case6_accounts.csv"],
    "icon": "vault",
    "character": {
        "name": "Kaveri Menon", "role": "Fraud analyst, Sahyadri Co-operative Bank",
        "quote": "Nine hundred transfers in a month. One of them is your Accountant. I just can't see him in the crowd.",
        "facts": ["Watches 900+ UPI transfers a month", "Amounts are stored as messy text", "Has coffee. Lots of coffee."],
    },
    "story": [
        "Every case has whispered the same name: the Accountant. Fake trucks, fake reviews, ticket bots, stolen power, fixed matches - all of it paid upstream.",
        "Kaveri Menon gives you thirty days of transfers and the account register. The amounts are written like humans write them: ₹3,943.09, Rs. 41,000.",
        "No tip-off this time. You'll have to let the numbers tell you who doesn't belong.",
    ],
    "briefing": {
        "title": "Putting it together + NumPy anomaly detection",
        "points": [
            "Text money like <code>\"₹3,943.09\"</code> must become numbers: remove symbols with <code>.str.replace(\"₹\", \"\", regex=False)</code>, then <code>.astype(float)</code>.",
            "<b>NumPy</b> does fast maths on whole arrays: <code>arr.mean()</code>, <code>arr.std()</code>, <code>np.abs()</code>.",
            "A <b>z-score</b> says how many standard deviations a value is from the average: <code>z = (x - mean) / std</code>.",
            "Values with <code>|z| &gt; 3</code> are very rare in normal data (about 0.3%) - classic <b>anomalies</b>.",
            "Then use everything you know: filter, merge, value_counts.",
        ],
        "example": T('''
import numpy as np

amounts = np.array([500, 620, 480, 550, 9000, 510])
z = (amounts - amounts.mean()) / amounts.std()
print(np.round(z, 2))
print("Odd one out:", amounts[np.abs(z) > 2])
'''),
    },
    "steps": [
        {
            "title": "Count the real money",
            "task": "Load <b>case6_transactions.csv</b> into <code>tx</code>. The <code>amount</code> column is text like <code>₹3,943.09</code> or <code>Rs. 150</code>. Clean it into a float column (still called <code>amount</code>) and print the total.",
            "starter": T('''
import pandas as pd
import numpy as np

tx = pd.read_csv("case6_transactions.csv")
print(tx["amount"].head())

# remove "₹", "Rs." and "," then convert to float
tx["amount"] = tx["amount"]

print("Total moved: ₹", tx["amount"].sum())
'''),
            "solution": T('''
import pandas as pd
import numpy as np

tx = pd.read_csv("case6_transactions.csv")

tx["amount"] = (tx["amount"]
                .str.replace("₹", "", regex=False)
                .str.replace("Rs.", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
                .astype(float))

print("Total moved: ₹", tx["amount"].sum())
'''),
            "hints": [
                "Chain three <code>.str.replace(old, \"\", regex=False)</code> calls - one each for \"₹\", \"Rs.\" and \",\".",
                "Finish with <code>.str.strip().astype(float)</code> to remove spaces and convert.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "tx")
    if e: return False, e
    import pandas as pd
    a = ns["tx"]["amount"]
    if not pd.api.types.is_numeric_dtype(a):
        return False, "`amount` is still text. After removing ₹, Rs. and commas, use .astype(float)."
    if len(a) != @@N@@:
        return False, f"tx has {len(a)} rows, expected @@N@@. Don't drop rows."
    if abs(float(a.sum()) - @@T@@) > 1:
        return False, f"The total is {a.sum():,.2f}. Some amounts were damaged - remove only the symbols."
    return True, "₹@@TI@@ moved in one month. Somewhere in there is the Accountant."
''', N=len(tx), T=TX_TOTAL, TI=inr(TX_TOTAL)),
        },
        {
            "title": "Find the outliers",
            "task": "Using NumPy, compute the z-score of every amount: <code>z = (amounts - amounts.mean()) / amounts.std()</code>. Keep transactions with <code>|z| &gt; 3</code> in <code>suspicious</code>.",
            "starter": T('''
amounts = tx["amount"].to_numpy()

z =
suspicious = tx[ ]

print(len(suspicious), "suspicious transfers")
suspicious
'''),
            "solution": T('''
amounts = tx["amount"].to_numpy()

z = (amounts - amounts.mean()) / amounts.std()
suspicious = tx[np.abs(z) > 3]

print(len(suspicious), "suspicious transfers")
suspicious
'''),
            "hints": [
                "<code>z = (amounts - amounts.mean()) / amounts.std()</code> - NumPy does it for all 900+ values at once.",
                "Filter with a True/False array: <code>tx[np.abs(z) > 3]</code>.",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "suspicious")
    if e: return False, e
    s = ns["suspicious"]
    if len(s) != @@N@@:
        return False, f"You have {len(s)} rows. Keep rows where np.abs(z) > 3 - the absolute value catches extremes in both directions."
    if s["amount"].min() < 30000:
        return False, "Some of your rows are ordinary amounts. Check the z-score formula."
    return True, "@@N@@ transfers that don't belong. Who received them?"
''', N=N_SUSP),
        },
        {
            "title": "Follow the money",
            "task": "Load <b>case6_accounts.csv</b> as <code>accounts</code>. Merge <code>suspicious</code> with it (<code>to_acct</code> ↔ <code>acct_id</code>) into <code>linked</code>, and set <code>mastermind</code> to the <code>holder_name</code> that received the most suspicious transfers.",
            "starter": T('''
accounts = pd.read_csv("case6_accounts.csv")

linked =

print(linked["holder_name"].value_counts())
mastermind =
'''),
            "solution": T('''
accounts = pd.read_csv("case6_accounts.csv")

linked = suspicious.merge(accounts, left_on="to_acct", right_on="acct_id")

print(linked["holder_name"].value_counts())
mastermind = linked["holder_name"].value_counts().idxmax()
'''),
            "hints": [
                "Same move as the cricket case: <code>suspicious.merge(accounts, left_on=\"to_acct\", right_on=\"acct_id\")</code>.",
                "<code>linked[\"holder_name\"].value_counts().idxmax()</code>",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "linked", "mastermind")
    if e: return False, e
    if "holder_name" not in ns["linked"]:
        return False, "`linked` has no holder_name - merge suspicious with accounts on to_acct = acct_id."
    if str(ns["mastermind"]) != "@@M@@":
        return False, f"{ns['mastermind']!r} received one big payment - could be a car. Who received the MOST?"
    return True, "@@M@@. Three shell accounts, one name. You've heard it before…"
''', M=MASTERMIND),
        },
        {
            "title": "The final number",
            "task": "For the charge sheet: compute <code>heist_total</code>, the total <code>amount</code> the mastermind received in the suspicious transfers.",
            "starter": T('''
heist_total =
print(f"Total laundered: ₹{heist_total:,.0f}")
'''),
            "solution": T('''
heist_total = linked[linked["holder_name"] == mastermind]["amount"].sum()
print(f"Total laundered: ₹{heist_total:,.0f}")
'''),
            "hints": [
                "Filter <code>linked</code> to rows where <code>holder_name == mastermind</code>, then take the <code>amount</code> column.",
                "<code>linked[linked[\"holder_name\"] == mastermind][\"amount\"].sum()</code>",
            ],
            "check": check('''
def check(ns, out):
    e = _need(ns, "heist_total")
    if e: return False, e
    v = _num(ns["heist_total"])
    if v is None:
        return False, "`heist_total` should be one number - finish with .sum()."
    if abs(v - @@H@@) > 1:
        return False, f"₹{v:,.0f} isn't right. Only the mastermind's suspicious transfers, summed."
    return True, "₹@@HI@@. Enough for a warrant."
''', H=HEIST_TOTAL, HI=inr(HEIST_TOTAL)),
        },
    ],
    "closing": [
        "Jamnadas Holdings. Owner: Seth Jamnadas Khatri - the mango trader from your very first case.",
        "The 'missing' truck was an insurance scam. The review farm, the ticket bot, the stolen power for his cold storage, the betting money - all laundered through his shell accounts.",
        f"Dawn at Vashi. Seth Jamnadas is arrested next to a crate of Alphonso, ₹{inr(HEIST_TOTAL)} of heist money frozen.",
        "Chief Inspector Qureshi pins a new badge on your coat. \"Data never lies, Chief. People do.\"",
    ],
})


def main():
    for c in CASES:
        for s in c["steps"]:
            assert len(s["hints"]) == 2, (c["id"], s["title"])
    out = {"version": 1, "cases": CASES}
    (D / "cases.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote data/cases.json with", len(CASES), "cases,", sum(len(c["steps"]) for c in CASES), "steps")
    print("answers:", dict(missing_truck=MISSING_TRUCK, top=TOP_REVIEWER, fakes=len(FAKE_IDS), agent=RACKET_AGENT,
                           pnr=FASTEST_PNR, theft=THEFT_AREA, loss=THEFT_LOSS, bookie=BOOKIE, mole=MOLE,
                           peak=PEAK_DAY, susp=N_SUSP, mastermind=MASTERMIND, heist=HEIST_TOTAL))


if __name__ == "__main__":
    main()
