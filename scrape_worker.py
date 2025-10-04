import json
import re
import time
from typing import Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from scraping_utils import (
    first_text as su_first_text,
    get_address as su_get_address,
    extract_time_for as su_extract_time_for,
    open_gallery as su_open_gallery,
    collect_gallery_images as su_collect_gallery_images,
    close_gallery as su_close_gallery,
    find_many_src as su_find_many_src,
)


def scrape_hotel(href: str, fast_images: bool = True) -> Dict:
    options = Options()
    # Keep the same behavior as main browser (do not change to headless to avoid behavioral diffs)
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    try:
        driver.get(href)
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Hotel name
        name = su_first_text(
            driver,
            [
                "h2.pp-header__title",
                "h2.ddb12f4f86.pp-header__title",
                "[data-testid='hp-hotel-name'] h2",
                "header h2",
            ],
        )

        # Address
        address = su_get_address(driver)

        # Description
        description = su_first_text(
            driver,
            [
                "p[data-testid='property-description']",
                "[data-testid='property-description']",
            ],
        )

        # Review score and total reviews
        review_score = None
        total_reviews = None
        try:
            scorecard = driver.find_elements(By.CSS_SELECTOR, "#js--hp-gallery-scorecard")
            if scorecard:
                review_score = scorecard[0].get_attribute("data-review-score") or None
            comp = driver.find_elements(
                By.CSS_SELECTOR, "[data-testid='review-score-right-component']"
            )
            if comp:
                text_blob = comp[0].text
                m_score = re.search(r"(\\d+(?:\\.\\d+)?)", text_blob)
                if not review_score and m_score:
                    review_score = m_score.group(1)
                m_reviews = re.search(r"([\\d,]+)\\s+reviews", text_blob, re.IGNORECASE)
                if m_reviews:
                    total_reviews = m_reviews.group(1)
            if not total_reviews:
                any_reviews = driver.find_elements(
                    By.XPATH,
                    "//*[contains(translate(text(),'REVIEWS','reviews'),'reviews')]",
                )
                for el in any_reviews:
                    m = re.search(r"([\\d,]+)\\s+reviews", el.text, re.IGNORECASE)
                    if m:
                        total_reviews = m.group(1)
                        break
        except Exception:
            pass

        # Check-in/out
        check_in_time = su_extract_time_for(driver, "Check-in")
        check_out_time = su_extract_time_for(driver, "Check-out")

        # Images
        if fast_images:
            # Fast path: do minimal scrolling and collect all bstatic image URLs from page without opening gallery
            try:
                # Trigger lazy-loads briefly
                for _ in range(2):
                    driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
                    time.sleep(0.3)
                    driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(0.2)
                urls = driver.execute_script(
                    """
                    const out = new Set();
                    const imgs = Array.from(document.querySelectorAll('img'));
                    for (const i of imgs) {
                      const s = i.getAttribute('src') || i.getAttribute('data-src');
                      if (s && s.includes('bstatic.com')) out.add(s);
                    }
                    // also pick picture > source
                    const sources = Array.from(document.querySelectorAll('picture source'));
                    for (const s of sources) {
                      const srcset = s.getAttribute('srcset') || '';
                      srcset.split(',').forEach(chunk => {
                        const u = chunk.trim().split(' ')[0];
                        if (u && u.includes('bstatic.com')) out.add(u);
                      });
                    }
                    return Array.from(out);
                    """
                )
                image_urls = [u for u in urls if '/images/hotel/' in u]
            except Exception:
                # Fallback to previous inline scrape in case JS fails
                image_urls = su_find_many_src(
                    driver,
                    [
                        "img[src*='bstatic.com']",
                        "img[data-src*='bstatic.com']",
                        "figure img",
                    ],
                )
        else:
            # Original behavior: open gallery and collect
            gallery_urls = []
            if su_open_gallery(driver):
                gallery_urls = su_collect_gallery_images(driver)
                su_close_gallery(driver)
            if gallery_urls:
                image_urls = gallery_urls
            else:
                image_urls = su_find_many_src(
                    driver,
                    [
                        "img[src*='bstatic.com']",
                        "img[data-src*='bstatic.com']",
                        "figure img",
                    ],
                )

        return {
            "url": href,
            "hotel_name": name,
            "address": address,
            "image_urls": image_urls,
            "description": description,
            "review_score": review_score,
            "total_reviews": total_reviews,
            "check_in": check_in_time,
            "check_out": check_out_time,
        }
    finally:
        try:
            driver.quit()
        except Exception:
            pass
