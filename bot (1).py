"""
Bot de alertas (GitHub Actions, 24/7) -> notificaciones push en el móvil (ntfy)

1) Calendario ForexFactory: solo impacto MEDIO (🟠) y ALTO (🔴).
   - Aviso X minutos antes de cada evento (ALERT_MINUTES).
   - Resumen diario (SUMMARY_HOUR, hora local).
2) Noticias en vivo (FinancialJuice / InvestingLive), filtradas por palabras clave.

Guarda en sent.json lo ya enviado para no duplicar avisos.
"""
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
STATE_FILE = Path(__file__).parent / "sent.json"

NTFY_TOPIC = os.environ["NTFY_TOPIC"]
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
TZ = ZoneInfo(os.environ.get("TZ_NAME") or "UTC")
ALERT_MINUTES = int(os.environ.get("ALERT_MINUTES") or 15)
SUMMARY_HOUR = int(os.environ.get("SUMMARY_HOUR") or 7)
CURRENCIES = {c.strip().upper() for c in (os.environ.get("CURRENCIES") or "").split(",") if c.strip()}

DEFAULT_FEEDS = [
    "https://www.financialjuice.com/feed.ashx?xy=rss",
    "https://investinglive.com/feed/",
    "https://investinglive.com/feed/centralbank",
]
FEEDS = [f.strip() for f in (os.environ.get("FEEDS") or "").split(",") if f.strip()] or DEFAULT_FEEDS

DEFAULT_KEYWORDS = (
    "FED,FOMC,POWELL,ECB,LAGARDE,BOE,BAILEY,BOJ,UEDA,SNB,RBA,RBNZ,BOC,"
    "RATE DECISION,RATE CUT,RATE HIKE,INTEREST RATE,CPI,PCE,INFLATION,NFP,NONFARM,PAYROLLS,"
    "UNEMPLOYMENT,JOBLESS,GDP,PMI,ISM,RETAIL SALES,TARIFF,TARIFFS,SANCTIONS,TRUMP,"
    "INTERVENTION,EMERGENCY,BREAKING,OPEC"
)
KEYWORDS = [k.strip().upper() for k in (os.environ.get("KEYWORDS") or DEFAULT_KEYWORDS).split(",") if k.strip()]
EXCLUDE = [k.strip() for k in (os.environ.get("EXCLUDE") or "FJElite").split(",") if k.strip()]
EX_RE = re.compile("|".join(re.escape(k) for k in EXCLUDE), re.IGNORECASE) if EXCLUDE else None
KW_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in KEYWORDS) + r")\b", re.IGNORECASE)

IMPACTS = {"High": ("🔴", 5), "Medium": ("🟠", 4)}
HEADERS = {"User-Agent": "Mozilla/5.0 (ff-push-alerts/1.1)"}


# ---------------- utilidades ----------------
def load_state():
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    state.setdefault("alerts", {})
    state.setdefault("summaries", [])
    state.setdefault("news", {})
    return state


def save_state(state):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    state["alerts"] = {k: v for k, v in state["alerts"].items() if v > cutoff}
    news_cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    state["news"] = {k: v for k, v in state["news"].items() if v > news_cutoff}
    state["summaries"] = state["summaries"][-10:]
    STATE_FILE.write_text(json.dumps(state, indent=2))


def send(title, message, priority=3, click="https://www.forexfactory.com/calendar"):
    r = requests.post(
        NTFY_SERVER,
        json={"topic": NTFY_TOPIC, "title": title[:250], "message": message,
              "priority": priority, "click": click},
        timeout=20,
    )
    r.raise_for_status()


# ---------------- 1) calendario ----------------
def fetch_events():
    try:
        r = requests.get(CALENDAR_URL, timeout=20, headers=HEADERS)
        if r.status_code == 429:
            print("Calendario: límite de peticiones (429), se reintenta luego.")
            return []
        r.raise_for_status()
    except Exception as ex:
        print(f"Calendario: error {ex}")
        return []
    events = []
    for e in r.json():
        if e.get("impact") not in IMPACTS:
            continue
        if CURRENCIES and e.get("country", "").upper() not in CURRENCIES:
            continue
        e["dt"] = datetime.fromisoformat(e["date"])
        events.append(e)
    return events


def fmt(e):
    emoji = IMPACTS[e["impact"]][0]
    line = f"{emoji} {e['dt'].astimezone(TZ):%H:%M} · {e['country']} · {e['title']}"
    extra = []
    if e.get("forecast"):
        extra.append(f"Prev: {e['forecast']}")
    if e.get("previous"):
        extra.append(f"Anterior: {e['previous']}")
    if extra:
        line += f"\n    {' | '.join(extra)}"
    return line


def run_calendar(state, now):
    events = fetch_events()
    local_now = now.astimezone(TZ)

    today = local_now.date().isoformat()
    if local_now.hour >= SUMMARY_HOUR and today not in state["summaries"]:
        todays = sorted((e for e in events if e["dt"].astimezone(TZ).date() == local_now.date()),
                        key=lambda e: e["dt"])
        title = f"📅 Calendario de hoy {local_now:%d %b}"
        if todays:
            send(title, "\n".join(fmt(e) for e in todays), priority=3)
        else:
            send(title, "Sin eventos rojos ni naranjas hoy.", priority=2)
        state["summaries"].append(today)

    for e in events:
        delta_min = (e["dt"] - now).total_seconds() / 60
        if not (-5 <= delta_min <= ALERT_MINUTES):
            continue
        key = f"{e['date']}|{e['country']}|{e['title']}"
        if key in state["alerts"]:
            continue
        emoji, prio = IMPACTS[e["impact"]]
        when = f"en {round(delta_min)} min" if delta_min > 0 else "ahora"
        send(f"{emoji} {e['country']} {when}: {e['title']}", fmt(e), priority=prio)
        state["alerts"][key] = now.isoformat()


# ---------------- 2) noticias en vivo ----------------
def parse_feed(xml_text):
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "id": (it.findtext("guid") or it.findtext("link") or it.findtext("title") or "").strip(),
            "date": it.findtext("pubDate"),
        })
    atom = "{http://www.w3.org/2005/Atom}"
    for it in root.iter(f"{atom}entry"):
        link_el = it.find(f"{atom}link")
        items.append({
            "title": (it.findtext(f"{atom}title") or "").strip(),
            "link": link_el.get("href", "") if link_el is not None else "",
            "id": (it.findtext(f"{atom}id") or "").strip(),
            "date": it.findtext(f"{atom}updated"),
        })
    return items


def parse_date(s):
    if not s:
        return None
    try:
        return parsedate_to_datetime(s)
    except Exception:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None


def run_news(state, now):
    first_run = not state.get("news_seeded")
    to_send = []
    for url in FEEDS:
        try:
            r = requests.get(url, timeout=20, headers=HEADERS)
            r.raise_for_status()
            items = parse_feed(r.content)
        except Exception as ex:
            print(f"Feed {url}: error {ex}")
            continue
        source = "FinancialJuice" if "financialjuice" in url else "InvestingLive"
        for it in items:
            key = f"{source}|{it['id']}"
            if not it["title"] or key in state["news"]:
                continue
            state["news"][key] = now.isoformat()
            if first_run:
                continue  # primera ejecución: solo memoriza, no envía lo antiguo
            dt = parse_date(it["date"])
            if dt and (now - dt) > timedelta(minutes=45):
                continue
            title = re.sub(r"^FinancialJuice:\s*", "", it["title"])
            if KW_RE.search(title) and not (EX_RE and EX_RE.search(title)):
                to_send.append((source, title, it["link"]))

    for source, title, link in to_send[:10]:
        send(f"📰 {source}", title, priority=4, click=link or "https://www.financialjuice.com")
    state["news_seeded"] = True


RUN_SECONDS = int(os.environ.get("RUN_SECONDS") or 0)          # 0 = una sola pasada
CHECK_SECONDS = int(os.environ.get("CHECK_SECONDS") or 30)
CALENDAR_EVERY = 300  # el feed del calendario limita peticiones: máximo cada 5 min


def main():
    state = load_state()
    start = time.time()
    last_calendar = 0.0
    while True:
        now = datetime.now(timezone.utc)
        try:
            if time.time() - last_calendar >= CALENDAR_EVERY:
                run_calendar(state, now)
                last_calendar = time.time()
            run_news(state, now)
        except Exception as ex:
            print(f"Error: {ex}")
        save_state(state)
        if time.time() - start + CHECK_SECONDS >= RUN_SECONDS:
            break
        time.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    main()
