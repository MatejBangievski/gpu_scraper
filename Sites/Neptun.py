from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.functions import *  # Custom Functions
from utils.constants import UNSUPPORTED_BRANDS


def get_brand(desc):
    return desc.strip().split()[1]


def run():
    conn, existing_gpus = initialize_scraping()

    store_id = add_store(conn, "Neptun", "https://www.neptun.mk/")

    browser = initialize_browser('https://www.neptun.mk/Graficki_karticki.nspx?items=100&page=1')

    div_products = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.col-lg-9.col-md-9.col-sm-8.col-fix-main"))
    )

    child_divs = div_products.find_elements(By.XPATH, './div[@ng-class]')

    for product in child_divs:
        product = product.find_element(By.CSS_SELECTOR, "div.white-box")

        product_name = product.find_element(By.TAG_NAME, "h2").text.strip()

        img_url = product.find_element(By.TAG_NAME, "img").get_attribute("src")

        manufacturer = get_manufacturer(product_name)

        model = extract_model(product_name, manufacturer)
        if model is None:
            continue

        vram = extract_vram(product_name)

        url_tag = product.find_element(By.TAG_NAME, "a")
        url = url_tag.get_attribute("href")

        prices_tag = product.find_elements(By.CSS_SELECTOR, "span.product-price__amount--value.ng-binding")
        if len(prices_tag) == 3:
            club_price = prices_tag[0].text.strip()
            club_price = get_price(club_price)

            og_price = prices_tag[1].text.strip()
            og_price = get_price(og_price)
        else:
            og_price = club_price = get_price(prices_tag[0].text.strip())

        # In my testing, every listed item is available.
        available = True

        brand = get_brand(product_name)
        if brand in UNSUPPORTED_BRANDS:
            continue

        add_gpu(conn, product_name, manufacturer, brand, model, vram, store_id, og_price, club_price, available,
                img_url, url, existing_gpus)

    browser.quit()
    conn.commit()
    conn.close()


if __name__ == "__main__":
    run()
