# Booking.com Scraper (Selenium)

This project automates Booking.com search, selects check-in/out dates, collects hotel result links, and scrapes details for each hotel into `output.json`.

It uses:
- Selenium WebDriver (Chrome)
- Parallel scraping of hotel pages for speed
- Two modes for images: fast on-page scraping (default) or gallery scraping

## Project structure
- `main.py` — main entry point (search + URL collection + parallel detail scraping)
- `scraping_utils.py` — reusable helpers (calendar, selectors, gallery helpers, etc.)
- `scrape_worker.py` — standalone worker used in parallel threads to scrape each hotel page
- `input.json` — configuration file (currency, city, dates, etc.)
- `output.json` — results (generated)
- `requirements.txt` — Python deps

## Requirements
- Python 3.9+
- Google Chrome installed
- Selenium (Selenium Manager auto-downloads ChromeDriver)

Install deps:
```bash
pip install -r requirements.txt
```

## Configuration (`input.json`)
Example:
```json
{
  "currency": "USD",
  "search": "New York",
  "check_in": "2025-10-15",
  "check_out": "2025-10-21",
  "propertyType": "Hotels",
  "maxitems": 10,
  "fast_images": true
}
```
- `currency`: Booking.com currency code.
- `search`: City or query.
- `check_in` / `check_out`: Dates in `YYYY-MM-DD`.
- `propertyType`: Filter label (e.g., `Hotels`).
- `maxitems`: Max number of hotel URLs to collect from results (default 10).
- `fast_images`:
  - `true` (default): Do not open gallery; quickly collect all `bstatic.com` hotel images present on the page.
  - `false`: Open image gallery and scroll to collect image URLs (slower, but more gallery-accurate).

## Run
From the project directory:
```bash
python main.py
```
Results will be saved to `output.json`.

## Output format (`output.json`)
Each hotel object contains:
- `url`
- `hotel_name`
- `address`
- `image_urls` (list)
- `description`
- `review_score` (string or null)
- `total_reviews` (string or null)
- `check_in` (e.g., "From 3:00 PM")
- `check_out` (e.g., "Until 12:00 PM")

## Notes
- The script uses parallel threads to scrape hotel details. Default worker count is 4; increase in `main.py` if your machine can handle more Chrome instances.
- The calendar/date selection interacts with Booking.com's datepicker and navigates months until the target date appears.
- Cookie consent is auto-dismissed when detected.

## Tips for performance
- Keep `fast_images: true` for quickest image collection.
- Reduce `maxitems` during development.
- Consider closing other Chrome instances while running.

## Troubleshooting
- Chrome/Driver mismatch: Selenium 4.6+ bundles Selenium Manager which resolves drivers automatically. Ensure Chrome is installed and up to date.
- Elements not found/timeouts: UI may vary by locale. If selectors drift, update CSS/XPath in `scraping_utils.py` accordingly.
- Slow runs:
  - Ensure `fast_images: true`.
  - Increase parallelism: change `ThreadPoolExecutor(max_workers=4)` in `main.py`.


