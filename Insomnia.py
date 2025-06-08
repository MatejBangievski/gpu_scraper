from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from functions import *  # Custom Functions
from constants import UNSUPPORTED_BRANDS


if __name__ == "__main__":
    conn, existing_gpus = initialize_scraping()

    store_id = add_store(conn, "Insomnia", "https://insomnia.mk/")

    browser = initialize_browser('https://insomnia.mk/catalog/komponeneti/grafichki-karti/page-all')

    div_products = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.ID, "fn_products_content"))
    )

    child_divs = div_products.find_elements(By.XPATH, "./div")

    for product in child_divs:

        # Product name
        product_name = product.find_element(By.NAME, "fp_product_name")
        product_name = product_name.get_attribute("value")

        # Manufacturer
        manufacturer = get_manufacturer(product_name)

        # Model - if can't scrape the model don't add
        model = extract_model(product_name, manufacturer)
        if model is None:
            continue

        # Vram
        vram = extract_vram(product_name)

        # Gpu url
        url_tag = first_a_tag = product.find_element(By.TAG_NAME, "a")
        url = url_tag.get_attribute("href")

        # Price
        og_price = product.find_element(By.CLASS_NAME, "fn_price").text.strip()
        og_price = get_price(og_price)

        # Club price
        club_price = product.find_element(By.CLASS_NAME, "fn_old_price").text.strip()
        club_price = get_price(club_price)
        if club_price == 0:
            club_price = og_price

        original_window = browser.current_window_handle

        browser.execute_script("window.open(arguments[0]);", url)

        browser.switch_to.window(browser.window_handles[-1])

        # Extract brand
        try:
            brand = browser.find_element(By.CSS_SELECTOR, "span[itemprop='brand']").text.strip()
        except:
            brand = None

        # Extract availability
        try:
            availability_text = browser.find_element(By.CLASS_NAME, "available__in_stock").text.strip()
            available = availability_text == "Да"
        except:
            available = False

        try:
            img_element = browser.find_element(By.CSS_SELECTOR, "img[itemprop='image']")
            img_url = img_element.get_attribute("src").strip()
        except:
            img_url = None

        # Close the product tab when done
        browser.close()

        browser.switch_to.window(original_window)

        # Check brand

        if brand in UNSUPPORTED_BRANDS:
            continue

        add_gpu(conn, product_name, manufacturer, brand, model, vram, store_id, og_price, club_price, available, img_url, url, existing_gpus)

    conn.commit()
    conn.close()
