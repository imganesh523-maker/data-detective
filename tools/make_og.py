"""Renders assets/og-image.png (1200x627) with the same canvas code the game uses for share cards.
Run with the site served on localhost:8765:  python tools/make_og.py
"""
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_test import URL, proxy_opts

ROOT = Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_context(**proxy_opts()).new_page()
    page.goto(URL)
    page.wait_for_selector("html[data-ready='1']")
    page.evaluate("""async () => { await window.DD.drawCard({ mode: 'og', title: 'Crack crimes with real Python',
        caseNum: 0, rank: 'Rookie', concepts: ['print', 'loops', 'pandas', 'groupby', 'merge', 'numpy'] }); }""")
    data = page.evaluate("() => document.querySelector('#shareCanvas').toDataURL('image/png')")
    out = ROOT / "assets" / "og-image.png"
    out.write_bytes(base64.b64decode(data.split(",", 1)[1]))
    print("wrote", out, out.stat().st_size // 1024, "KB")
    b.close()
