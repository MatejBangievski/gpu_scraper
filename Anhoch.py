from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from functions import *  # Custom Functions
from constants import UNSUPPORTED_BRANDS

import math, time

def load_products_and_btn():
    WebDriverWait(browser, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, "search-result"))
    )

    time.sleep(10) #TODO: CHANGE WITH BETTER IMPLEMENTATION

    div_products = WebDriverWait(browser, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, "grid-view-products"))
    )

    child_divs = div_products.find_elements(By.XPATH, "./div")

    pages_div = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.pagination"))
    )

    buttons = pages_div.find_elements(By.CSS_SELECTOR, "button.page-link")
    next_page_btn = buttons[-1]

    return child_divs, next_page_btn


def get_pagination_last_page():
    pages_div = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "showing-results"))
    )

    result_text = pages_div.text.strip()
    starting_page, products_per_page, total_products = list(map(int, re.findall(r'\d+', result_text)))

    num_pages = math.ceil(total_products / products_per_page)

    return num_pages

def get_brand(desc):
    return product_name.strip().split()[0]


if __name__ == "__main__":
    conn, existing_gpus = initialize_scraping()

    store_id = add_store(conn, "Anhoch", "https://www.anhoch.com/")

    #browser = initialize_browser('https://www.anhoch.com/categories/grafichki-karti/products?brand=&attribute=&toPrice=324980&inStockOnly=2&sort=latest&perPage=50&page=1')
    browser = initialize_browser('https://www.anhoch.com/categories/grafichki-karti/products?inStockOnly=2&sort=latest&perPage=50&page=1')

    last_page = get_pagination_last_page()

    for _ in range(last_page):
        child_divs, next_page_btn = load_products_and_btn()
        for product in child_divs:
            product = product.find_element(By.TAG_NAME, "div")

            img_url = product.find_element(By.TAG_NAME, "img").get_attribute("src")

            product_name = product.get_attribute("title")

            brand = get_brand(product_name)

            manufacturer = get_manufacturer(product_name)

            model = extract_model(product_name, manufacturer)
            if model is None:
                continue

            vram = extract_vram(product_name)

            url_tag = product.find_element(By.CSS_SELECTOR, "a.product-image")
            url = url_tag.get_attribute("href")

            try:
                price_element = product.find_element(By.CLASS_NAME, "product-price")

                previous_element = price_element.find_element(By.CLASS_NAME, "previous-price")
                club_price_text = price_element.get_attribute("innerText").strip()
                original_text = previous_element.get_attribute("innerText").strip()

                club_price = get_price(club_price_text.replace(original_text, "").strip())
                og_price = get_price(original_text)

            except:
                og_price = get_price(price_element.get_attribute("innerText").strip())
                club_price = 0

            if club_price == 0:
                club_price = og_price

            try:
                availablility_tag = product.find_element(By.CSS_SELECTOR, "ul.list-inline.product-badge").find_element(By.TAG_NAME, "li")
                availability_text = availablility_tag.text.strip()
                if availability_text == 'Нема на залиха':
                    available = False
            except:
                available = True

            add_gpu(conn, product_name, manufacturer, brand, model, vram, store_id, og_price, club_price, available, img_url, url, existing_gpus)

        browser.execute_script("arguments[0].click();", next_page_btn)

    browser.quit()
    conn.commit()
    conn.close()
