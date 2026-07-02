from playwright.async_api import async_playwright

from scrapers.utils import ScraperError, parse_money, retry_scrape, run_playwright

WEB_DOLARHOY = "https://dolarhoy.com/cotizaciondolarblue"


@retry_scrape
async def _scrape() -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(WEB_DOLARHOY, wait_until="domcontentloaded")

            values = page.locator(".cotizacion_value .value")
            await values.first.wait_for()
            tcc_blue = parse_money(await values.nth(0).inner_text())
            tcv_blue = parse_money(await values.nth(1).inner_text())
        finally:
            await browser.close()

    return {"TCC_Blue": tcc_blue, "TCV_Blue": tcv_blue}


async def run() -> dict:
    try:
        return await _scrape()
    except Exception as exc:
        raise ScraperError("DolarHoy", "leer cotización blue", exc) from exc


def run_sync() -> dict:
    return run_playwright(run())
