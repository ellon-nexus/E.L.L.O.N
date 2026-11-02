"""Cotações de fecho, sem chave nem Claude: Yahoo Finance (gráfico diário) com reserva no Stooq.
Grava data/quotes.json = {asOf, fx, prices:{T:{p,prev,cur}}, watch:{...}, source}. Só dados públicos."""
import csv, io, json, os, sys, time, urllib.request
from datetime import datetime, timezone

ASSETS = {  # ticker do E.L.L.O.N: (Yahoo, Stooq, moeda)
    "VUAA": ("VUAA.L", "vuaa.uk", "USD"), "O": ("O", "o.us", "USD"), "NEE": ("NEE", "nee.us", "USD"),
    "CMCSA": ("CMCSA", "cmcsa.us", "USD"), "NVDA": ("NVDA", "nvda.us", "USD"), "WTRG": ("WTRG", "wtrg.us", "USD"),
    "SPCX": ("SPCX", "spcx.us", "USD"), "JPM": ("CMC.DE", "cmc.de", "EUR"),
}
WATCH = {"CNQ": ("CNQ", "cnq.us", "USD")}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read().decode("utf-8", "replace")

def yahoo(sym):
    import yfinance as yf  # trata dos cookies do Yahoo e evita o erro 429
    h = yf.Ticker(sym).history(period="10d", interval="1d", auto_adjust=False)
    h = h[h["Close"].notna()]
    p, prev = float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
    when = min(h.index[-1].to_pydatetime().astimezone(timezone.utc).replace(hour=21), datetime.now(timezone.utc))
    try:
        cur = yf.Ticker(sym).fast_info.get("currency")
    except Exception:
        cur = None
    return round(p, 4), round(prev, 4), when, cur

def stooq(sym):
    rows = list(csv.DictReader(io.StringIO(get(f"https://stooq.com/q/d/l/?s={sym}&i=d"))))
    rows = [r for r in rows if r.get("Close") not in (None, "", "N/D")]
    a, b = rows[-1], rows[-2]
    when = datetime.strptime(a["Date"], "%Y-%m-%d").replace(hour=21, tzinfo=timezone.utc)
    return round(float(a["Close"]), 4), round(float(b["Close"]), 4), when, None

GOOGLE = {"VUAA.L": "VUAA:LON", "O": "O:NYSE", "NEE": "NEE:NYSE", "CMCSA": "CMCSA:NASDAQ", "NVDA": "NVDA:NASDAQ",
          "WTRG": "WTRG:NYSE", "NNE": "NNE:NASDAQ", "SPCX": "SPCX:NASDAQ", "BCP.LS": "BCP:ELI", "CNQ": "CNQ:NYSE", "EURUSD=X": "EUR-USD"}

def google(ys):
    import re
    h = get("https://www.google.com/finance/quote/" + GOOGLE[ys] + "?hl=en")
    p = float(re.search(r'data-last-price="([\d.]+)"', h).group(1))
    m = re.search(r'Previous close</div>.*?>([\d,.]+)\s*<', h, re.S) or re.search(r'Previous close.{0,400}?([\d,]+\.\d+)', h, re.S)
    prev = float(m.group(1).replace(",", "")) if m else p
    return round(p, 4), round(prev, 4), datetime.now(timezone.utc), None

ERRS = []
def fetch(ys, ss):
    for fn, s in ((yahoo, ys), (google, ys), (stooq, ss)):
        try:
            return fn(s) + (fn.__name__,)
        except Exception as e:
            ERRS.append(f"{fn.__name__} {s}: {str(e)[:120]}")
        time.sleep(1)
    return None

path = "data/quotes.json"
old = json.load(open(path)) if os.path.exists(path) else {"prices": {}, "watch": {}}
out = {"prices": dict(old.get("prices", {})), "watch": dict(old.get("watch", {})), "fx": old.get("fx")}
latest, used, failed = None, set(), []
for group, table in (("prices", ASSETS), ("watch", WATCH)):
    for t, (ys, ss, cur) in table.items():
        r = fetch(ys, ss)
        if not r:
            failed.append(t); continue
        p, prev, when, ycur = r[0], r[1], r[2], r[3]
        oldp = (old.get(group, {}).get(t) or {}).get("p")
        if oldp and abs(p / oldp - 1) > 0.35:  # salto absurdo: mantém o que estava
            failed.append(t); continue
        if ycur == "GBp":  # cotado em pence
            p, prev, cur = p / 100, prev / 100, "GBP"
        out[group][t] = {"p": p, "prev": prev, "cur": cur}
        used.add(r[4]); latest = max(latest or when, when)
fx = fetch("EURUSD=X", "eurusd")
if fx and 0.9 < fx[0] < 1.4:
    out["fx"] = fx[0]; used.add(fx[4])
out["asOf"] = (latest or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
out["source"] = "Fecho diário via " + " e ".join(sorted({"yahoo": "Yahoo Finance", "google": "Google Finance", "stooq": "Stooq"}[u] for u in used)) + (f"; sem dados: {', '.join(failed)}" if failed else "")
out["erros"] = ERRS[:12]
json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
