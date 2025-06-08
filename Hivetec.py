import time

from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from functions import *  # Custom Functions

import re

def load_products_and_btn():
    WebDriverWait(browser, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, "/html/body/div[2]/div/div/div/div/div/section[2]/div/div[2]/div/div[2]/div")
        )
    )

    time.sleep(10) #TODO: CHANGE WITH BETTER IMPLEMENTATION

    page_div = browser.find_element(By.XPATH,
                                  "/html/body/div[2]/div/div/div/div/div/section[2]/div/div[2]/div/div[2]/div")

    child_divs = page_div.find_elements(By.XPATH, "./div")

    # Grid of products
    products_div = child_divs[1]

    # Nav bar of pages
    pages_div = child_divs[2].find_elements(By.TAG_NAME, "a")

    # Get next page arrow
    next_page_btn = pages_div[-1]

    products = products_div.find_elements(By.XPATH, "./div")

    # Return products and btn
    return products, next_page_btn

def get_pagination_last_page():
    pages_div = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div/div/div/div/div/section[2]/div/div[2]/div/div[2]/div/div[3]/nav/ul"))
    )

    pages = pages_div.find_elements(By.TAG_NAME, "a")

    last_page = int(pages[-2].text.strip()) # Second to last

    return last_page

def get_price(text):
    match = re.search(r'([\d,]+\.\d+)', text)
    if match:
        price_str = match.group(1)  # e.g. '8,999.00'
        price_float = float(price_str.replace(',', ''))  # 8999.00
        return int(price_float)  # 8999
    return 0

if __name__ == "__main__":
    conn, existing_gpus = initialize_scraping()

    store_id = add_store(conn, "Hivetec", "https://hivetec.mk/en/")

    browser = initialize_browser('https://hivetec.mk/en/product-category/grafichki-karti/?per_page=24')

    last_page = get_pagination_last_page()

    # Iterate through each direct child div
    for _ in range(last_page):
        product_divs, next_page_btn = load_products_and_btn()

        for product in product_divs:
            # Image
            img_url = product.find_element(By.TAG_NAME, "img").get_attribute("src")

            # Product name
            title_tag = product.find_element(By.CLASS_NAME, "wd-entities-title").find_element(By.TAG_NAME, "a")
            product_name = title_tag.text

            # Manufacturer
            manufacturer = get_manufacturer(product_name)

            # Model - if can't scrape the model don't add
            model = extract_model(product_name, manufacturer)
            if model is None:
                continue

            # Vram
            vram = extract_vram(product_name)

            # Gpu url
            url = product.find_element(By.CLASS_NAME, "product-image-link").get_attribute("href")

            # Price
            price_tag = browser.find_element(By.CSS_SELECTOR, "span.price").find_elements(By.TAG_NAME, "bdi")
            og_price_text = price_tag[0].text.strip()
            og_price = get_price(og_price_text)

            # Club price
            club_price_text = price_tag[1].text.strip()
            club_price = get_price(club_price_text)

            if club_price == 0:
                club_price = og_price

            # Available
            stock_paragraph = product.find_element(By.CSS_SELECTOR,
                                                   "p.wd-product-stock")
            if stock_paragraph.text == 'Производот е достапен' or stock_paragraph.text == 'In stock':
                available = True
            else:
                available = False

            # Brand

            # Hover over the element
            actions = ActionChains(browser)
            actions.move_to_element(product).perform()

            brand = product.find_element(By.TAG_NAME, "tbody").find_element(By.CSS_SELECTOR, "span.wd-attr-term").find_element(By.TAG_NAME, "p").text.strip()

            add_gpu(conn, product_name, manufacturer, brand, model, vram, store_id, og_price, club_price, available, img_url, url, existing_gpus)

        browser.execute_script("arguments[0].click();",
                               next_page_btn)  # JavaScript - Click the element passed (btn) as the first argument.

    conn.commit()
    conn.close()