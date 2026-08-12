from playwright.async_api import async_playwright

from scrapers.utils import ScraperError, parse_money, retry_scrape

# Riesgo país ya no se scrapea acá: viene de la API en scrapers/riesgo_pais.py.
WEB_MEP = "https://www.ambito.com/contenidos/dolar-mep.html"
WEB_EURO = "https://www.ambito.com/euro-informal"


@retry_scrape
async def _scrape() -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()

            await page.goto(WEB_MEP, wait_until="domcontentloaded")
            mep_value = page.locator(".variation-max-min__value.data-valor")
            await mep_value.wait_for()
            tcv_mep = parse_money(await mep_value.inner_text())

            await page.goto(WEB_EURO, wait_until="domcontentloaded")
            compra = page.locator(".variation-max-min__value.data-compra")
            venta = page.locator(".variation-max-min__value.data-venta")
            await compra.wait_for()
            tcc_euro = parse_money(await compra.inner_text())
            tcv_euro = parse_money(await venta.inner_text())
        finally:
            await browser.close()

    return {
        "TCV_MEP": tcv_mep,
        "TCC_Euro": tcc_euro,
        "TCV_Euro": tcv_euro,
    }


async def run() -> dict:
    try:
        return await _scrape()
    except Exception as exc:
        raise ScraperError("Ambito", "leer cotizaciones", exc) from exc
