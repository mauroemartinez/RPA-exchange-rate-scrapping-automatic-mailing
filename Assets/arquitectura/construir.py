"""Arma el diagrama de arquitectura (HTML) y lo renderiza a PNG con Chromium.

Deja los PNG en Assets/ (Architecture.png y Architecture_opcion2.png), que es
donde los busca el README; los HTML intermedios quedan en esta carpeta.

Uso: python construir.py [1|2|ambas]

Los logos salen de iconos/ (bajados con bajar_iconos.py) y quedan embebidos en el
HTML como data URI, así que el HTML se puede editar y volver a renderizar sin red,
salvo por las tipografías de Google Fonts.
"""

import base64
import io
import re
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
ICONOS = DIR / "iconos"
ANCHO, ALTO = 1728, 910

FUENTES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700'
    '&family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700'
    '&family=Playfair+Display:wght@700;800&display=block" rel="stylesheet">'
)


# ── Íconos ──────────────────────────────────────────────────────────────────

def _uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def dev(nombre: str) -> str:
    """Logo a color de devicon, tal cual."""
    return _uri((ICONOS / f"dev_{nombre}.svg").read_text(encoding="utf-8"))


def si(nombre: str, color: str) -> str:
    """Logo monocromo de Simple Icons, pintado del color pedido."""
    svg = (ICONOS / f"si_{nombre}.svg").read_text(encoding="utf-8")
    svg = re.sub(r"<title>.*?</title>", "", svg)
    svg = svg.replace("<svg ", f'<svg fill="{color}" ', 1)
    return _uri(svg)


GLOBO = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" stroke="#B866FF" stroke-width="2.6">'
    '<circle cx="32" cy="32" r="27"/><ellipse cx="32" cy="32" rx="12" ry="27"/>'
    '<path d="M5 32h54M9.5 18h45M9.5 46h45"/></svg>'
)

NUBE_API = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 84" fill="none" stroke="#C46BFF" stroke-width="3">'
    '<path d="M26 54h46a15 15 0 0 0 1-30 22 22 0 0 0-41-6A17 17 0 0 0 26 54z" stroke-linejoin="round"/>'
    '<text x="48" y="46" font-family="Barlow, sans-serif" font-weight="700" font-size="19" fill="#D9A6FF" '
    'stroke="none" text-anchor="middle">API</text>'
    '<circle cx="48" cy="70" r="5.5"/><circle cx="48" cy="70" r="10" stroke-width="4.5" stroke-dasharray="3.6 4.25"/>'
    '<path d="M48 54v6"/></svg>'
)

GEMINI = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs>'
    '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#3D7BFF"/><stop offset=".55" stop-color="#9D6BFF"/>'
    '<stop offset="1" stop-color="#FF6FB1"/></linearGradient></defs>'
    '<path d="M50 3C53 30 70 47 97 50C70 53 53 70 50 97C47 70 30 53 3 50C30 47 47 30 50 3Z" fill="url(#g)"/></svg>'
)

SEABORN = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs>'
    '<linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8CC4EE"/>'
    '<stop offset="1" stop-color="#2B5C9E"/></linearGradient>'
    '<clipPath id="c"><circle cx="32" cy="32" r="28"/></clipPath></defs>'
    '<circle cx="32" cy="32" r="28" fill="#0E2A4D"/>'
    '<g clip-path="url(#c)"><path d="M0 36C14 25 24 45 38 34S58 27 64 31V64H0Z" fill="url(#s)"/>'
    '<path d="M0 47C14 39 26 56 40 45S58 41 64 45V64H0Z" fill="#244F8A"/></g>'
    '<circle cx="32" cy="32" r="28" fill="none" stroke="#A9CCEB" stroke-width="2"/></svg>'
)

SOBRE = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 124 80"><defs>'
    '<linearGradient id="e" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FF8AA6"/>'
    '<stop offset="1" stop-color="#E52A62"/></linearGradient></defs>'
    '<g stroke="#FF5A7E" stroke-width="3.2" stroke-linecap="round"><path d="M2 24h20M9 37h13M2 50h20"/></g>'
    '<rect x="30" y="9" width="90" height="62" rx="6" fill="url(#e)" stroke="#FFC0CF" stroke-width="2"/>'
    '<path d="M32 13L75 45L118 13" fill="none" stroke="#FFE4EB" stroke-width="3.2" stroke-linejoin="round"/>'
    '<path d="M32 69L63 41M118 69L87 41" fill="none" stroke="#FFC6D3" stroke-width="2"/></svg>'
)

CAMPANA = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" stroke="#FF5A7E" stroke-width="3.6" '
    'stroke-linejoin="round" stroke-linecap="round">'
    '<path d="M32 9c-10.5 0-17.5 7.5-17.5 18.5V38L8.5 46h47l-6-8V27.5C49.5 16.5 42.5 9 32 9z"/>'
    '<path d="M26 51.5a6 6 0 0 0 12 0"/><path d="M9 19c2-5 5-8.5 9-11M55 19c-2-5-5-8.5-9-11"/></svg>'
)

CALENDARIO = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 84 84" fill="none" stroke="#C46BFF" stroke-width="3.6" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="6" y="13" width="58" height="54" rx="8"/><path d="M6 28h58M21 6v13M49 6v13"/>'
    '<path d="M18 40h7M31 40h7M44 40h4M18 53h7M31 53h4"/>'
    '<circle cx="61" cy="61" r="17" fill="#000"/><path d="M61 52v10l7 4"/></svg>'
)

FLECHA = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 40"><defs>'
    '<linearGradient id="a" x1="0" x2="1"><stop offset="0" stop-color="#1663F5"/>'
    '<stop offset="1" stop-color="#3FA2FF"/></linearGradient></defs>'
    '<path d="M2 13h23V2l21 18-21 18V27H2z" fill="url(#a)"/></svg>'
)

FLECHA_ABAJO = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 48"><defs>'
    '<linearGradient id="a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1663F5"/>'
    '<stop offset="1" stop-color="#3FA2FF"/></linearGradient></defs>'
    '<path d="M13 2h14v23h11L20 46 2 25h11z" fill="url(#a)"/></svg>'
)

BANCO = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" stroke="#B866FF" stroke-width="3" '
    'stroke-linejoin="round"><path d="M6 24L32 9l26 15z"/><path d="M12 28v20M24 28v20M40 28v20M52 28v20"/>'
    '<path d="M6 52h52M4 58h56"/></svg>'
)

NAVEGADOR = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" stroke="#B866FF" stroke-width="3" '
    'stroke-linejoin="round"><rect x="5" y="10" width="54" height="44" rx="6"/><path d="M5 21h54"/>'
    '<circle cx="12" cy="15.5" r="1.6" fill="#B866FF"/><circle cx="18" cy="15.5" r="1.6" fill="#B866FF"/>'
    '<path d="M14 44l9-10 8 6 10-12 9 8" stroke-linecap="round"/></svg>'
)

PLANILLA = _uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none" stroke="#B866FF" stroke-width="3" '
    'stroke-linejoin="round"><path d="M14 4h26l12 12v44H14z"/><path d="M40 4v12h12"/>'
    '<path d="M21 28h24M21 37h24M21 46h24M30 28v26"/></svg>'
)


# ── Estilos comunes ─────────────────────────────────────────────────────────

CSS_BASE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: %(W)spx; height: %(H)spx; background: #000; overflow: hidden; }
body { -webkit-font-smoothing: antialiased; color: #F4F4F5; font-family: 'Barlow', sans-serif; }
#lienzo { position: relative; width: %(W)spx; height: %(H)spx;
  background: radial-gradient(ellipse 70%% 55%% at 50%% 40%%, #070912 0%%, #000 70%%); }
h1 { position: absolute; top: 12px; left: 0; width: 100%%; text-align: center;
  font: 600 50px/1.1 'Oswald', sans-serif; letter-spacing: 1.2px; color: #fff; }
h1 .c { color: #23AEF5; text-shadow: 0 0 16px rgba(35,174,245,.35); }
.sub { position: absolute; top: 80px; left: 0; width: 100%%; text-align: center;
  font: 400 23px 'Barlow', sans-serif; letter-spacing: .3px; color: #E4E4E7; }
.flecha { position: absolute; width: 44px; height: 37px;
  filter: drop-shadow(0 0 6px rgba(40,140,255,.85)); }
.cap { font: 500 20px 'Barlow', sans-serif; color: #fff; text-align: center; line-height: 1.1; }
.cap.chica { font-size: 15px; font-weight: 500; color: #E4E4E7; }
.cap.grande { font-size: 30px; font-weight: 500; }
""" % {"W": ANCHO, "H": ALTO}


def tarjeta_css(clase: str, borde: str, titulo: str) -> str:
    return (
        f".{clase} {{ --c: {borde}; --t: {titulo}; }}\n"
    )


# ── Opción 1: el mismo diagrama, actualizado ────────────────────────────────

COLUMNAS = [
    {
        "clase": "c1", "borde": "#A855F7", "titulo_color": "#C17BFF", "titulo": "Data Sources",
        "logos": f"""
          <img src="{GLOBO}" style="width:86px;margin-top:6px;filter:drop-shadow(0 0 8px rgba(184,102,255,.45))">
          <img src="{NUBE_API}" style="width:108px;margin-top:22px;filter:drop-shadow(0 0 8px rgba(196,107,255,.45))">""",
        "items": [
            "FX portals: BNA, DolarHoy, Ámbito",
            "BCRA API: rates, inflation, money &amp; debt",
            "St. Louis FED API (EFFR)",
            "ArgentinaDatos: country risk &amp; holidays",
            "Yahoo Finance (BTC)",
            "Secretaría de Finanzas: public debt",
        ],
    },
    {
        "clase": "c2", "borde": "#1ECBEA", "titulo_color": "#33D6F2", "titulo": "Data Extraction",
        "logos": f"""
          <img src="{dev('python')}" style="width:62px">
          <div class="cap">Python</div>
          <div class="httpx">http<span>x</span></div>
          <img src="{dev('playwright')}" style="width:76px;margin-top:2px">
          <div class="cap" style="font-size:24px">Playwright</div>""",
        "items": [
            "Async REST APIs with httpx",
            "Concurrent Playwright scrapers",
            "Headless Chromium",
            "Retries with backoff",
            "Structured ScraperError alerts",
        ],
    },
    {
        "clase": "c3", "borde": "#12B5CC", "titulo_color": "#2AD0E0", "titulo": "Validation &amp; Loading",
        "logos": f"""
          <div class="sqla">SQL<span>Alchemy</span></div>
          <img src="{si('pydantic', '#E92063')}" style="width:66px;margin-top:22px;filter:drop-shadow(0 0 8px rgba(233,32,99,.45))">
          <div class="cap grande" style="margin-top:6px">Pydantic</div>""",
        "items": [
            "Pydantic validation gate",
            "Bad rows blocked before DB write",
            "Idempotent upsert (ON CONFLICT)",
            "Run lock against duplicate runs",
            "Freshness checks per source",
        ],
    },
    {
        "clase": "c4", "borde": "#2FD27C", "titulo_color": "#46E08E", "titulo": "Cloud Relational Database",
        "logos": f"""
          <img src="{dev('postgresql')}" style="width:84px">
          <div class="cap" style="font-size:24px">PostgreSQL</div>
          <img src="{dev('supabase')}" style="width:64px;margin-top:10px;filter:drop-shadow(0 0 10px rgba(62,207,142,.5))">
          <div class="cap" style="font-size:20px">Supabase</div>""",
        "items": [
            "Supabase cloud PostgreSQL",
            "Fact_Mercado_Macro: daily row + AI texts",
            "Fact_Series_Macro: money &amp; debt series in original units",
            "Row level security",
        ],
    },
    {
        "clase": "c5", "borde": "#B38BF5", "titulo_color": "#C3A2FF", "titulo": "AI Narrative (Gemini)",
        "logos": f"""
          <img src="{GEMINI}" style="width:104px;margin-top:14px;filter:drop-shadow(0 0 14px rgba(157,107,255,.75))">
          <div class="cap grande" style="margin-top:12px">Gemini</div>""",
        "items": [
            "Structured JSON output",
            "Summary + per-chart comments",
            "Validated with Pydantic",
            "Multi-key &amp; model failover",
            "Single-paragraph fallback",
            "Daily + 25-session context",
        ],
    },
    {
        "clase": "c6", "borde": "#F2CC0C", "titulo_color": "#FFD60A", "titulo": "Analytics &amp; Reporting",
        "logos": f"""
          <img src="{dev('python')}" style="width:52px">
          <div class="cap" style="font-size:18px">Python</div>
          <div class="rejilla">
            <div><span class="disco"><img src="{dev('matplotlib')}" style="width:44px"></span><div class="cap chica">matplotlib</div></div>
            <div><img src="{SEABORN}" style="width:50px"><div class="cap chica">seaborn</div></div>
            <div><img src="{si('jinja', '#F2F2F2')}" style="width:50px;margin:2px 0 1px"><div class="cap chica">Jinja2</div></div>
            <div><img src="{si('microsoftpowerpoint', '#E0592F')}" style="width:46px;margin:3px 0 2px"><div class="cap chica">PowerPoint</div></div>
          </div>""",
        "items": [
            "6 charts: FX &amp; risk, inflation, variations, BTC, money, debt in USD",
            "Spreads &amp; Fisher forwards",
            "HTML/CSS email template",
            "Executive PowerPoint deck",
        ],
    },
    {
        "clase": "c7", "borde": "#FF4766", "titulo_color": "#FF5C78", "titulo": "Automatic Delivery",
        "logos": f"""
          <img src="{SOBRE}" style="width:118px;filter:drop-shadow(0 0 10px rgba(255,80,120,.45))">
          <div class="cap" style="font-size:22px">Gmail SMTP</div>
          <div class="fila-logos" style="gap:22px;margin-top:8px">
            <img src="{dev('html5')}" style="width:40px"><img src="{dev('css3')}" style="width:40px">
          </div>
          <div class="fila-logos" style="gap:26px;margin-top:8px">
            <div><img src="{si('github', '#FFFFFF')}" style="width:46px"><div class="cap chica">GitHub</div></div>
            <div><img src="{CAMPANA}" style="width:46px"><div class="cap chica">alerts</div></div>
          </div>""",
        "items": [
            "Two mail variants, one with CSV",
            "Charts committed to GitHub",
            "Deck replaced daily on its own branch",
            "Failure alerts + daily control",
        ],
    },
]

CSS_1 = CSS_BASE + """
.tarjeta { position: absolute; top: 152px; width: 216px; height: 592px; border: 2px solid var(--c);
  border-radius: 14px; background: linear-gradient(180deg, color-mix(in srgb, var(--c) 6%, #000) 0%, #000 55%);
  box-shadow: 0 0 7px var(--c), 0 0 18px color-mix(in srgb, var(--c) 40%, transparent),
              inset 0 0 20px color-mix(in srgb, var(--c) 14%, transparent);
  display: flex; flex-direction: column; align-items: center; padding: 34px 10px 16px; }
.num { position: absolute; top: -24px; left: 50%; transform: translateX(-50%); width: 46px; height: 46px;
  border-radius: 50%; border: 3px solid var(--c); background: #000; color: #fff;
  font: 600 27px/1 'Oswald', sans-serif; display: flex; align-items: center; justify-content: center;
  box-shadow: 0 0 10px var(--c), inset 0 0 6px color-mix(in srgb, var(--c) 40%, transparent); }
.titulo { color: var(--t); font: 600 21.5px/1.22 'Barlow Condensed', sans-serif; letter-spacing: .7px;
  text-transform: uppercase; text-align: center; min-height: 54px; display: flex; align-items: center;
  text-shadow: 0 0 10px color-mix(in srgb, var(--c) 45%, transparent); }
.logos { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; gap: 2px; margin-top: 8px; }
.fila-logos { display: flex; align-items: center; justify-content: center; }
.fila-logos > div { display: flex; flex-direction: column; align-items: center; }
ul { list-style: none; margin-top: auto; width: 100%; padding: 0 4px 0 8px; }
li { position: relative; padding-left: 15px; font: 400 15.6px/1.3 'Barlow', sans-serif; color: #F4F4F5;
  margin-bottom: 6px; }
li:last-child { margin-bottom: 0; }
li::before { content: ""; position: absolute; left: 1px; top: 8px; width: 5px; height: 5px; border-radius: 50%;
  background: #fff; }
.httpx { font: 700 50px/1 'Barlow', sans-serif; color: #fff; letter-spacing: -.5px; margin: 10px 0 6px; }
.httpx span { color: #24C6F0; }
.sqla { font: 800 33px/1 'Playfair Display', serif; color: #ECECEC; letter-spacing: -.4px; margin-top: 16px;
  text-shadow: 0 0 2px rgba(255,255,255,.25); }
.sqla span { color: #E2342C; }
.rejilla { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 22px; margin-top: 8px; }
.rejilla > div { display: flex; flex-direction: column; align-items: center; }
.disco { display: inline-flex; width: 50px; height: 50px; border-radius: 50%; background: #F3F3F3;
  align-items: center; justify-content: center; margin-bottom: 1px; }
.conectores { position: absolute; left: 0; top: 0; width: 100%; height: 100%; pointer-events: none; }
.barra { position: absolute; top: 806px; left: 610px; display: flex; align-items: center; gap: 22px; }
.barra img { width: 82px; filter: drop-shadow(0 0 8px rgba(196,107,255,.6)); }
.barra .t1 { font: 600 26px/1.15 'Barlow Condensed', sans-serif; letter-spacing: 1.2px; color: #D27BFF;
  text-transform: uppercase; text-shadow: 0 0 10px rgba(196,107,255,.45); }
.barra .t2 { font: 400 17.5px/1.35 'Barlow', sans-serif; color: #E4E4E7; margin-top: 4px; }
.barra .t2 b { font-weight: 600; color: #fff; }
"""


def opcion_1() -> str:
    ancho, hueco, izq = 216, 30, 16
    css = CSS_1 + "".join(tarjeta_css(c["clase"], c["borde"], c["titulo_color"]) for c in COLUMNAS)
    tarjetas, flechas, centros = [], [], []
    for i, col in enumerate(COLUMNAS):
        x = izq + i * (ancho + hueco)
        centros.append(x + ancho / 2)
        items = "".join(f"<li>{t}</li>" for t in col["items"])
        tarjetas.append(
            f'<div class="tarjeta {col["clase"]}" style="left:{x}px">'
            f'<div class="num">{i + 1}</div><div class="titulo">{col["titulo"]}</div>'
            f'<div class="logos">{col["logos"]}</div><ul>{items}</ul></div>'
        )
        if i < len(COLUMNAS) - 1:
            fx = x + ancho + hueco / 2 - 22
            flechas.append(f'<img class="flecha" src="{FLECHA}" style="left:{fx}px;top:428px">')

    # Conectores punteados: un pin bajo cada columna, la línea que los une y el lazo
    # que vuelve a empezar cada día desde la barra de programación.
    violeta = "#B45CFF"
    lineas = []
    for i, cx in enumerate(centros):
        color = COLUMNAS[i]["borde"]
        lineas.append(f'<line x1="{cx}" y1="746" x2="{cx}" y2="760" stroke="{color}" stroke-width="2" stroke-dasharray="3 3"/>')
        lineas.append(f'<circle cx="{cx}" cy="768" r="7.5" fill="#000" stroke="{color}" stroke-width="2"/>')
        lineas.append(f'<circle cx="{cx}" cy="768" r="2.2" fill="{color}"/>')
        lineas.append(f'<line x1="{cx}" y1="776" x2="{cx}" y2="796" stroke="{color}" stroke-width="2" stroke-dasharray="3 3"/>')
    c1, c7 = centros[0], centros[-1]
    lineas.append(f'<line x1="{c1}" y1="796" x2="{c7}" y2="796" stroke="{violeta}" stroke-width="2.2" stroke-dasharray="7 6"/>')
    lineas.append(f'<path d="M{c1} 806 V866 H596" fill="none" stroke="{violeta}" stroke-width="2.2" stroke-dasharray="7 6"/>')
    lineas.append(f'<path d="M588 860 L598 866 L588 872" fill="none" stroke="{violeta}" stroke-width="2.4"/>')
    lineas.append(f'<path d="M1366 866 H{c7} V806" fill="none" stroke="{violeta}" stroke-width="2.2" stroke-dasharray="7 6"/>')
    lineas.append(f'<path d="M{c7 - 6} 814 L{c7} 804 L{c7 + 6} 814" fill="none" stroke="{violeta}" stroke-width="2.4"/>')
    conectores = f'<svg class="conectores" viewBox="0 0 {ANCHO} {ALTO}">{"".join(lineas)}</svg>'

    barra = (
        f'<div class="barra"><img src="{CALENDARIO}">'
        '<div><div class="t1">Scheduled cloud automation · GitHub Actions</div>'
        '<div class="t2"><b>Free plan:</b> runs pipeline.py every business day, skips holidays, '
        'tests every push in CI.<br>FastAPI + Docker stay optional for a future server.</div></div></div>'
    )

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>Architecture</title>' + FUENTES + f"<style>{css}</style></head><body>"
        '<div id="lienzo">'
        '<h1>AUTOMATED <span class="c">ARGENTINIAN MACROECONOMIC</span> INTELLIGENCE SYSTEM</h1>'
        '<p class="sub">End-to-end automation: from macro data ingestion to AI insights and automatic delivery</p>'
        + conectores + "".join(tarjetas) + "".join(flechas) + barra +
        "</div></body></html>"
    )


# ── Opción 2: la corrida diaria, de punta a punta ───────────────────────────

ETAPAS = [
    # (número, título, detalle, color de la familia de la opción 1)
    (1, "Control", "run lock · weekends &amp; holidays skipped", "#A855F7"),
    (2, "History", "reads the warehouse; flags an unfinished day", "#2FD27C"),
    (3, "Scraping", "6 sources in parallel", "#1ECBEA"),
    (4, "Validation", "Pydantic gate before any write", "#12B5CC"),
    (5, "Persistence", "idempotent upsert of today's row", "#2FD27C"),
    (6, "AI narrative", "Gemini JSON: summary + chart comments", "#B38BF5"),
    (7, "Indicators", "money &amp; debt series: BCRA, Finanzas", "#1ECBEA"),
    (8, "Charts", "6 charts, debt in USD", "#F2CC0C"),
    (9, "Mail", "2 variants, one with CSV", "#FF4766"),
    (10, "Deck", "executive PowerPoint", "#F2CC0C"),
    (11, "Publish", "charts to GitHub, deck to its branch", "#FF4766"),
    (12, "Series", "money &amp; debt series to Supabase", "#2FD27C"),
]

FUENTES_2 = [
    (NAVEGADOR, "BNA · DolarHoy · Ámbito", "FX quotes (Playwright)"),
    (BANCO, "BCRA API", "BADLAR, inflation, money, debt"),
    (BANCO, "St. Louis FED", "EFFR"),
    (NUBE_API, "ArgentinaDatos", "country risk, holidays"),
    (si("yahoo", "#9B5CFF"), "Yahoo Finance", "BTC"),
    (PLANILLA, "Secretaría de Finanzas", "public debt (monthly)"),
]

CSS_2 = CSS_BASE + """
.sub { top: 78px; }
.panel { position: absolute; border: 2px solid var(--c); border-radius: 16px; background: #000;
  box-shadow: 0 0 7px var(--c), 0 0 20px color-mix(in srgb, var(--c) 38%, transparent),
              inset 0 0 22px color-mix(in srgb, var(--c) 12%, transparent);
  display: flex; flex-direction: column; }
.rotulo { position: absolute; top: -17px; left: 22px; background: #000; padding: 0 10px; color: var(--t);
  font: 600 22px/34px 'Barlow Condensed', sans-serif; letter-spacing: 1px; text-transform: uppercase;
  text-shadow: 0 0 10px color-mix(in srgb, var(--c) 50%, transparent); }
.lista { flex: 1; display: flex; flex-direction: column; justify-content: space-around; }
.fuente { display: flex; align-items: center; gap: 14px; padding: 8px 4px; }
.fuente + .fuente { border-top: 1px dashed #3B2350; }
.fuente img { width: 44px; flex: 0 0 44px; }
.fuente .n { font: 600 18px/1.15 'Barlow', sans-serif; color: #fff; }
.fuente .d { font: 400 15px/1.25 'Barlow', sans-serif; color: #C9C9D1; margin-top: 3px; }
.gha { display: flex; align-items: center; gap: 16px; }
.gha img { width: 60px; filter: drop-shadow(0 0 8px rgba(32,136,255,.6)); }
.gha .t1 { font: 600 26px/1.1 'Barlow Condensed', sans-serif; letter-spacing: 1px; color: #59A8FF;
  text-transform: uppercase; text-shadow: 0 0 10px rgba(32,136,255,.5); }
.gha .t2 { font: 400 16.5px/1.32 'Barlow', sans-serif; color: #E4E4E7; margin-top: 3px; }
.gha .t2 b { color: #fff; font-weight: 600; }
.etapas { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px 26px; }
.etapa { position: relative; border: 2px solid var(--e); border-radius: 12px; padding: 10px 10px 10px 56px;
  height: 100px; background: linear-gradient(90deg, color-mix(in srgb, var(--e) 12%, #000), #000 80%);
  box-shadow: 0 0 9px color-mix(in srgb, var(--e) 45%, transparent); display: flex; flex-direction: column;
  justify-content: center; }
.etapa:not(:nth-child(4n))::after { content: ""; position: absolute; right: -22px; top: 50%; transform: translateY(-50%);
  border-left: 12px solid #3FA2FF; border-top: 8px solid transparent; border-bottom: 8px solid transparent;
  filter: drop-shadow(0 0 4px rgba(63,162,255,.9)); }
.etapa .k { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); width: 36px; height: 36px;
  border-radius: 50%; border: 2.5px solid var(--e); color: #fff; font: 600 18px/1 'Oswald', sans-serif;
  display: flex; align-items: center; justify-content: center; box-shadow: 0 0 8px var(--e); background: #000; }
.etapa .n { font: 600 19px/1.1 'Barlow Condensed', sans-serif; letter-spacing: .6px; text-transform: uppercase;
  color: var(--e); }
.etapa .d { font: 400 15px/1.25 'Barlow', sans-serif; color: #E9E9EE; margin-top: 4px; }
.pie { margin-top: auto; display: flex; align-items: center; justify-content: center; gap: 18px; }
.pie .et { font: 600 16px 'Barlow Condensed', sans-serif; letter-spacing: 1.2px; color: #8FA3BF; text-transform: uppercase; }
.logitos { display: flex; gap: 16px; align-items: center; }
.logitos img { height: 38px; }
.logitos .disco { display: inline-flex; width: 40px; height: 40px; border-radius: 50%; background: #F3F3F3;
  align-items: center; justify-content: center; }
.logitos .disco img { height: 31px; }
.salida { display: flex; gap: 14px; align-items: flex-start; padding: 8px 4px; }
.salida + .salida { border-top: 1px dashed #4A2030; }
.salida .ic { flex: 0 0 64px; display: flex; justify-content: center; padding-top: 2px; }
.salida .n { font: 600 18.5px/1.15 'Barlow', sans-serif; color: #fff; }
.salida .d { font: 400 15px/1.3 'Barlow', sans-serif; color: #D4D4DB; margin-top: 3px; }
.redes { display: flex; flex-wrap: wrap; gap: 10px 12px; }
.chip { border: 1.6px dashed #B45CFF; border-radius: 999px; padding: 7px 16px; font: 500 16px 'Barlow', sans-serif;
  color: #F0E4FF; background: rgba(180,92,255,.07); }
.flecha2 { position: absolute; width: 50px; height: 42px; filter: drop-shadow(0 0 7px rgba(40,140,255,.9)); }
"""


def opcion_2() -> str:
    fuentes = "".join(
        f'<div class="fuente"><img src="{icono}"><div><div class="n">{n}</div><div class="d">{d}</div></div></div>'
        for icono, n, d in FUENTES_2
    )
    etapas = "".join(
        f'<div class="etapa" style="--e:{color}"><div class="k">{k}</div><div class="n">{n}</div><div class="d">{d}</div></div>'
        for k, n, d, color in ETAPAS
    )
    logitos = "".join([
        f'<img src="{dev("python")}">', f'<img src="{dev("playwright")}">', f'<img src="{dev("postgresql")}">',
        f'<img src="{si("pydantic", "#E92063")}">', f'<img src="{GEMINI}">',
        f'<span class="disco"><img src="{dev("matplotlib")}"></span>', f'<img src="{SEABORN}">',
        f'<img src="{si("jinja", "#F2F2F2")}">', f'<img src="{si("microsoftpowerpoint", "#E0592F")}">',
        f'<img src="{dev("githubactions")}">',
    ])
    redes = "".join(
        f'<span class="chip">{t}</span>' for t in [
            "Run lock: one run at a time", "Holidays skipped", "Pydantic gate", "Unfinished day detected",
            "Secrets masked in logs", "Failure alert by mail", "Daily control after the run", "CI tests on every push",
        ]
    )
    salidas = "".join(
        f'<div class="salida"><div class="ic"><img src="{icono}" style="width:{ancho}px"></div>'
        f'<div><div class="n">{n}</div><div class="d">{d}</div></div></div>'
        for icono, ancho, n, d in [
            (SOBRE, 64, "Subscribers' inbox", "HTML report with 6 charts and AI comments; a second variant carries the CSV history"),
            (si("github", "#FFFFFF"), 44, "GitHub repository", "Charts committed to Previews/; the executive deck replaced daily on its own branch"),
            (dev("supabase"), 42, "Supabase warehouse", "Fact_Mercado_Macro: daily row + AI texts. Fact_Series_Macro: money &amp; debt series"),
            (CAMPANA, 44, "Maintainer's inbox", "One alert per failed run, plus the daily control"),
        ]
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>Architecture daily run</title>' + FUENTES + f"<style>{CSS_2}</style></head><body>"
        '<div id="lienzo">'
        '<h1>AUTOMATED <span class="c">ARGENTINIAN MACROECONOMIC</span> INTELLIGENCE SYSTEM</h1>'
        '<p class="sub">One business day, end to end: GitHub Actions runs pipeline.py, which gathers the data, fills the warehouse and delivers the report</p>'
        # Fuentes
        '<div class="panel" style="--c:#A855F7;--t:#C17BFF;left:16px;top:146px;width:300px;height:600px;padding:28px 16px 14px">'
        f'<div class="rotulo">Data sources</div><div class="lista">{fuentes}</div></div>'
        # La corrida
        '<div class="panel" style="--c:#2088FF;--t:#59A8FF;left:372px;top:146px;width:984px;height:600px;padding:30px 26px 18px">'
        '<div class="rotulo">The daily run</div>'
        f'<div class="gha"><img src="{dev("githubactions")}"><div><div class="t1">GitHub Actions · free plan</div>'
        '<div class="t2"><b>Every business day</b> a runner starts <b>pipeline.py</b>. Each stage reports its state and time, '
        'and any error turns the run red and sends one alert.</div></div></div>'
        '<div style="height:1px;margin:16px 0 22px;background:linear-gradient(90deg,transparent,#2088FF,transparent)"></div>'
        f'<div class="etapas">{etapas}</div>'
        f'<div class="pie"><span class="et">Built with</span><div class="logitos">{logitos}</div></div>'
        "</div>"
        # Salidas
        '<div class="panel" style="--c:#FF4766;--t:#FF5C78;left:1412px;top:146px;width:300px;height:600px;padding:28px 14px 14px">'
        f'<div class="rotulo">Outputs</div><div class="lista">{salidas}</div></div>'
        # Flechas entre paneles
        f'<img class="flecha2" src="{FLECHA}" style="left:320px;top:425px">'
        f'<img class="flecha2" src="{FLECHA}" style="left:1359px;top:425px">'
        # Redes de seguridad
        '<div class="panel" style="--c:#B45CFF;--t:#D27BFF;left:16px;top:780px;width:1696px;height:112px;padding:30px 22px 14px;'
        'border-style:dashed">'
        '<div class="rotulo">Safety nets</div>'
        f'<div style="display:flex;align-items:center;gap:20px"><img src="{CALENDARIO}" style="width:60px;flex:0 0 60px;'
        'filter:drop-shadow(0 0 8px rgba(196,107,255,.6))">'
        f'<div class="redes">{redes}</div></div>'
        "</div>"
        "</div></body></html>"
    )


# ── Render ──────────────────────────────────────────────────────────────────

def renderizar(paginas: dict[str, str]) -> None:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            pagina = navegador.new_page(viewport={"width": ANCHO, "height": ALTO}, device_scale_factor=1)
            for html_nombre, png_nombre in paginas.items():
                ruta = DIR / html_nombre
                pagina.goto(ruta.as_uri(), wait_until="networkidle")
                pagina.evaluate("document.fonts.ready.then(() => true)")
                pagina.wait_for_timeout(300)
                crudo = pagina.screenshot(clip={"x": 0, "y": 0, "width": ANCHO, "height": ALTO})
                imagen = Image.open(io.BytesIO(crudo)).convert("RGB")
                destino = DIR.parent / png_nombre  # Assets/, donde los lee el README
                imagen.save(destino, optimize=True)
                if destino.stat().st_size > 700_000:
                    # Paleta de 256 colores: el diagrama es casi plano y la diferencia no se ve
                    imagen.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(
                        destino, optimize=True
                    )
                print(f"{png_nombre}: {destino.stat().st_size / 1024:.0f} KB")
        finally:
            navegador.close()


if __name__ == "__main__":
    cual = sys.argv[1] if len(sys.argv) > 1 else "ambas"
    paginas = {}
    if cual in ("1", "ambas"):
        (DIR / "architecture.html").write_text(opcion_1(), encoding="utf-8")
        paginas["architecture.html"] = "Architecture.png"
    if cual in ("2", "ambas"):
        (DIR / "architecture_opcion2.html").write_text(opcion_2(), encoding="utf-8")
        paginas["architecture_opcion2.html"] = "Architecture_opcion2.png"
    renderizar(paginas)
