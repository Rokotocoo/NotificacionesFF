"""
Lector de ForexFactory /news en tu Mac -> notificaciones push (ntfy)
Envía solo las noticias marcadas con impacto ROJO (alto) o NARANJA (medio).

Abre la página con un navegador real (Playwright), la recarga cada CHECK_SECONDS
y avisa de las noticias nuevas. La primera vez solo memoriza las existentes.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

NTFY_TOPIC = os.environ.get("NTFY_TOPIC") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not NTFY_TOPIC:
    sys.exit("Falta NTFY_TOPIC")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
CHECK_SECONDS = int(os.environ.get("CHECK_SECONDS") or 60)
URL = "https://www.forexfactory.com/news"

HOME = Path.home() / ".ff-alerts"
HOME.mkdir(exist_ok=True)
STATE_FILE = HOME / "seen.json"
PROFILE_DIR = HOME / "browser-profile"

LEVELS = {"High": ("🔴", 5), "Medium": ("🟠", 4)}

# Busca los iconos de impacto y sube por el DOM hasta encontrar el enlace de la noticia
EXTRACT_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const nodes = document.querySelectorAll('[class*="impact"], [title*="Impact"], [title*="impact"]');
  nodes.forEach(el => {
    const txt = ((el.className && el.className.toString()) + ' ' + (el.getAttribute('title') || '')).toLowerCase();
    let level = null;
    if (/impact[-_]*red|impact--high|high impact|impact-high/.test(txt)) level = 'High';
    else if (/impact[-_]*ora|impact--orange|impact--medium|medium impact|impact-medium/.test(txt)) level = 'Medium';
    if (!level) return;
    let node = el;
    for (let i = 0; i < 10 && node; i++) {
      const links = node.querySelectorAll ? node.querySelectorAll('a[href*="/news/"]') : [];
      for (const a of links) {
        const t = (a.textContent || '').trim();
        if (t.length > 15 && !seen.has(a.href)) {
          seen.add(a.href);
          out.push({level, title: t.replace(/\s+/g, ' '), href: a.href});
          return;
        }
      }
      if (links.length) return;
      node = node.parentElement;
    }
  });
  return out;
}
"""


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen": [], "seeded": False, "warned": False}


def save_state(state):
    state["seen"] = state["seen"][-1000:]
    STATE_FILE.write_text(json.dumps(state))


def send(title, message, priority=3, click=URL):
    try:
        requests.post(NTFY_SERVER, json={"topic": NTFY_TOPIC, "title": title[:250],
                      "message": message, "priority": priority, "click": click}, timeout=20)
    except Exception as ex:
        log(f"ntfy error: {ex}")


def launch(p, headless):
    kwargs = dict(user_data_dir=str(PROFILE_DIR), headless=headless,
                  viewport={"width": 1280, "height": 900},
                  args=["--disable-blink-features=AutomationControlled"])
    try:
        return p.chromium.launch_persistent_context(channel="chrome", **kwargs)
    except Exception:
        return p.chromium.launch_persistent_context(**kwargs)


def blocked(page):
    title = (page.title() or "").lower()
    return "just a moment" in title or "attention required" in title


def main():
    state = load_state()
    headless = os.environ.get("HEADLESS", "1") != "0"
    with sync_playwright() as p:
        ctx = launch(p, headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        empty_streak = 0
        while True:
            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                for _ in range(15):
                    if not blocked(page):
                        break
                    page.wait_for_timeout(2000)
                if blocked(page) and headless:
                    log("Bloqueado en modo oculto, reabriendo con ventana visible…")
                    ctx.close()
                    headless = False
                    ctx = launch(p, headless)
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                    continue
                page.wait_for_timeout(3000)
                items = page.evaluate(EXTRACT_JS)

                if not items:
                    empty_streak += 1
                    if empty_streak == 5:
                        (HOME / "debug.html").write_text(page.content())
                        page.screenshot(path=str(HOME / "debug.png"), full_page=True)
                        log("No encuentro noticias. Guardado ~/.ff-alerts/debug.html")
                        if not state["warned"]:
                            send("⚠️ FF News local", "No encuentro noticias en ForexFactory /news. "
                                 "Revisa ~/.ff-alerts/debug.png", priority=3)
                            state["warned"] = True
                            save_state(state)
                else:
                    empty_streak = 0
                    seen = set(state["seen"])
                    new = [it for it in items if it["href"] not in seen]
                    if state["seeded"]:
                        for it in reversed(new):
                            emoji, prio = LEVELS[it["level"]]
                            send(f"{emoji} FF News", it["title"], priority=prio, click=it["href"])
                            log(f"Enviada: {it['level']} {it['title']}")
                    else:
                        log(f"Primera ejecución: memorizadas {len(items)} noticias")
                        state["seeded"] = True
                    state["seen"].extend(it["href"] for it in new)
                    state["warned"] = False
                    save_state(state)
            except Exception as ex:
                log(f"Error: {ex}")
            time.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    main()
