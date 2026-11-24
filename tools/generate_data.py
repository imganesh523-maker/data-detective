"""Generate the small, realistic (but 100% fictional) evidence files used by Data Detective.

Run:  python tools/generate_data.py
Every dataset uses a fixed random seed, so the files (and the case answers) never change.
All names, phone numbers, PNRs and accounts are invented.
"""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)

FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Reyansh", "Arjun", "Kabir", "Rohan", "Siddharth", "Yash",
         "Ananya", "Diya", "Saanvi", "Meera", "Kavya", "Priya", "Ishita", "Pooja", "Neha", "Riya",
         "Farhan", "Imran", "Zoya", "Sameer", "Joseph", "Maria", "Harpreet", "Gurpreet", "Lakshmi", "Venkat",
         "Suresh", "Ramesh", "Sunita", "Anita", "Deepak", "Manoj", "Rahul", "Sneha", "Tanvi", "Nikhil"]
LAST = ["Sharma", "Patil", "Iyer", "Khan", "Desai", "Nair", "Reddy", "Gupta", "Joshi", "Kulkarni",
        "Mehta", "Shaikh", "Fernandes", "Singh", "Rao", "Pillai", "Bose", "Chatterjee", "Verma", "Yadav"]


def write(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote data/{name}: {len(rows)} rows")


# ---------------------------------------------------------------- Case 1: mango trucks
def case1():
    rng = random.Random(101)
    plates = [f"MH08 {a}{b} {rng.randint(1000, 9999)}" for a, b in
              zip("ABCDEFGHJKLM", "TUVWXYZTUVWX")]
    drivers = ["Bhau Shinde", "Pappu Yadav", "Salim Shaikh", "Tukaram More", "Gurdeep Singh", "Ravi Naik",
               "Dinesh Gawde", "Anwar Ali", "Sandeep Kadam", "Mohan Pawar", "Raju Jadhav", "Kishore Sawant"]
    rows = []
    missing = 7  # index of the truck that never arrives
    for i, (p, d) in enumerate(zip(plates, drivers)):
        arrived = "" if i == missing else {2: 396, 9: 398}.get(i, 400)  # a few crates crushed on the ghats
        arr_time = "" if i == missing else f"0{rng.randint(4, 7)}:{rng.randint(0, 59):02d}"
        rows.append([p, d, "Ratnagiri", 400, arrived, arr_time])
    write("case1_gate_log.csv",
          ["truck_no", "driver", "loaded_at", "crates_loaded", "crates_arrived", "arrival_time"], rows)


# ---------------------------------------------------------------- Case 2: fake reviews
def case2():
    rng = random.Random(202)
    real_texts = [
        ("Good sound quality for the price. Bass could be better.", 4),
        ("Delivery was late by two days but product works fine.", 3),
        ("Battery backup is decent, lasts the whole Pune-Mumbai trip.", 4),
        ("Stopped working after a week. Shop refused to replace it.", 1),
        ("Value for money. Packaging was poor though.", 3),
        ("Charger heats up a lot. Not happy.", 2),
        ("Works as described. Nothing special.", 3),
        ("Excellent build, my father loves it.", 5),
        ("Remote stopped working, had to buy new batteries on day one.", 2),
        ("Picture quality is sharp, cricket matches look great.", 5),
        ("Average product. Customer care did not pick up.", 2),
        ("Fan is silent and the speed control is smooth.", 4),
    ]
    fake_texts = [
        "Best product ever!!! Must buy!!!",
        "BEST PRODUCT EVER. Five stars. Sharma Electronics zindabad!",
        "best product ever, sabse sasta, sabse accha!!",
        "Wow wow wow. Best Product Ever. Buy now!!!",
    ]
    products = ["Boomz Bluetooth Speaker", "TurboCharge Power Bank", "CoolBreeze Table Fan",
                "VisionMax 32in LED TV", "ClickPro Wireless Mouse"]
    real_users = [f"{rng.choice(FIRST).lower()}_{rng.choice(LAST).lower()}{rng.randint(1, 99)}" for _ in range(40)]
    real_users = list(dict.fromkeys(real_users))
    rows = []
    rid = 1001
    start = datetime(2026, 9, 1)
    # 48 genuine reviews
    for _ in range(48):
        text, stars = rng.choice(real_texts)
        rows.append([rid, rng.choice(real_users), rng.choice(products), stars, text,
                     (start + timedelta(days=rng.randint(0, 60))).strftime("%Y-%m-%d")])
        rid += 1
    # one genuine customer honestly happy -- uses the phrase but gives 4 stars (a red herring)
    rows.append([rid, "meera_iyer21", "VisionMax 32in LED TV", 4,
                 "Honestly not the best product ever, but good for the price.", "2026-10-03"]); rid += 1
    # 14 fake reviews from the bot account + 4 from two helper accounts, all 5 stars
    for i in range(14):
        rows.append([rid, "deal_dhamaka_99", rng.choice(products), 5, rng.choice(fake_texts), "2026-10-17"]); rid += 1
    for u in ["sasta_sundar_01", "sasta_sundar_02"]:
        for i in range(2):
            rows.append([rid, u, rng.choice(products), 5, rng.choice(fake_texts), "2026-10-17"]); rid += 1
    rng.shuffle(rows)
    # renumber ids in shuffled order so ids look natural
    for i, r in enumerate(rows):
        r[0] = 1001 + i
    write("case2_reviews.csv", ["review_id", "reviewer", "product", "stars", "text", "date"], rows)


# ---------------------------------------------------------------- Case 3: railway tickets
def case3():
    rng = random.Random(303)
    trains = [("12951", "Mumbai Rajdhani", "MMCT", "NDLS"), ("12137", "Punjab Mail", "CSMT", "FZR"),
              ("11057", "Amritsar Express", "CSMT", "ASR"), ("12809", "Howrah Mail", "CSMT", "HWH"),
              ("12627", "Karnataka Express", "SBC", "NDLS")]
    agents = ["AG-1042", "AG-2217", "AG-3108", "AG-4471", "AG-5520", "AG-6093", "AG-7719"]
    racket = "AG-4471"
    rows = []
    for i in range(240):
        t = rng.choice(trains)
        quota = rng.choices(["General", "Tatkal", "Ladies", "Senior Citizen"], [55, 30, 8, 7])[0]
        agent = rng.choice(agents + ["SELF"] * 6)
        if quota == "Tatkal":
            sec = rng.randint(25, 3500)
        else:
            sec = rng.randint(0, 86000)
        rows.append([t, quota, agent, sec])
    # the racket: 26 Tatkal tickets in the first 20 seconds, by one agent's bot
    for i in range(26):
        rows.append([rng.choice(trains[:2]), "Tatkal", racket, rng.randint(2, 19)])
    # a few honest fast bookers (still slower than the bot on average)
    for i in range(5):
        rows.append([rng.choice(trains), "Tatkal", rng.choice(["SELF", "AG-2217", "AG-6093"]), rng.randint(14, 29)])
    # people on other quotas who happened to book early (not Tatkal -- not suspicious)
    for i in range(4):
        rows.append([rng.choice(trains), rng.choice(["General", "Ladies"]), rng.choice(agents + ["SELF"]), rng.randint(3, 18)])
    # honest Tatkal bookers at exactly 20 seconds (the line is "less than 20")
    for i in range(3):
        rows.append([rng.choice(trains), "Tatkal", rng.choice(["SELF", "AG-1042"]), 20])
    rng.shuffle(rows)
    out = []
    used = set()
    for t, quota, agent, sec in rows:
        while True:
            pnr = str(rng.randint(2_100_000_000, 8_999_999_999))
            if pnr not in used:
                used.add(pnr); break
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        age = rng.randint(60, 85) if quota == "Senior Citizen" else rng.randint(18, 70)
        cls = rng.choice(["SL", "3A", "2A"]) if quota != "Tatkal" else rng.choice(["3A", "2A", "SL"])
        base = {"SL": 650, "3A": 1750, "2A": 2550}[cls]
        fare = base + (400 if quota == "Tatkal" else 0) + rng.randint(-60, 60)
        out.append([pnr, name, age, t[0], t[1], t[2], t[3], "2026-12-05", cls, quota, fare, agent, sec])
    # make sure the single fastest booking is the racket's and unique
    fastest = min(out, key=lambda r: r[-1])
    fastest[-1] = 1
    fastest[11] = racket
    fastest[9] = "Tatkal"
    write("case3_tickets.csv",
          ["pnr", "passenger", "age", "train_no", "train_name", "from_stn", "to_stn", "travel_date",
           "class", "quota", "fare", "agent_id", "seconds_after_open"], out)


# ---------------------------------------------------------------- Case 4: power theft
def case4():
    rng = np.random.default_rng(404)
    areas = ["Gulmohar Nagar", "Shanti Vihar", "Lotus Colony", "Sagar Park", "Indira Chowk"]
    messy = {a: [a, a.upper(), a.lower(), " " + a, a + "  "] for a in areas}
    rows = []
    mid = 50001
    for a in areas:
        n = rng.integers(28, 36)
        for _ in range(n):
            cat = rng.choice(["Domestic", "Domestic", "Domestic", "Commercial"])
            base = 180 if cat == "Domestic" else 900
            for month in ["2026-07", "2026-08", "2026-09"]:
                units = float(round(rng.normal(base, base * 0.25)))
                units = max(units, 20.0)
                if rng.random() < 0.06:
                    units = np.nan  # meter not read
                rows.append([f"MTR{mid}", rng.choice(messy[a]), cat, month,
                             "" if np.isnan(units) else int(units)])
            mid += 1
    write("case4_meter_readings.csv", ["meter_id", "area", "category", "month", "units_billed"], rows)
    # feeder (substation) supply per area for the same 3 months. Normal line loss is ~7-10%;
    # one area is losing far more -- that is the theft.
    billed = {a: 0.0 for a in areas}
    for r in rows:
        if r[4] != "":
            billed[r[1].strip().title()] += r[4]
    factor = {"Gulmohar Nagar": 1.08, "Shanti Vihar": 1.07, "Lotus Colony": 1.52,
              "Sagar Park": 1.10, "Indira Chowk": 1.09}
    write("case4_feeder_supply.csv", ["area", "units_supplied"],
          [[a, int(round(billed[a] * factor[a], -2))] for a in areas])


# ---------------------------------------------------------------- Case 5: cricket betting
def case5():
    rng = random.Random(505)
    teams = ["Dadar Dolphins", "Bandra Blasters", "Thane Tigers", "Vasai Vipers"]
    players = []
    used = set()
    for team in teams:
        for _ in range(5):
            while True:
                name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                if name not in used:
                    used.add(name); break
            phone = f"+91 9{rng.randint(100000000, 999999999)}"
            players.append([phone, name, team])
    mole_idx = 6  # a Bandra Blasters player
    players[mole_idx][1] = "Rocky Malhotra"
    write("case5_players.csv", ["phone", "player_name", "team"], players)

    start = datetime(2026, 8, 1, 19, 30)
    matches = []
    pairs = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2), (0, 1), (2, 3), (1, 3)]
    for i, (a, b) in enumerate(pairs):
        d = start + timedelta(days=3 * i)
        stage = "League" if i < 8 else "Final"
        matches.append([f"MML-{i + 1:02d}", d.strftime("%Y-%m-%d %H:%M"), teams[a], teams[b], stage])
    write("case5_matches.csv", ["match_id", "start_time", "team_a", "team_b", "stage"], matches)

    bookie = "+91 98200 13579"
    others = [f"+91 {rng.choice([70, 81, 88, 99])}{rng.randint(10000000, 99999999)}" for _ in range(25)]
    calls = []
    t0 = datetime(2026, 7, 28)
    # background calls: friends, family, random numbers, any hour (mostly daytime)
    for _ in range(420):
        caller = rng.choice(others)
        receiver = rng.choice([p[0] for p in players] + others)
        t = t0 + timedelta(days=rng.randint(0, 30), hours=rng.choice(range(8, 24)), minutes=rng.randint(0, 59),
                           seconds=rng.randint(0, 59))
        calls.append([caller, receiver, t, rng.randint(15, 600)])
    # some innocent late-night calls (friends) to players
    for _ in range(18):
        t = t0 + timedelta(days=rng.randint(0, 30), hours=rng.choice([0, 1, 2, 3, 4]), minutes=rng.randint(0, 59))
        calls.append([rng.choice(others), rng.choice(players)[0], t, rng.randint(30, 300)])
    # early-morning calls at 5 AM (gym buddies, the milkman...) -- just outside the "before 5" window
    for _ in range(6):
        t = t0 + timedelta(days=rng.randint(0, 30), hours=5, minutes=rng.randint(0, 59))
        calls.append([rng.choice(others), rng.choice(players)[0], t, rng.randint(30, 200)])
    # late-night calls between people who are NOT players (night-shift workers, insomniacs...)
    for _ in range(14):
        t = t0 + timedelta(days=rng.randint(0, 30), hours=rng.choice([0, 1, 2, 3, 4]), minutes=rng.randint(0, 59))
        a, b = rng.sample(others, 2)
        calls.append([a, b, t, rng.randint(30, 400)])
    # bookie: late-night calls to several players, heavy on the mole, peak the night before the final
    final_day = datetime.strptime(matches[-1][1], "%Y-%m-%d %H:%M").date()
    peak_night = datetime.combine(final_day - timedelta(days=1), datetime.min.time())  # date before final
    targets = [players[mole_idx][0]] * 10 + [players[1][0], players[11][0], players[16][0]] * 2
    for _ in range(16):
        tgt = rng.choice(targets)
        day = rng.randint(0, 22)
        t = t0 + timedelta(days=day, hours=rng.choice([0, 1, 2, 3]), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
        calls.append([bookie, tgt, t, rng.randint(60, 900)])
    for k in range(7):
        tgt = players[mole_idx][0] if k < 5 else players[1][0]
        t = peak_night + timedelta(hours=rng.choice([1, 2, 3]), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
        calls.append([bookie, tgt, t, rng.randint(200, 1500)])
    calls.sort(key=lambda c: c[2])
    rows = [[f"C{i + 1:05d}", c[0], c[1], c[2].strftime("%Y-%m-%d %H:%M:%S"), c[3]] for i, c in enumerate(calls)]
    write("case5_calls.csv", ["call_id", "from_number", "to_number", "call_time", "duration_sec"], rows)


# ---------------------------------------------------------------- Case 6: final heist
def case6():
    rng = np.random.default_rng(606)
    prng = random.Random(606)
    holders = []
    accts = []
    for i in range(60):
        acct = f"UPI{70000 + i * 37}"
        name = f"{prng.choice(FIRST)} {prng.choice(LAST)}"
        branch = prng.choice(["Fort", "Andheri", "Vashi", "Thane", "Borivali", "Dadar"])
        opened = (datetime(2015, 1, 1) + timedelta(days=int(rng.integers(0, 3500)))).strftime("%Y-%m-%d")
        accts.append([acct, name, branch, opened])
    shells = ["UPI99001", "UPI99002", "UPI99003"]
    for s in shells:
        accts.append([s, "Jamnadas Holdings", "Vashi", "2026-06-12"])
    # a decoy: a wealthy jeweller with big but *normal* (frequent) payments
    write("case6_accounts.csv", ["acct_id", "holder_name", "branch", "opened_on"], accts)

    normal_ids = [a[0] for a in accts[:60]]
    rows = []
    t0 = datetime(2026, 10, 1)
    for i in range(900):
        amt = float(np.clip(rng.normal(3200, 1400), 150, 9800))
        a, b = prng.sample(normal_ids, 2)
        t = t0 + timedelta(minutes=int(rng.integers(0, 60 * 24 * 30)))
        rows.append([a, b, round(amt, 2), t])
    # the heist: big transfers into the shells
    for i in range(9):
        amt = float(rng.integers(38000, 49500))
        t = t0 + timedelta(days=int(rng.integers(20, 29)), hours=int(rng.integers(1, 4)), minutes=int(rng.integers(0, 59)))
        rows.append([prng.choice(normal_ids), prng.choice(shells), amt, t])
    # one decoy big payment: a car down-payment to a normal account (also an anomaly, different receiver)
    rows.append([normal_ids[3], normal_ids[17], 41000.0, t0 + timedelta(days=5, hours=14)])
    rows.sort(key=lambda r: r[3])

    def rupees(x):
        x = round(x, 2)
        s = f"{x:,.2f}"
        if s.endswith(".00") and prng.random() < 0.5:
            s = s[:-3]
        return "₹" + s if prng.random() < 0.8 else "Rs. " + s

    out = [[f"TXN{i + 1:05d}", r[3].strftime("%Y-%m-%d %H:%M"), r[0], r[1], rupees(r[2]),
            prng.choice(["UPI", "UPI", "UPI", "IMPS", "NEFT"])] for i, r in enumerate(rows)]
    write("case6_transactions.csv", ["txn_id", "timestamp", "from_acct", "to_acct", "amount", "channel"], out)


if __name__ == "__main__":
    case1(); case2(); case3(); case4(); case5(); case6()
