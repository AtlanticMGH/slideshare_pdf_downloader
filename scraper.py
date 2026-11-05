import argparse
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

PROJECT_DIR = Path(__file__).resolve().parent
IMAGES_DIR = PROJECT_DIR / "images"


def wait_for_slide(page: Page, n: int, timeout: int = 8000) -> bool:
    """Wait until the container #slide{n} exists in the DOM, scrolling down to trigger loading."""
    selector = f"#slide{n}"
    waited = 0
    step = 500
    while waited < timeout:
        if page.locator(selector).count() > 0:
            return True
        # Scroll to the bottom so more slides get loaded
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(step)
        waited += step
    return page.locator(selector).count() > 0


def download_slides(url: str) -> int:
    """Download all slides as images into IMAGES_DIR. Returns the number of saved slides."""
    IMAGES_DIR.mkdir(exist_ok=True)

    # Remove old slides so different presentations don't get mixed up
    for old in IMAGES_DIR.glob("slide*.jpg"):
        old.unlink()

    saved = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")

        # Dismiss the cookie banner if present
        try:
            page.click("button:has-text('Accept')", timeout=3000)
        except Exception:
            pass

        page.wait_for_selector("div.slide-item")

        n = 1
        while True:
            if not wait_for_slide(page, n):
                print(f"No slide {n} found, finished downloading.")
                break

            slide = page.locator(f"#slide{n}")
            slide.scroll_into_view_if_needed()  # triggers image lazy loading

            img = slide.locator("img[data-testid='vertical-slide-image']")
            src = None
            for _ in range(10):  # wait up to ~5 s for the large version
                if img.count() > 0:
                    src = img.first.get_attribute("src")
                    if src and "2048" in src:
                        break
                page.wait_for_timeout(500)

            if not src:
                print(f"slide{n}: no src found, skipped")
                n += 1
                continue

            resp = context.request.get(src, headers={"Referer": "https://www.slideshare.net/"})
            if resp.ok:
                (IMAGES_DIR / f"slide{n}.jpg").write_bytes(resp.body())
                saved += 1
                print(f"slide{n}.jpg saved")
            else:
                print(f"slide{n}: HTTP {resp.status}")

            n += 1

        browser.close()

    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Download SlideShare slides as images")
    parser.add_argument("url", help="URL of the SlideShare presentation")
    args = parser.parse_args()

    print(f"Saving to: {IMAGES_DIR}")
    saved = download_slides(args.url)
    print(f"Done. {saved} slides saved.")


if __name__ == "__main__":
    main()