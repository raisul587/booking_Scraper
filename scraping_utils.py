from typing import List, Optional
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ---------- Calendar helpers ----------

def open_calendar(driver, wait: WebDriverWait) -> bool:
    selectors = [
        "button[data-testid='searchbox-dates-container']",
        "button[aria-controls='calendar-searchboxdatepicker']",
    ]
    for sel in selectors:
        try:
            btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.6)
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='searchbox-datepicker-calendar']"))
            )
            return True
        except TimeoutException:
            continue
    # Fallback: click the start date display's parent button
    try:
        display = driver.find_element(By.CSS_SELECTOR, "[data-testid='date-display-field-start']")
        parent_btn = driver.execute_script("return arguments[0].closest('button')", display)
        if parent_btn:
            driver.execute_script("arguments[0].click();", parent_btn)
            time.sleep(0.6)
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='searchbox-datepicker-calendar']"))
            )
            return True
    except Exception:
        pass
    return False


def select_date(driver, wait: WebDriverWait, date_str: str, max_hops: int = 24) -> bool:
    for _ in range(max_hops):
        try:
            el = driver.find_element(By.CSS_SELECTOR, f"span[data-date='{date_str}']")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            driver.execute_script("arguments[0].click();", el)
            time.sleep(0.4)
            return True
        except NoSuchElementException:
            try:
                next_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Next month"]'))
                )
                next_btn.click()
                time.sleep(0.3)
            except TimeoutException:
                alt_next = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Next']")
                if alt_next:
                    driver.execute_script("arguments[0].click();", alt_next[0])
                    time.sleep(0.3)
                else:
                    break
    return False

# ---------- Generic scraping helpers ----------

def first_text(driver, selectors: List[str]) -> Optional[str]:
    for sel in selectors:
        try:
            el = WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
            txt = el.text.strip()
            if txt:
                return txt
        except TimeoutException:
            continue
    return None


def find_many_src(driver, selectors: List[str], limit: int = 15) -> List[str]:
    urls: List[str] = []
    seen = set()
    for sel in selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for e in els:
                src = e.get_attribute("src") or e.get_attribute("data-src")
                if src and src not in seen and "bstatic.com" in src:
                    seen.add(src)
                    urls.append(src)
                    if len(urls) >= limit:
                        return urls
        except Exception:
            pass
    return urls


def get_address(driver) -> Optional[str]:
    raw = first_text(
        driver,
        [
            "[data-testid='address']",
            "span[data-node_tt_id='address']",
            "[data-node_tt_id='address']",
        ],
    )
    if raw:
        return raw.split("\n", 1)[0].strip()
    try:
        el = driver.find_element(
            By.CSS_SELECTOR, "button.de576f5064 div.b99b6ef58f.cb4b7a25d9.b06461926f"
        )
        return el.text.split("\n", 1)[0].strip()
    except Exception:
        return None


def extract_time_for(driver, label_text: str) -> Optional[str]:
    try:
        val_el = driver.find_element(
            By.XPATH,
            (
                f"//div[contains(@class,'b0400e5749')][.//div[contains(@class,'e7addce19e') and normalize-space(text())='{label_text}']]"
                "//div[contains(@class,'c92998be48')]//div[contains(@class,'b99b6ef58f')][1]"
            ),
        )
        return val_el.text.strip()
    except Exception:
        return None

# ---------- Gallery helpers ----------

def open_gallery(driver) -> bool:
    try:
        selectors = [
            "img.f6c12c77eb.c0e44985a8.c09abd8a52.ca3dad4476",
            "[data-testid='image-gallery-scroll-container'] img",
            "figure img",
        ]
        thumbs = []
        for sel in selectors:
            thumbs.extend(driver.find_elements(By.CSS_SELECTOR, sel))
        valid = []
        for t in thumbs:
            try:
                src = t.get_attribute("src") or t.get_attribute("data-src") or ""
                src_l = src.lower()
                if (
                    "bstatic.com" in src_l
                    and "/images/hotel/" in src_l
                    and "images-flags" not in src_l
                    and "design-assets" not in src_l
                    and "transparent" not in src_l
                ):
                    valid.append(t)
            except Exception:
                continue
        target = valid[1] if len(valid) >= 2 else (valid[0] if valid else None)
        if target is None:
            return False
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        driver.execute_script("arguments[0].click();", target)
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button[data-testid^='gallery-grid-photo-action-']")
            )
        )
        return True
    except TimeoutException:
        try:
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button[data-testid^='gallery-grid-photo-action-']")
                )
            )
            return True
        except Exception:
            return False
    except Exception:
        return False


def collect_gallery_images(driver, max_scrolls: int = 20) -> List[str]:
    urls = set()
    try:
        grid_container = None
        try:
            grid_container = driver.find_element(By.CSS_SELECTOR, "div.ff6e679a8f, div.f8e0b81a32")
        except Exception:
            grid_container = None

        def current_buttons():
            return driver.find_elements(By.CSS_SELECTOR, "button[data-testid^='gallery-grid-photo-action-']")

        last_count = -1
        stagnate = 0
        for _ in range(max_scrolls):
            btns = current_buttons()
            for b in btns:
                try:
                    img = b.find_element(By.CSS_SELECTOR, "img")
                    src = img.get_attribute("src") or img.get_attribute("data-src")
                    if src and "bstatic.com" in src:
                        urls.add(src)
                except Exception:
                    continue
            if len(btns) == last_count:
                stagnate += 1
            else:
                stagnate = 0
            last_count = len(btns)
            if stagnate >= 3:
                break
            if grid_container:
                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollTop + arguments[0].clientHeight;",
                    grid_container,
                )
            else:
                driver.execute_script("window.scrollBy(0, Math.min(800, window.innerHeight));")
            time.sleep(0.4)
        return list(urls)
    except Exception:
        return list(urls)


def close_gallery(driver) -> None:
    try:
        close_btn = driver.find_elements(
            By.CSS_SELECTOR, "button[aria-label*='Close'], button[aria-label*='close']"
        )
        if close_btn:
            driver.execute_script("arguments[0].click();", close_btn[0])
            return
    except Exception:
        pass
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ESCAPE)
    except Exception:
        pass
