from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from urllib.parse import urlparse, parse_qs, unquote  # Image extract url
from functions import *  # Custom Functions

import re  # Regex

def load_products_and_btn():
    wait = WebDriverWait(browser, 10)

    # Wait for product grid
    div_products = wait.until(
        EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[2]"))
    )

    # Wait for direct child divs inside product grid
    child_divs = WebDriverWait(div_products, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, "./div"))
    )

    # Product grid
    product_grid = child_divs[0]

    # Pagination
    pagination = child_divs[1]

    next_page_btn = pagination.find_element(By.TAG_NAME, "div").find_elements(By.TAG_NAME, "button")[-1]

    # Return products and btn
    return product_grid.find_elements(By.XPATH, "./div"), next_page_btn


def get_pagination_last_page():
    wait = WebDriverWait(browser, 10)
    div_products = wait.until(
        EC.presence_of_element_located((By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[2]"))
    )

    # Child divs - 0 = grid, 1 = pagination 0 - with wait
    child_divs = WebDriverWait(div_products, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, "./div"))
    )

    # Pagination
    pagination = child_divs[1]

    # Get number of pages
    pages_div = pagination.find_element(By.TAG_NAME, "div").find_element(By.TAG_NAME, "div")
    buttons = pages_div.find_elements(By.TAG_NAME, "button")

    last_page = int(buttons[-1].text.strip())

    return last_page


def generate_product_url(base_url, description):
    # Lowercase
    url_part = description.lower()

    # Replace spaces with hyphens
    url_part = url_part.replace(" ", "-")

    # Optionally, remove unwanted characters (keep alphanum, dash)
    url_part = re.sub(r"[^a-z0-9\-]", "", url_part)  # Mybe delete

    full_url = base_url.rstrip("/") + "/" + url_part
    return full_url


if __name__ == "__main__":
    conn, existing_gpus = initialize_scraping()

    store_id = add_store(conn, "Setec", "https://setec.mk/")

    # Setec - grafichki kartichki
    browser = initialize_browser('https://setec.mk/category/grafichki-20karti-25?page=1')

    # BRANDS
    brands = []

    # Find all GPU Manufacturers - XPATH
    # Wait until the container div is present
    brand_elem = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[1]/div/div/div[3]/div[2]"))
    )

    # Then wait for buttons inside that container
    brand_buttons = WebDriverWait(browser, 10).until(
        EC.presence_of_all_elements_located(
            (By.XPATH, "/html/body/div[2]/div[2]/div/div[2]/div/div[2]/div[1]/div/div/div[3]/div[2]/button")
        )
    )

    for button in brand_buttons:
        text = button.get_attribute("textContent").strip()
        brands.append(text.lower())

    last_page = get_pagination_last_page()

    # Iterate through each direct child div
    for _ in range(last_page):
        product_divs, next_page_btn = load_products_and_btn()

        for product in product_divs:
            child_product_divs = product.find_elements(By.XPATH, "./div")

            # Image
            img_tag = child_product_divs[1].find_element(By.TAG_NAME, "img")
            nextjs_img_url = img_tag.get_attribute("src")

            # Prase nextjs img
            query = urlparse(nextjs_img_url).query
            img_url = unquote(parse_qs(query)["url"][0])

            # Brand
            p_tag = child_product_divs[1].find_element(By.TAG_NAME, "p")
            brand = p_tag.text

            # If not a gpu - continue
            if brand.lower() not in brands:
                continue

            # Product name
            h3_tag = child_product_divs[1].find_element(By.TAG_NAME, "h3")
            product_name = h3_tag.text

            # Manufacturer
            manufacturer = get_manufacturer(product_name)

            # Model - if can't scrape the model don't add
            model = extract_model(product_name, manufacturer)
            if model is None:
                continue

            # Vram
            vram = extract_vram(product_name)

            # Gpu url
            url = generate_product_url("https://setec.mk/products", product_name)

            # Price
            price_tag = child_product_divs[2]
            og_price_tag = price_tag.find_element(By.CLASS_NAME, "text-blackSecondary")
            og_price_text = og_price_tag.find_element(By.TAG_NAME, "span").text.strip()
            og_price = get_price(og_price_text)

            # Club price
            try:  # If there's no span - there isn't a club price
                club_tag = price_tag.find_element(By.CLASS_NAME, "h-7")
                span = club_tag.find_element(By.TAG_NAME, "span")
                club_price_text = span.text.strip()
                club_price = get_price(club_price_text)
            except NoSuchElementException:
                club_price = og_price

            # Available
            available_tag = child_product_divs[-1].find_element(By.CLASS_NAME, "min-h-6")
            try:  # If P tag exists = not in stock
                available_tag.find_element(By.TAG_NAME, "p")
                available = False
            except NoSuchElementException:
                available = True

            add_gpu(conn, product_name, manufacturer, brand, model, vram, store_id, og_price, club_price, available,
                    img_url, url, existing_gpus)

        browser.execute_script("arguments[0].click();",
                               next_page_btn)  # JavaScript - Click the element passed (btn) as the first argument.

    conn.commit()
    conn.close()
