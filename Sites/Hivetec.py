import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from utils.functions import *  # Custom Functions

import re


def load_products_and_btn(browser):
    WebDriverWait(browser, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, "/html/body/div[2]/div/div/div/div/div/section[2]/div/div[2]/div/div[2]/div")
        )
    )

    time.sleep(10)  # TODO: CHANGE WITH BETTER IMPLEMENTATION

    page_div = browser.find_element(By.XPATH,
                                    "/html/body/div[2]/div/div/div/div/div/section[2]/div/div[2]/div/div[2]/div")

    child_divs = page_div.find_elements(By.XPATH, "./div")

    products_div = child_divs[1]

    pages_div = child_divs[2].find_elements(By.TAG_NAME, "a")

    next_page_btn = pages_div[-1]

    products = products_div.find_elements(By.XPATH, "./div")

    return products, next_page_btn


def get_pagination_last_page(browser):
    pages_div = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "/html/body/div[2]/div/div/div/div/div/section[2]/div/div[2]/div/div[2]/div/div[3]/nav/ul"))
    )

    pages = pages_div.find_elements(By.TAG_NAME, "a")

    last_page = int(pages[-2].text.strip())  # Second to last

    return last_page


def get_price(text):
    match = re.search(r'([\d,]+\.\d+)', text)
    if match:
        price_str = match.group(1)
        price_float = float(price_str.replace(',', ''))  # 8999.00
        return int(price_float)
    return 0


def run():
    conn, existing_gpus = initialize_scraping()

    store_id = add_store(conn, "Hivetec", "https://hivetec.mk/en/")

    browser = initialize_browser('https://hivetec.mk/en/product-category/grafichki-karti/?per_page=24')

    last_page = get_pagination_last_page(browser)

    for _ in range(last_page):
        product_divs, next_page_btn = load_products_and_btn(browser)

        for product in product_divs:
            img_url = product.find_element(By.TAG_NAME, "img").get_attribute("src")

            title_tag = product.find_element(By.CLASS_NAME, "wd-entities-title").find_element(By.TAG_NAME, "a")
            product_name = title_tag.text

            manufacturer = get_manufacturer(product_name)

            model = extract_model(product_name, manufacturer)
            if model is None:
                continue

            vram = extract_vram(product_name)

            url = product.find_element(By.CLASS_NAME, "product-image-link").get_attribute("href")

            price_tag = browser.find_element(By.CSS_SELECTOR, "span.price").find_elements(By.TAG_NAME, "bdi")
            og_price_text = price_tag[0].text.strip()
            og_price = get_price(og_price_text)

            club_price_text = price_tag[1].text.strip()
            club_price = get_price(club_price_text)

            if club_price == 0:
                club_price = og_price

            stock_paragraph = product.find_element(By.CSS_SELECTOR,
                                                   "p.wd-product-stock")
            if stock_paragraph.text == 'Производот е достапен' or stock_paragraph.text == 'In stock':
                available = True
            else:
                available = False

            # Hover over the element
            actions = ActionChains(browser)
            actions.move_to_element(product).perform()

            brand = product.find_element(By.TAG_NAME, "tbody").find_element(By.CSS_SELECTOR,
                                                                            "span.wd-attr-term").find_element(
                By.TAG_NAME, "p").text.strip()

            add_gpu(conn, product_name, manufacturer, brand, model, vram, store_id, og_price, club_price, available,
                    img_url, url, existing_gpus)

        browser.execute_script("arguments[0].click();",
                               next_page_btn)  # JavaScript - Click the element passed (btn) as the first argument.

    browser.quit()
    conn.commit()
    conn.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"An error occurred: {e}")
