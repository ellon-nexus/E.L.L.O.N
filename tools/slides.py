"""Slides diários da Conjuntura Diária (Instagram, 1080x1350), feitos sem Claude.
Lê a edição mais recente de data/edicoes.json; se tiver "slides" usa-os, senão monta-os a partir do resumo e dos temas.
Fotografias: Pixabay (chave no segredo PIXABAY_KEY) e, em reserva, Openverse só com licenças CC0/domínio público.
Grava slides/AAAA-MM-DD/NN.png, slides/AAAA-MM-DD/creditos.json e slides/index.json."""
import io, json, os, re, sys, textwrap, urllib.parse, urllib.request
from datetime import datetime
from PIL import Image, ImageDraw, ImageFilter, ImageFont

VERSION = 6
W, H = 1080, 1350
DARK, MID, LIGHT = (38, 12, 69), (116, 36, 208), (226, 210, 248)
LOGO = "logo-roxo.png"
# uma cor por dia útil, a rodar (a grelha do Instagram fica variada): começa no roxo a 30/10/2026
import colorsys
PALETAS = [("roxo", 268, .70), ("laranja", 28, .92), ("azul", 222, .85), ("verde", 152, .75), ("vermelho", 352, .80)]


def rgb(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h / 360, l, s)
    return (int(r * 255), int(g * 255), int(b * 255))


def paleta(day):
    from datetime import date, timedelta
    d0, d = date(2026, 10, 30), datetime.strptime(day, "%Y-%m-%d").date()
    n, step = 0, timedelta(days=1)
    a, b = (d0, d) if d >= d0 else (d, d0)
    while a < b:
        a += step
        if a.weekday() < 5:
            n += 1
    if d < d0:
        n = -n
    nome, h, s = PALETAS[n % len(PALETAS)]
    return nome, rgb(h, .16, s), rgb(h, .46, s), rgb(h, .90, s * .7)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, "assets", "fonts")
UA = {"User-Agent": "ConjunturaDiaria/1.0 (+https://ellon-nexus.github.io/E.L.L.O.N/)"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def serif(size, weight="Bold"):
    f = ImageFont.truetype(os.path.join(F, "Lora-Variable.ttf"), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def sans(size, bold=False):
    return ImageFont.truetype(os.path.join(F, "Carlito-Bold.ttf" if bold else "Carlito-Regular.ttf"), size)


def get(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def photo(query, used):
    """Devolve (Image, crédito) ou (None, None)."""
    key = os.environ.get("PIXABAY_KEY", "").strip()
    if key and query:
        for lang in ("en", "pt"):
            try:
                q = urllib.parse.urlencode({"key": key, "q": query[:90], "image_type": "photo", "orientation": "vertical", "safesearch": "true", "per_page": 20, "lang": lang, "order": "popular"})
                hits = json.loads(get("https://pixabay.com/api/?" + q)).get("hits", [])
                if not hits:
                    q = q.replace("orientation=vertical", "orientation=all")
                    hits = json.loads(get("https://pixabay.com/api/?" + q)).get("hits", [])
                for h in hits:
                    if h["id"] in used:
                        continue
                    used.add(h["id"])
                    img = Image.open(io.BytesIO(get(h.get("largeImageURL") or h["webformatURL"], True))).convert("RGB")
                    return img, "Foto: Pixabay"
            except Exception as e:
                print("pixabay falhou:", query, e, file=sys.stderr)
    if query:
        try:
            q = urllib.parse.urlencode({"q": query[:90], "license": "cc0,pdm", "page_size": 20, "mature": "false"})
            res = json.loads(get("https://api.openverse.org/v1/images/?" + q)).get("results", [])
            for r in res:
                if r["id"] in used or (r.get("width") or 0) < 900:
                    continue
                used.add(r["id"])
                img = Image.open(io.BytesIO(get(r["url"], True))).convert("RGB")
                return img, "Foto: domínio público (Openverse)"
        except Exception as e:
            print("openverse falhou:", query, e, file=sys.stderr)
    return None, None


def cover_crop(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s) + 1, int(img.height * s) + 1), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 3
    return img.crop((x, y, x + w, y + h))


def background(img):
    if img is None:  # fundo próprio: gradiente roxo com relevo
        bg = Image.new("RGB", (W, H), DARK)
        d = ImageDraw.Draw(bg)
        for i in range(0, 1400, 6):
            t = i / 1400
            d.line([(0, i), (W, i)], fill=tuple(int(DARK[k] + (MID[k] - DARK[k]) * (1 - t) * 0.55) for k in range(3)))
        for r in range(80, 1500, 70):
            d.ellipse((W // 2 - r, 380 - r, W // 2 + r, 380 + r), outline=tuple(int((DARK[k] + MID[k]) / 2) for k in range(3)), width=2)
        return bg
    bg = cover_crop(img, W, H)
    # tom roxo: mistura leve com a cor da marca
    tint = Image.new("RGB", (W, H), MID)
    bg = Image.blend(bg, tint, 0.18)
    return bg


def overlay(bg, start=0.30):
    """Escurece a parte de baixo para o texto ler-se bem."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    y0 = int(H * start)
    for y in range(y0, H):
        t = (y - y0) / (H - y0)
        d.line([(0, y), (W, y)], fill=DARK + (int(255 * min(1, (t ** 0.8) * 1.12)),))
    for y in range(0, 230):
        d.line([(0, y), (W, y)], fill=DARK + (int(150 * (1 - y / 230)),))
    out = bg.convert("RGBA")
    out.alpha_composite(ov)
    return out


def wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def header(im, date_txt):
    d = ImageDraw.Draw(im)
    logo = Image.open(os.path.join(ROOT, "assets", LOGO)).convert("RGBA").resize((118, 118), Image.LANCZOS)
    im.alpha_composite(logo, (60, 54))
    d.text((196, 72), "CONJUNTURA DIÁRIA", font=sans(40, True), fill=(255, 255, 255))
    d.text((198, 122), date_txt, font=sans(30), fill=LIGHT)


def footer(im, n, total, credit):
    d = ImageDraw.Draw(im)
    d.line([(60, H - 92), (W - 60, H - 92)], fill=(255, 255, 255, 90), width=2)
    d.text((60, H - 72), "@conjunturadiaria", font=sans(30, True), fill=(255, 255, 255))
    if credit:
        d.text((W // 2, H - 72), credit, font=sans(24), fill=LIGHT, anchor="ma")
    d.text((W - 60, H - 72), f"{n}/{total}", font=sans(30, True), fill=(255, 255, 255), anchor="ra")


def pill(im, x, y, text, hot=False):
    d = ImageDraw.Draw(im)
    f = sans(30, True)
    pad = 50 if hot else 22
    w = int(d.textlength(text, font=f)) + pad + 22
    d.rounded_rectangle((x, y, x + w, y + 54), radius=27, fill=(255, 255, 255) if hot else MID)
    if hot:
        d.ellipse((x + 18, y + 17, x + 38, y + 37), fill=(220, 38, 38))
    d.text((x + pad, y + 11), text, font=f, fill=MID if hot else (255, 255, 255))
    return y + 54


def slide_news(s, n, total, date_txt, used, credits):
    img, cred = photo(s.get("foto") or s.get("titulo", ""), used)
    credits.append(cred)
    im = overlay(background(img), 0.22 if img else 0.0)
    header(im, date_txt)
    d = ImageDraw.Draw(im)
    hot = s.get("tipo") == "ultima_hora"
    tf = serif(76 if len(s.get("titulo", "")) < 60 else 64)
    bf = sans(40)
    tl = wrap(d, s.get("titulo", ""), tf, W - 120)[:4]
    bl = wrap(d, s.get("texto", ""), bf, W - 120)[:7]
    block = 54 + 30 + len(tl) * int(tf.size * 1.18) + 26 + len(bl) * 52
    y = H - 120 - block
    y = pill(im, 60, y, ("ÚLTIMA HORA" if hot else (s.get("tag") or "MERCADOS").upper()), hot) + 30
    for ln in tl:
        d.text((60, y), ln, font=tf, fill=(255, 255, 255))
        y += int(tf.size * 1.18)
    y += 26
    for ln in bl:
        d.text((60, y), ln, font=bf, fill=(236, 228, 248))
        y += 52
    footer(im, n, total, cred)
    return im


def slide_cover(ed, n, total, date_txt, used, credits, heads):
    img, cred = photo(ed.get("capa_foto") or "stock market city morning", used)
    credits.append(cred)
    im = overlay(background(img), 0.10 if img else 0.0)
    d = ImageDraw.Draw(im)
    logo = Image.open(os.path.join(ROOT, "assets", LOGO)).convert("RGBA").resize((210, 210), Image.LANCZOS)
    im.alpha_composite(logo, ((W - 210) // 2, 120))
    d.text((W // 2, 360), "CONJUNTURA DIÁRIA", font=sans(52, True), fill=(255, 255, 255), anchor="ma")
    d.text((W // 2, 422), date_txt, font=sans(34), fill=LIGHT, anchor="ma")
    tf = serif(70)
    y = 560
    for ln in wrap(d, ed.get("capa_titulo") or "O que mexeu com o mundo e com o teu bolso", tf, W - 140)[:3]:
        d.text((W // 2, y), ln, font=tf, fill=(255, 255, 255), anchor="ma")
        y += 84
    y += 30
    for h in heads[:5]:
        for i, ln in enumerate(wrap(d, h, sans(36), W - 200)[:2]):
            d.text((100, y), ("•  " if i == 0 else "    ") + ln, font=sans(36), fill=(236, 228, 248))
            y += 46
        y += 8
    footer(im, n, total, cred)
    return im


def slide_end(n, total, date_txt, wd=0):
    im = overlay(background(None), 0.0)
    d = ImageDraw.Draw(im)
    logo = Image.open(os.path.join(ROOT, "assets", LOGO)).convert("RGBA").resize((260, 260), Image.LANCZOS)
    im.alpha_composite(logo, ((W - 260) // 2, 260))
    d.text((W // 2, 590), "Até segunda-feira." if wd >= 4 else "Amanhã há mais.", font=serif(78), fill=(255, 255, 255), anchor="ma")
    for i, ln in enumerate(["Segue a Conjuntura Diária para receberes", "as notícias dos mercados todas as manhãs."]):
        d.text((W // 2, 720 + i * 52), ln, font=sans(40), fill=(236, 228, 248), anchor="ma")
    for i, ln in enumerate(wrap(d, "Compilação de notícias de fontes públicas, para informação. Não é recomendação de investimento: a decisão é sempre de quem investe.", sans(30), W - 200)):
        d.text((W // 2, 1000 + i * 40), ln, font=sans(30), fill=LIGHT, anchor="ma")
    footer(im, n, total, None)
    return im


def build_slides(ed):
    sl = ed.get("slides")
    if sl:
        return [s for s in sl if s.get("titulo")][:8]
    out = []
    for t in (ed.get("themes") or []):
        if t.get("t") == "Na tua carteira":
            continue
        out.append({"tipo": "noticia", "titulo": t.get("t", ""), "texto": t.get("txt", ""), "tag": "Mercados", "foto": t.get("foto") or re.sub(r"[^\w\s]", " ", t.get("t", ""))})
    return out[:6]


def render(ed, force=False):
    global DARK, MID, LIGHT, LOGO
    day = ed["id"]
    cor, DARK, MID, LIGHT = paleta(day)
    LOGO = f"logo-{cor}.png"
    outdir = os.path.join(ROOT, "slides", day)
    ip = os.path.join(outdir, "info.json")
    if os.path.exists(ip) and not force:
        old = json.load(open(ip))
        sem_fotos = os.environ.get("PIXABAY_KEY") and not any(old.get("creditos") or [])
        if old.get("v") == VERSION and old.get("fonte") == ed.get("_fonte") and not sem_fotos:
            print("já existem slides para", day); return
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    dt = datetime.strptime(day, "%Y-%m-%d")
    date_txt = f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"
    news = build_slides(ed)
    total = len(news) + 2
    used, credits = set(), []
    heads = [s["titulo"] for s in news]
    ims = [slide_cover(ed, 1, total, date_txt, used, credits, heads)]
    for i, s in enumerate(news):
        ims.append(slide_news(s, i + 2, total, date_txt, used, credits))
    ims.append(slide_end(total, total, date_txt, dt.weekday()))
    for i, im in enumerate(ims):
        im.convert("RGB").save(os.path.join(outdir, f"{i + 1:02d}.png"), optimize=True)
    caption = ed.get("legenda") or (ed.get("summary", "")[:600] + "\n\n#mercados #economia #bolsa #investimentos #portugal")
    json.dump({"v": VERSION, "fonte": ed.get("_fonte"), "dia": day, "slides": [f"{i + 1:02d}.png" for i in range(len(ims))], "creditos": credits, "legenda": caption}, open(ip, "w"), ensure_ascii=False, indent=1)
    idx_path = os.path.join(ROOT, "slides", "index.json")
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else []
    idx = [x for x in idx if x.get("dia") != day]
    idx.insert(0, {"dia": day, "n": len(ims)})
    json.dump(sorted(idx, key=lambda x: x["dia"], reverse=True)[:30], open(idx_path, "w"), ensure_ascii=False, indent=1)
    print("slides", day, len(ims))


def main():
    force = os.environ.get("FORCE") == "1"
    todo = {}
    eds = [e for e in json.load(open(os.path.join(ROOT, "data", "edicoes.json"), encoding="utf-8")) if e.get("id")]
    if eds:
        ed = sorted(eds, key=lambda e: e["id"])[-1]
        ed["_fonte"] = "edicao"
        todo[ed["id"]] = ed
    md = os.path.join(ROOT, "data", "slides-manual")
    if os.path.isdir(md):  # slides feitos à mão (têm prioridade sobre a edição do mesmo dia)
        for f in sorted(os.listdir(md))[-3:]:
            if f.endswith(".json"):
                ed = json.load(open(os.path.join(md, f), encoding="utf-8"))
                ed["_fonte"] = "manual"
                todo[ed["id"]] = ed
    for day in sorted(todo):
        render(todo[day], force)


if __name__ == "__main__":
    main()
