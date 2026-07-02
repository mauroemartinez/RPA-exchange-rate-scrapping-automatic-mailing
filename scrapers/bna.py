from playwright.async_api import async_playwright

from scrapers.utils import ScraperError, parse_money, retry_scrape, run_playwright

WEB_BNA = "https://www.bna.com.ar/Personas"

BILLETES_ROW = "#billetes table tbody tr:first-child"
DIVISAS_ROW = "#divisas table tbody tr:first-child"


@retry_scrape
async def _scrape() -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(WEB_BNA, wait_until="domcontentloaded")

            billetes_row = page.locator(BILLETES_ROW)
            await billetes_row.wait_for()
            tcc_billete = parse_money(await billetes_row.locator("td").nth(1).inner_text())
            tcv_billete = parse_money(await billetes_row.locator("td").nth(2).inner_text())

            await page.locator("#rightHome").get_by_role("link", name="Divisas").click()
            divisas_row = page.locator(DIVISAS_ROW)
            await divisas_row.wait_for()
            tcc_divisas = parse_money(await divisas_row.locator("td").nth(1).inner_text())
            tcv_divisas = parse_money(await divisas_row.locator("td").nth(2).inner_text())
        finally:
            await browser.close()

    return {
        "TCC_Billete": tcc_billete,
        "TCV_Billete": tcv_billete,
        "TCC_Divisas": tcc_divisas,
        "TCV_Divisas": tcv_divisas,
        "Solidario": tcv_billete * 1.3,
    }


async def run() -> dict:
    """Scrapea TC billete y divisas de BNA. Devuelve las mismas claves que armaba
    la celda de Selenium: TCC_Billete, TCV_Billete, TCC_Divisas, TCV_Divisas, Solidario.
    Reintenta ante timeouts transitorios; si se agotan los reintentos, propaga un
    ScraperError con contexto en vez de fallar silenciosamente."""
    try:
        return await _scrape()
    except Exception as exc:
        raise ScraperError("BNA", "leer cotizaciones", exc) from exc


def run_sync() -> dict:
    """Versión sincrónica de run(), pensada para llamarse desde una celda de
    notebook sin pelearse con el event loop que ya corre el kernel de Jupyter."""
    return run_playwright(run())
