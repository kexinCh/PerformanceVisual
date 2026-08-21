from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "http://localhost:8501"
OUT = Path(__file__).parent / "dashboard_screenshots"
OUT.mkdir(exist_ok=True)


def main() -> None:
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True, executable_path=p.firefox.executable_path)
        page = browser.new_page(viewport={"width": 1366, "height": 768}, device_scale_factor=1)
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=45000)
        page.get_by_text("Golf Mental-Performance Dashboard").wait_for(timeout=45000)
        page.wait_for_timeout(3500)
        page.screenshot(path=OUT / "team_overview.png", full_page=False)

        page.get_by_text("Player Explorer").click()
        page.wait_for_timeout(3500)
        page.screenshot(path=OUT / "player_example.png", full_page=False)
        browser.close()

    print(f"Wrote dashboard screenshots to {OUT}")


if __name__ == "__main__":
    main()
