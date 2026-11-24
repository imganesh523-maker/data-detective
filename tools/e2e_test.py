"""Headless browser test: real Chromium + real Pyodide from the CDN.

Usage:
  python -m http.server 8765  (in the repo root, separately)  -- or pass --url
  python tools/e2e_test.py mango reviews       # test those cases (by id)
  python tools/e2e_test.py --shots             # take README screenshots

For every case it plays like a player: opens the case, runs a WRONG answer (must show a fail),
then types each reference solution into the editor, presses Run, and waits for "Clue found!".
After the last step the "Case Closed" overlay and share card must appear.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = "http://localhost:8765/"
for a in sys.argv:
    if a.startswith("--url="):
        URL = a.split("=", 1)[1]
CASES = json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))["cases"]
PROFILE = "/tmp/dd-pw-profile"


def proxy_opts():
    """Use the machine's HTTPS proxy (if any) so Chromium can reach the Pyodide CDN."""
    import os
    import urllib.parse
    v = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not v:
        return {}
    u = urllib.parse.urlparse(v)
    proxy = {"server": f"{u.scheme}://{u.hostname}:{u.port}", "bypass": "localhost,127.0.0.1"}
    if u.username:
        proxy.update(username=urllib.parse.unquote(u.username), password=urllib.parse.unquote(u.password or ""))
    return {"proxy": proxy, "ignore_https_errors": True}
errors = []
results = []


def log(ok, msg):
    results.append((ok, msg))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def wait_feedback(page, timeout=90000):
    page.wait_for_function("() => document.querySelector('#feedback .feedback') && !document.querySelector('#btnRun').disabled",
                           timeout=timeout)
    el = page.query_selector("#feedback .feedback")
    return "pass" in el.get_attribute("class"), el.inner_text()


def run_code(page, code, timeout=90000):
    page.evaluate("() => { const f = document.querySelector('#feedback'); if (f) f.innerHTML = ''; }")
    page.evaluate("(c) => window.DD.setCode(c)", code)
    page.click("#btnRun")
    return wait_feedback(page, timeout)


def play(page, case):
    t0 = time.time()
    page.evaluate("(id) => { document.querySelectorAll('.overlay').forEach(o => o.hidden = true); window.DD.openCase(id, 'steps'); }", case["id"])
    # wrong answer first: the untouched starter (or a NameError) must not pass
    ok, text = run_code(page, "print(answer_that_does_not_exist)")
    err = page.inner_text("#consoleBody")
    log(not ok and "doesn't know anything called" in err, f"[{case['id']}] wrong code rejected with plain-English NameError tip")
    for i, step in enumerate(case["steps"]):
        page.evaluate("(i) => { const b = document.querySelector(`.stepdot[data-step='${i}']`); b && b.click(); }", i)
        if i == 0 or True:
            pass
        ok, text = run_code(page, step["solution"])
        log(ok, f"[{case['id']}] step {i + 1} '{step['title']}' passes in the browser: {text.splitlines()[1] if len(text.splitlines()) > 1 else text}")
        if i < len(case["steps"]) - 1:
            page.evaluate("() => { document.querySelectorAll('.overlay').forEach(o => o.hidden = true); }")
    page.wait_for_selector("#closed:not([hidden])", timeout=8000)
    log(True, f"[{case['id']}] Case Closed overlay shown ({time.time() - t0:.1f}s)")
    size = page.evaluate("() => { const c = document.querySelector('#shareCanvas'); return [c.width, c.height, c.toDataURL('image/png').length]; }")
    log(size[0] == 1200 and size[1] == 627 and size[2] > 50000, f"[{case['id']}] share card canvas {size[0]}x{size[1]}, PNG {size[2] // 1024} KB")
    if case["id"] == "cricket":
        n = page.evaluate("() => document.querySelectorAll('#consoleBody img.fig').length")
        log(n >= 1, f"[cricket] matplotlib chart rendered in console ({n} image)")


def main():
    ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    shots = "--shots" in sys.argv
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, headless=True, **proxy_opts(), viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_selector("html[data-ready='1']", timeout=30000)
        page.evaluate("() => localStorage.clear()")
        page.reload(); page.wait_for_selector("html[data-ready='1']", timeout=30000)
        page.evaluate("() => { window.DD.state.data.unlockAll = true; window.DD.state.save(); }")
        for cid in ids:
            play(page, next(c for c in CASES if c["id"] == cid))
        if "--misc" in sys.argv:
            misc(page)
        if shots:
            take_shots(p, ctx, page)
        ctx.close()
    bad = [m for ok, m in results if not ok]
    real_errors = [e for e in errors if "favicon" not in e]
    print(f"\n{len(results) - len(bad)} passed, {len(bad)} failed; console errors: {real_errors[:5]}")
    sys.exit(1 if bad or real_errors else 0)


def misc(page):
    """Wrong logic answer, briefing example, infinite-loop recovery, progress saved across reload."""
    page.evaluate("() => { document.querySelectorAll('.overlay').forEach(o => o.hidden = true); window.DD.openCase('railway', 'steps'); }")
    page.evaluate("() => document.querySelector(`.stepdot[data-step='1']`).click()")
    ok, text = run_code(page, "suspects = df[df['seconds_after_open'] < 20]")
    log(not ok and "Tatkal" in text, "wrong logic (forgot the quota filter) is rejected with a specific tip: " + text.splitlines()[-1][:90])
    ok, text = run_code(page, "suspects = df[df['quota'] == 'Tatkal' & df['seconds_after_open'] < 20]")
    con = page.inner_text("#consoleBody")
    log(not ok and ("TypeError" in con or "ValueError" in con), "missing brackets around conditions -> error explained in plain English")
    # briefing example
    page.evaluate("() => window.DD.selectTab('brief')")
    page.click("#btnExample")
    page.wait_for_function("() => { const o = document.querySelector('#exampleOut'); return o && !o.hidden && o.querySelector('table, pre.out'); }", timeout=60000)
    log(True, "briefing example runs and shows output")
    # infinite loop -> lab restarts after 20 s, then works again
    page.evaluate("() => window.DD.selectTab('steps')")
    page.evaluate("() => window.DD.setCode('while True:\\n    pass')")
    t0 = time.time()
    page.click("#btnRun")
    page.wait_for_function("() => document.querySelector('#consoleBody').innerText.includes('ran for over 20 seconds')", timeout=60000)
    log(True, f"infinite loop stopped and explained after {time.time() - t0:.0f}s")
    ok, text = run_code(page, "suspects = df[(df['quota'] == 'Tatkal') & (df['seconds_after_open'] < 20)]")
    log(ok, "lab rebooted and the next run passes")
    # progress survives reload
    page.reload(); page.wait_for_selector("html[data-ready='1']")
    n = page.evaluate("() => Object.keys(window.DD.state.data.solved).length")
    log(n >= 1, f"progress saved in localStorage across reload ({n} cases solved)")


def take_shots(p, ctx, page):
    out = ROOT / "screenshots"
    out.mkdir(exist_ok=True)
    page.evaluate("() => { localStorage.clear(); }")
    # progress: first 4 cases closed, case 5 at its chart step
    prog = {"solved": {"mango": True, "reviews": True, "railway": True, "power": True},
            "steps": {"mango": 3, "reviews": 3, "railway": 4, "power": 4, "cricket": 3},
            "hints": {"railway:1": 1}, "code": {}, "passed": {}, "seenStory": {c["id"]: True for c in CASES}, "unlockAll": False}
    page.evaluate("(p) => localStorage.setItem('data-detective-progress-v1', JSON.stringify(p))", prog)
    page.goto(URL); page.wait_for_selector("html[data-ready='1']")
    time.sleep(3.5)
    page.screenshot(path=str(out / "title-desktop.png"))
    page.goto(URL + "#board"); page.reload(); page.wait_for_selector("html[data-ready='1']"); time.sleep(2.5)
    page.screenshot(path=str(out / "board-desktop.png"))
    # case 5, chart step, solved run
    page.evaluate("() => window.DD.openCase('cricket', 'steps')")
    sol = next(c for c in CASES if c["id"] == "cricket")["steps"][3]["solution"]
    run_code(page, sol)
    time.sleep(1.5)
    page.evaluate("() => { document.querySelectorAll('.overlay').forEach(o => o.hidden = true); const cb = document.querySelector('#consoleBody'); const img = cb.querySelector('img.fig'); if (img) img.scrollIntoView(); }")
    time.sleep(0.5)
    page.screenshot(path=str(out / "case-chart-desktop.png"))
    page.evaluate("() => window.DD.showClosed('cricket')")
    time.sleep(2.5)
    page.screenshot(path=str(out / "case-closed-desktop.png"))
    # mobile
    m = p.chromium.launch()
    mctx = m.new_context(**proxy_opts(), viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    mp = mctx.new_page()
    mp.goto(URL); mp.wait_for_selector("html[data-ready='1']")
    mp.evaluate("(p) => localStorage.setItem('data-detective-progress-v1', JSON.stringify(p))", prog)
    mp.goto(URL + "#case=railway"); mp.reload(); mp.wait_for_selector("html[data-ready='1']"); time.sleep(2)
    mp.evaluate("() => window.DD.selectTab('steps')")
    time.sleep(1)
    mp.screenshot(path=str(out / "case-mobile.png"))
    mp.goto(URL + "#board"); mp.reload(); mp.wait_for_selector("html[data-ready='1']"); time.sleep(2)
    mp.screenshot(path=str(out / "board-mobile.png"))
    m.close()
    print("screenshots saved to", out)


if __name__ == "__main__":
    main()
