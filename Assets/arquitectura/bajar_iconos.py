"""Baja los logos (solo GET a cdn.jsdelivr.net) y los deja en iconos/ para no volver a pedirlos."""
from pathlib import Path

import httpx

DIR = Path(__file__).resolve().parent / "iconos"
DIR.mkdir(exist_ok=True)

DEVICON = "https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/{n}/{n}-{v}.svg"
SIMPLE = "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{s}.svg"

pedidos = {
    # devicon: logos a color
    "dev_python": [DEVICON.format(n="python", v="original")],
    "dev_postgresql": [DEVICON.format(n="postgresql", v="original")],
    "dev_html5": [DEVICON.format(n="html5", v="original")],
    "dev_css3": [DEVICON.format(n="css3", v="original")],
    "dev_matplotlib": [DEVICON.format(n="matplotlib", v="original")],
    "dev_playwright": [DEVICON.format(n="playwright", v="original")],
    "dev_supabase": [DEVICON.format(n="supabase", v="original")],
    "dev_sqlalchemy": [DEVICON.format(n="sqlalchemy", v="original"), DEVICON.format(n="sqlalchemy", v="plain")],
    "dev_githubactions": [DEVICON.format(n="githubactions", v="original")],
    "dev_docker": [DEVICON.format(n="docker", v="original")],
    "dev_fastapi": [DEVICON.format(n="fastapi", v="original")],
    "dev_pandas": [DEVICON.format(n="pandas", v="original")],
    "dev_pytest": [DEVICON.format(n="pytest", v="original")],
    # simple-icons: monocromos, se colorean al armar la página
    "si_github": [SIMPLE.format(s="github")],
    "si_githubactions": [SIMPLE.format(s="githubactions")],
    "si_googlegemini": [SIMPLE.format(s="googlegemini")],
    "si_gmail": [SIMPLE.format(s="gmail")],
    "si_pydantic": [SIMPLE.format(s="pydantic")],
    "si_jinja": [SIMPLE.format(s="jinja")],
    "si_yahoo": [SIMPLE.format(s="yahoo")],
    "si_supabase": [SIMPLE.format(s="supabase")],
    "si_postgresql": [SIMPLE.format(s="postgresql")],
    "si_playwright": [SIMPLE.format(s="playwright")],
    "si_docker": [SIMPLE.format(s="docker")],
    "si_fastapi": [SIMPLE.format(s="fastapi")],
    "si_sqlalchemy": [SIMPLE.format(s="sqlalchemy")],
    "si_pandas": [SIMPLE.format(s="pandas")],
    "si_microsoftpowerpoint": [SIMPLE.format(s="microsoftpowerpoint")],
    "si_python": [SIMPLE.format(s="python")],
}

with httpx.Client(timeout=20, follow_redirects=True) as c:
    for nombre, urls in pedidos.items():
        destino = DIR / f"{nombre}.svg"
        if destino.exists():
            print(f"{nombre:<24} ya estaba")
            continue
        for url in urls:
            r = c.get(url)
            if r.status_code == 200 and "<svg" in r.text:
                destino.write_text(r.text, encoding="utf-8")
                print(f"{nombre:<24} OK  {len(r.text):>6} bytes")
                break
        else:
            print(f"{nombre:<24} NO  ({r.status_code})")
