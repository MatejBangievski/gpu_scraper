from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from urllib.parse import urlparse, parse_qs, unquote  # Image extract url
from utils.functions import *  # Custom Functions

import re  # Regex


def load_products_and_btn(browser):
    wait = WebDriverWait(browser, 10)

    div_products = wait.until(
        EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[2]"))
    )

    child_divs = WebDriverWait(div_products, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, "./div"))
    )

    product_grid = child_divs[0]

    pagination = child_divs[1]

    next_page_btn = pagination.find_element(By.TAG_NAME, "div").find_elements(By.TAG_NAME, "button")[-1]

    return product_grid.find_elements(By.XPATH, "./div"), next_page_btn


def get_pagination_last_page(browser):
    wait = WebDriverWait(browser, 10)
    div_products = wait.until(
        EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[2]"))
    )

    child_divs = WebDriverWait(div_products, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, "./div"))
    )

    pagination = child_divs[1]

    pages_div = pagination.find_element(By.TAG_NAME, "div").find_element(By.TAG_NAME, "div")
    buttons = pages_div.find_elements(By.TAG_NAME, "button")

    last_page = int(buttons[-1].text.strip())

    return last_page


def generate_product_url(base_url, description):
    url_part = description.lower()

    url_part = url_part.replace(" ", "-")

    url_part = re.sub(r"[^a-z0-9\-]", "", url_part)  # Mybe delete

    full_url = base_url.rstrip("/") + "/" + url_part
    return full_url


def run():
    conn, existing_gpus = initialize_scraping()

    store_id = add_store(conn, "Setec", "https://setec.mk/")

    browser = initialize_browser('https://setec.mk/category/grafichki-20karti-25?page=1')

    brands = []

    brand_elem = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[1]/div/div/div[3]/div[2]"))
    )

    brand_buttons = WebDriverWait(browser, 10).until(
        EC.presence_of_all_elements_located(
            (By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[1]/div/div/div[3]/div[2]/button")
        )
    )

    for button in brand_buttons:
        text = button.get_attribute("textContent").strip()
        brands.append(text.lower())

    last_page = get_pagination_last_page(browser)

    for _ in range(last_page):
        product_divs, next_page_btn = load_products_and_btn(browser)

        for product in product_divs:
            child_product_divs = product.find_elements(By.XPATH, "./div")

            img_tag = child_product_divs[1].find_element(By.TAG_NAME, "img")
            nextjs_img_url = img_tag.get_attribute("src")

            # Prase nextjs img
            query = urlparse(nextjs_img_url).query
            img_url = unquote(parse_qs(query)["url"][0])

            p_tag = child_product_divs[1].find_element(By.TAG_NAME, "p")
            brand = p_tag.text

            if brand.lower() not in brands:
                continue

            h3_tag = child_product_divs[1].find_element(By.TAG_NAME, "h3")
            product_name = h3_tag.text

            manufacturer = get_manufacturer(product_name)

            model = extract_model(product_name, manufacturer)
            if model is None:
                continue

            vram = extract_vram(product_name)

            url = generate_product_url("https://setec.mk/products", product_name)

            price_tag = child_product_divs[2]
            og_price_tag = price_tag.find_element(By.CLASS_NAME, "text-blackSecondary")
            og_price_text = og_price_tag.find_element(By.TAG_NAME, "span").text.strip()
            og_price = get_price(og_price_text)

            try:
                club_tag = price_tag.find_element(By.CLASS_NAME, "h-7")
                span = club_tag.find_element(By.TAG_NAME, "span")
                club_price_text = span.text.strip()
                club_price = get_price(club_price_text)
            except NoSuchElementException:
                club_price = og_price

            available_tag = child_product_divs[-1].find_element(By.CLASS_NAME, "min-h-6")
            try:
                available_tag.find_element(By.TAG_NAME, "p")
                available = False
            except NoSuchElementException:
                available = True

            add_gpu(conn, product_name, manufacturer, brand, model, vram, store_id, og_price, club_price, available,
                    img_url, url, existing_gpus)

        browser.execute_script("arguments[0].click();",
                               next_page_btn)  # JavaScript - Click the element passed (btn) as the first argument.

    browser.quit()
    conn.commit()
    conn.close()


if __name__ == "__main__":
    run()