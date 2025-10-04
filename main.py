import json
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from scraping_utils import (
    open_calendar as su_open_calendar,
    select_date as su_select_date,
    first_text as su_first_text,
    find_many_src as su_find_many_src,
    get_address as su_get_address,
    extract_time_for as su_extract_time_for,
    open_gallery as su_open_gallery,
    collect_gallery_images as su_collect_gallery_images,
    close_gallery as su_close_gallery,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
from scrape_worker import scrape_hotel

# ---------- Step 1: Load input.json ----------
with open("input.json", "r") as f:
    data = json.load(f)

currency = data["currency"]
search_text = data["search"]
check_in_date = data["check_in"]
check_out_date = data["check_out"]
property_type = data["propertyType"]
max_items = data.get("maxitems", 10)  # default to 10 if missing
fast_images = data.get("fast_images", True)  # Option A: default to fast image scraping

# ---------- Step 2: Setup Selenium ----------
options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 25)

# ---------- Step 3: Go to Booking.com ----------
url = f"https://www.booking.com/?selected_currency={currency}"
driver.get(url)

# Optional: dismiss cookie consent if present (non-fatal if not found)
try:
    consent_btn = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id^='onetrust-accept-btn-handler'], button[aria-label*='Accept']"))
    )
    consent_btn.click()
    time.sleep(0.5)
except TimeoutException:
    pass

# ---------- Step 4: Click on search input ----------
search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='ss']")))
search_box.click()
time.sleep(1)

# ---------- Step 5: Type the search text (NO ENTER) ----------
search_box.clear()
search_box.send_keys(search_text)
time.sleep(1)

# ---------- Step 6: Open the calendar (robust) ----------
if not su_open_calendar(driver, wait):
    raise RuntimeError("Could not open calendar")
time.sleep(0.8)

# ---------- Step 7: Select check-in ----------
if not su_select_date(driver, wait, check_in_date):
    raise RuntimeError(f"Could not select check-in date: {check_in_date}")

# ---------- Step 8: Select check-out ----------
if not su_select_date(driver, wait, check_out_date):
    raise RuntimeError(f"Could not select check-out date: {check_out_date}")
time.sleep(0.8)



# ---------- Step 10: Click the search button ----------
search_button = wait.until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='searchbox-submit-button'], button[type='submit']"))
)
search_button.click()

property_filter = WebDriverWait(driver, 15).until(
    EC.element_to_be_clickable(
        (By.XPATH, f"//div[@data-testid='filters-group-label-content' and text()='{property_type}']/ancestor::label")
    )
)

# click using JavaScript to avoid potential overlay issues
driver.execute_script("arguments[0].click();", property_filter)

# Wait until at least one search result appears
WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='property-card']"))
)

# Now wait for the clickable link inside the property card
hotel_link = WebDriverWait(driver, 20).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "div[data-testid='property-card'] h3 > a"))
)

# Scroll into view and click
driver.execute_script("arguments[0].scrollIntoView(true);", hotel_link)
driver.execute_script("arguments[0].click();", hotel_link)



# max_items = data.get("maxitems", 10)  # fallback to 10 if not present

main_handle = driver.current_window_handle

# Wait for search results to appear
WebDriverWait(driver, 20).until(
    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='property-card'] h3 > a"))
)

# STEP 1 — Collect all unique hrefs first
hrefs = []
while len(hrefs) < max_items:
    links = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='property-card'] h3 > a")
    for link in links:
        href = link.get_attribute("href")
        if href and href not in hrefs:
            hrefs.append(href)
        if len(hrefs) >= max_items:
            break

    if len(hrefs) < max_items:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

print(f"✅ Total collected: {len(hrefs)} URLs")

# STEP 2 — Parallel scraping of hotel details in separate processes
results = []
with ThreadPoolExecutor(max_workers=4) as executor:
    # Submit all tasks
    future_to_href = {executor.submit(scrape_hotel, href, fast_images): href for href in hrefs}
    for idx, future in enumerate(as_completed(future_to_href), start=1):
        href = future_to_href[future]
        try:
            data = future.result()
            results.append(data)
            print(f"✅ Scraped hotel #{idx}: {data.get('hotel_name') or href}")
        except Exception as e:
            print(f"ERROR scraping {href}: {e}")
# Write results to output.json
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# # ---------- Optional: wait to see results ----------
time.sleep(5)
driver.quit()
