"""Lista de vigia para a regra do dia 20: uma vez por dia, só dados públicos (Yahoo Finance via yfinance).
Grava data/vigia.json = {asOf, itens: {T: {n, y, p, cur, ma200, h52, div, rec, nrec, pe, cresc, motivos: [...]}}, falhas: [...]}.
Uma empresa nova só é sugerida com vários motivos bons (ver MOTIVOS); a página decide quantos bastam."""
import json, time
from datetime import datetime, timezone

# ticker como o André o escreve -> símbolo do Yahoo
Y = {
 "STX": "STX", "MU": "MU", "CAT": "CAT", "SNDK": "SNDK", "META": "META", "SPOT": "SPOT", "TSM": "TSM", "SAAB-B": "SAAB-B.ST",
 "WDC": "WDC", "UNH": "UNH", "OR": "OR.PA", "AAPL": "AAPL", "TSLA": "TSLA", "AMD": "AMD", "DPZ": "DPZ", "ISRG": "ISRG",
 "NOVO-B": "NOVO-B.CO", "MA": "MA", "GOOGL": "GOOGL", "V": "V", "UNP": "UNP", "SIE": "SIE.DE", "ABBV": "ABBV", "DELL": "DELL",
 "JNJ": "JNJ", "BA": "BA", "TTWO": "TTWO", "IBM": "IBM", "EA": "EA", "ASML": "ASML", "SNOW": "SNOW", "QCOM": "QCOM", "PG": "PG",
 "CRM": "CRM", "PEP": "PEP", "ORCL": "ORCL", "ABNB": "ABNB", "PLTR": "PLTR", "ANET": "ANET", "MRVL": "MRVL", "NOVN": "NOVN.SW",
 "GLW": "GLW", "2317": "2317.TW", "KO": "KO", "VOW3": "VOW3.DE", "INTC": "INTC", "NFLX": "NFLX", "ZTS": "ZTS", "UBER": "UBER",
 "TRP": "TRP", "FTS": "FTS", "PNR": "PNR", "ARM": "ARM", "ENB": "ENB", "BMY": "BMY", "TCEHY": "TCEHY", "LMND": "LMND",
 "RYAAY": "RYAAY", "RIO": "RIO", "STM": "STM", "VZ": "VZ", "GWO": "GWO.TO", "MO": "MO", "NKE": "NKE", "EZJ": "EZJ.L",
 "PLBC": "PLBC", "APA": "APA", "WISE": "WISE.L", "KMI": "KMI", "SIRI": "SIRI", "PFE": "PFE", "GSL": "GSL", "MBG": "MBG.DE",
 "CAPCOM": "9697.T", "SONY": "SONY", "SOFI": "SOFI", "GALP": "GALP.LS", "VALE": "VALE", "EDPR": "EDPR.LS", "VG": "VG",
 "PBR": "PBR", "LUNR": "LUNR", "RIOT": "RIOT", "MSTR": "MSTR", "NINTENDO": "7974.T", "MARA": "MARA", "PSKY": "PSKY",
 "RDW": "RDW", "PROX": "PROX.BR", "NOS": "NOS.LS", "FULC": "FULC", "EDP": "EDP.LS", "BCP": "BCP.LS", "VICI": "VICI",
 "CBG": "CBG.L", "RR": "RR.L", "F": "F", "RDDT": "RDDT", "SHEL": "SHEL", "IBS": "IBS.LS", "WEGE3": "WEGE3.SA", "RNG": "RNG",
 # empresas com 10+ anos de dividendos sem falhar, das conversas de 13/11/2026
 "CL": "CL", "GIS": "GIS", "HRL": "HRL", "MCD": "MCD", "PM": "PM", "MRK": "MRK", "LLY": "LLY", "ELV": "ELV", "BAYN": "BAYN.DE",
 "SO": "SO", "ETR": "ETR", "AWK": "AWK", "IBE": "IBE.MC", "ADC": "ADC", "MSFT": "MSFT", "AVGO": "AVGO", "AMAT": "AMAT",
 "LRCX": "LRCX", "SAP": "SAP.DE", "TENCENT": "0700.HK", "HYNIX": "000660.KS", "ENI": "ENI.MI", "PSX": "PSX", "UPS": "UPS",
 "NOC": "NOC", "TOYOTA": "7203.T", "FCNCA": "FCNCA", "JMT": "JMT.LS", "VOD": "VOD.L", "JPM": "JPM",
}
CARTEIRA = {"O", "NEE", "CMCSA", "NVDA", "WTRG", "SPCX", "CNQ", "VUAA"}  # já são posições: tratadas pelas cotações

def anos_div(divs):
    """Anos civis seguidos com dividendos, a contar para trás do último ano completo."""
    anos = {d.year for d in divs.index}
    y, n = datetime.now(timezone.utc).year - 1, 0
    while y in anos:
        n += 1; y -= 1
    return n

def um(sym):
    import yfinance as yf
    tk = yf.Ticker(sym)
    h = tk.history(period="1y", interval="1d", auto_adjust=False)
    c = h["Close"].dropna()
    if len(c) < 60:
        raise ValueError("sem histórico")
    divs = tk.dividends
    info = {}
    try:
        info = tk.info or {}
    except Exception:
        pass
    p = float(c.iloc[-1])
    r = {"y": sym, "p": round(p, 4), "cur": info.get("currency"), "ma200": round(float(c.tail(200).mean()), 4), "h52": round(float(c.max()), 4),
         "div": anos_div(divs) if len(divs) else 0, "n": info.get("shortName") or info.get("longName") or sym,
         "rec": info.get("recommendationMean"), "nrec": info.get("numberOfAnalystOpinions"),
         "pe": info.get("forwardPE") or info.get("trailingPE"), "cresc": info.get("earningsGrowth")}
    if r["cur"] == "GBp":
        for k in ("p", "ma200", "h52"):
            r[k] = round(r[k] / 100, 4)
        r["cur"] = "GBP"
    m = []
    if r["div"] >= 10: m.append(f"dividendos há {r['div']} anos seguidos")
    if r["p"] < r["ma200"] * 0.97: m.append(f"{(1 - r['p'] / r['ma200']) * 100:.0f}% abaixo da média de 200 dias")
    if r["p"] <= r["h52"] * 0.80: m.append(f"{(1 - r['p'] / r['h52']) * 100:.0f}% abaixo do máximo de 52 semanas")
    if r["rec"] and r["rec"] <= 2.0 and (r["nrec"] or 0) >= 5: m.append(f"analistas a favor ({r['nrec']} opiniões)")
    if r["pe"] and 0 < r["pe"] <= 20: m.append(f"P/L de {r['pe']:.0f}")
    if r["cresc"] and r["cresc"] > 0.05: m.append(f"lucros a crescer {r['cresc'] * 100:.0f}%")
    r["motivos"] = m
    return r

out, falhas = {}, []
for t, sym in Y.items():
    if t in CARTEIRA:
        continue
    try:
        out[t] = um(sym)
    except Exception as e:
        falhas.append(f"{t} ({sym}): {str(e)[:60]}")
    time.sleep(0.4)
doc = {"asOf": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "itens": out, "falhas": falhas}
json.dump(doc, open("data/vigia.json", "w"), ensure_ascii=False, indent=1, sort_keys=True)
print(len(out), "ativos;", len(falhas), "falhas:", falhas)
