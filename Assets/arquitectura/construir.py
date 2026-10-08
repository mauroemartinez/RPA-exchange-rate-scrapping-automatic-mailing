"""Arma el diagrama de arquitectura (HTML) y lo renderiza a PNG con Chromium.

Deja el PNG en Assets/Architecture.png, que es donde lo busca el README; los HTML intermedios quedan en esta carpeta.

Uso: python construir.py

Los logos salen de iconos/ (bajados con bajar_iconos.py) y quedan embebidos en el
HTML como data URI, así que el HTML se puede editar y volver a renderizar sin red,
salvo por las tipografías de Google Fonts.
"""

import base64
import io
import re
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
    '<radialGradient id="r" cx=".18" cy=".2" r=".55"><stop offset="0" stop-color="#EA4335"/><stop offset=".45" stop-color="#EA4335"/>'
    '<stop offset="1" stop-color="#EA4335" stop-opacity="0"/></radialGradient>'
    '<radialGradient id="y" cx=".2" cy=".85" r=".55"><stop offset="0" stop-color="#FBBC04"/><stop offset=".45" stop-color="#FBBC04"/>'
    '<stop offset="1" stop-color="#FBBC04" stop-opacity="0"/></radialGradient>'
    '<radialGradient id="v" cx=".85" cy=".8" r=".55"><stop offset="0" stop-color="#34A853"/><stop offset=".45" stop-color="#34A853"/>'
    '<stop offset="1" stop-color="#34A853" stop-opacity="0"/></radialGradient>'
    '<clipPath id="c"><path d="M50 3C53 30 70 47 97 50C70 53 53 70 50 97C47 70 30 53 3 50C30 47 47 30 50 3Z"/></clipPath></defs>'
    '<g clip-path="url(#c)"><rect width="100" height="100" fill="#4285F4"/><rect width="100" height="100" fill="url(#r)"/>'
    '<rect width="100" height="100" fill="url(#y)"/><rect width="100" height="100" fill="url(#v)"/></g></svg>'
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
        # Sin logos ni viñetas: la lista de fuentes de la opción 2 (FUENTES_LISTA, definida más abajo), cada una con su ícono
        "fuentes": True,
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
          <img src="{GEMINI}" style="width:104px;margin-top:14px;filter:drop-shadow(0 0 14px rgba(66,133,244,.7))">
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
.fuentes1 { flex: 1; width: 100%; display: flex; flex-direction: column; justify-content: space-around;
  margin-top: 6px; }
.fuentes1 .fuente { display: flex; align-items: center; gap: 10px; padding: 6px 2px; }
.fuentes1 .fuente + .fuente { border-top: 1px dashed #3B2350; }
.fuentes1 .fuente img { width: 36px; flex: 0 0 36px; }
.fuentes1 .n { font: 600 16px/1.15 'Barlow', sans-serif; color: #fff; }
.fuentes1 .d { font: 400 13.5px/1.25 'Barlow', sans-serif; color: #C9C9D1; margin-top: 2px; }
.conectores { position: absolute; left: 0; top: 0; width: 100%; height: 100%; pointer-events: none; }
.barra { position: absolute; top: 806px; left: 470px; display: flex; align-items: center; gap: 22px; }
.barra .iconos { display: flex; align-items: center; gap: 14px; }
.barra .iconos img { width: 64px; filter: drop-shadow(0 0 8px rgba(196,107,255,.6)); }
.barra .iconos img.gh { width: 54px; filter: drop-shadow(0 0 8px rgba(255,255,255,.35)); }
.barra .iconos img.gha { width: 58px; filter: drop-shadow(0 0 8px rgba(32,136,255,.7)); }
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
        if col.get("fuentes"):
            cuerpo = '<div class="fuentes1">' + "".join(
                f'<div class="fuente"><img src="{icono}"><div><div class="n">{n}</div><div class="d">{d}</div></div></div>'
                for icono, n, d in FUENTES_LISTA
            ) + "</div>"
        else:
            items = "".join(f"<li>{t}</li>" for t in col["items"])
            cuerpo = f'<div class="logos">{col["logos"]}</div><ul>{items}</ul>'
        tarjetas.append(
            f'<div class="tarjeta {col["clase"]}" style="left:{x}px">'
            f'<div class="num">{i + 1}</div><div class="titulo">{col["titulo"]}</div>{cuerpo}</div>'
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
    lineas.append(f'<path d="M{c1} 806 V866 H456" fill="none" stroke="{violeta}" stroke-width="2.2" stroke-dasharray="7 6"/>')
    lineas.append(f'<path d="M448 860 L458 866 L448 872" fill="none" stroke="{violeta}" stroke-width="2.4"/>')
    lineas.append(f'<path d="M1430 866 H{c7} V806" fill="none" stroke="{violeta}" stroke-width="2.2" stroke-dasharray="7 6"/>')
    lineas.append(f'<path d="M{c7 - 6} 814 L{c7} 804 L{c7 + 6} 814" fill="none" stroke="{violeta}" stroke-width="2.4"/>')
    conectores = f'<svg class="conectores" viewBox="0 0 {ANCHO} {ALTO}">{"".join(lineas)}</svg>'

    barra = (
        f'<div class="barra"><div class="iconos"><img src="{CALENDARIO}">'
        f'<img class="gh" src="{si("github", "#FFFFFF")}"><img class="gha" src="{dev("githubactions")}"></div>'
        '<div><div class="t1">Orchestration · GitHub Actions</div>'
        '<div class="t2"><b>Free plan:</b> runs pipeline.py every business day at 16:00, skips holidays and checks the row at 17:00.'
        '<br>Tests every push in CI. FastAPI + Docker stay optional for a future server.</div></div></div>'
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


# Las fuentes de la columna 1, cada una con su ícono

FUENTES_LISTA = [
    (NAVEGADOR, "BNA · DolarHoy · Ámbito", "FX quotes (Playwright)"),
    (BANCO, "BCRA API", "BADLAR, inflation, money, debt"),
    (BANCO, "St. Louis FED", "EFFR"),
    (NUBE_API, "ArgentinaDatos", "country risk, holidays"),
    (si("yahoo", "#9B5CFF"), "Yahoo Finance", "BTC"),
    (PLANILLA, "Secretaría de Finanzas", "public debt (monthly)"),
]


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
    (DIR / "architecture.html").write_text(opcion_1(), encoding="utf-8")
    renderizar({"architecture.html": "Architecture.png"})
