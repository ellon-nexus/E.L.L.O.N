"""Cotações de fecho, sem chave nem Claude: Yahoo Finance (gráfico diário) com reserva no Stooq.
Grava data/quotes.json = {asOf, fx, prices:{T:{p,prev,cur}}, watch:{...}, source}. Só dados públicos."""
import csv, io, json, os, sys, time, urllib.request
from datetime import datetime, timezone

ASSETS = {  # ticker do E.L.L.O.N: (Yahoo, Stooq, moeda)
    "VUAA": ("VUAA.L", "vuaa.uk", "USD"), "O": ("O", "o.us", "USD"), "NEE": ("NEE", "nee.us", "USD"),
    "CMCSA": ("CMCSA", "cmcsa.us", "USD"), "NVDA": ("NVDA", "nvda.us", "USD"), "WTRG": ("WTRG", "wtrg.us", "USD"),
    "SPCX": ("SPCX", "spcx.us", "USD"), "CNQ": ("CNQ", "cnq.us", "USD"),
}
WATCH = {"JPM": ("CMC.DE", "cmc.de", "EUR")}  # JPM vendida a 9/11/2026; fica em observação
CAND = {"VWCE": "VWCE.DE", "SPYD": "SPYD.DE"}  # ETF candidatos às compras do mês (Xetra, EUR); ainda não são posições

def stats(sym):
    """Média dos últimos 200 fechos e máximo de 52 semanas, para a regra de compra do dia 20."""
    import yfinance as yf
    d = yf.Ticker(sym).history(period="1y", interval="1d", auto_adjust=False)
    c = d["Close"].dropna()
    if len(c) < 60:
        return None
    return {"ma200": round(float(c.tail(200).mean()), 4), "h52": round(float(c.max()), 4),
            "p": round(float(c.iloc[-1]), 4), "prev": round(float(c.iloc[-2]), 4)}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read().decode("utf-8", "replace")

def yahoo(sym):
    """Fecho do último dia de bolsa. As barras horárias aparecem logo após o fecho;
    a barra diária do Yahoo às vezes só chega horas depois (dava sempre o dia anterior)."""
    import yfinance as yf  # trata dos cookies do Yahoo e evita o erro 429
    tk = yf.Ticker(sym)
    p = prev = day = None
    try:
        h = tk.history(period="7d", interval="1h", auto_adjust=False)
        h = h[h["Close"].notna()]
        days = sorted({ts.date() for ts in h.index})
        if len(days) >= 2:
            last = h[[ts.date() == days[-1] for ts in h.index]]
            before = h[[ts.date() == days[-2] for ts in h.index]]
            p, prev, day = float(last["Close"].iloc[-1]), float(before["Close"].iloc[-1]), days[-1]
    except Exception:
        pass
    d = tk.history(period="10d", interval="1d", auto_adjust=False)
    d = d[d["Close"].notna()]
    dday = d.index[-1].date()
    if day is None or dday >= day:  # a barra diária já tem o último dia: usa o fecho oficial
        p, prev, day = float(d["Close"].iloc[-1]), float(d["Close"].iloc[-2]), dday
    when = min(datetime(day.year, day.month, day.day, 21, tzinfo=timezone.utc), datetime.now(timezone.utc))
    try:
        cur = tk.fast_info.get("currency")
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
keep = lambda g, tab: {k: v for k, v in (old.get(g) or {}).items() if k in tab}  # só ativos atuais (tira os vendidos)
out = {"prices": keep("prices", ASSETS), "watch": keep("watch", WATCH), "fx": old.get("fx")}
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
# médias de 200 dias e máximos de 52 semanas (ativos e candidatos); falhas não travam o resto
out["cand"] = {}
for group, table in (("prices", {k: v[0] for k, v in ASSETS.items()}), ("cand", CAND)):
    for t, ys in table.items():
        try:
            st = stats(ys)
        except Exception as e:
            st = None; ERRS.append(f"stats {ys}: {str(e)[:80]}")
        if not st:
            continue
        if group == "cand":
            out["cand"][t] = {"p": st["p"], "prev": st["prev"], "cur": "EUR", "ma200": st["ma200"], "h52": st["h52"]}
        elif t in out["prices"]:
            k = 100 if out["prices"][t].get("cur") == "GBP" and st["p"] > 1000 else 1
            out["prices"][t].update({"ma200": round(st["ma200"] / k, 4), "h52": round(st["h52"] / k, 4)})
fx = fetch("EURUSD=X", "eurusd")
if fx and 0.9 < fx[0] < 1.4:
    out["fx"] = fx[0]; used.add(fx[4])
out["asOf"] = (latest or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
out["source"] = ("Fecho via " if datetime.now(timezone.utc).hour >= 21 or datetime.now(timezone.utc).weekday() >= 5 else "Durante a sessão via ") + " e ".join(sorted({"yahoo": "Yahoo Finance", "google": "Google Finance", "stooq": "Stooq"}[u] for u in used)) + (f"; sem dados: {', '.join(failed)}" if failed else "")
out["erros"] = ERRS[:12]
json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
