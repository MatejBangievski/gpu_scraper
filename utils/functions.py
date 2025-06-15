from selenium import webdriver
from utils.constants import NVIDIA_KEYWORDS

import re  # Regex
import psycopg2  # SQL


def get_db_connection():
    """
    Input: None
    Output: psycopg2 database connection object

    Establishes and returns a connection to the PostgreSQL database.
    """
    return psycopg2.connect(
        dbname="gpu_products_db",
        user="postgres",
        password="admin",
        host="localhost",
        port="5432"
    )


def load_existing_gpus(conn):
    """
    Input: Database connection
    Output: Set of tuples (manufacturer, brand, model, vram)

    Loads existing GPU records from the database to avoid duplicate entries.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT g.manufacturer, g.brand, g.model, g.vram
            FROM gpu g
            JOIN component c ON g.component_id = c.id
        """)
        return set((m, b, mo, v) for m, b, mo, v in cur.fetchall())


def initialize_scraping():
    """
    Input: None
    Output: Tuple (database connection, set of existing GPUs)

    Initializes the scraping process by connecting to the database and loading existing GPUs.
    """
    conn = get_db_connection()
    existing_gpus = load_existing_gpus(conn)
    return conn, existing_gpus


def initialize_browser(start_url):
    """
    Input: start_url (str)
    Output: Selenium Chrome WebDriver instance

    Initializes a headless Selenium Chrome browser and navigates to the start URL.
    """

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    browser = webdriver.Chrome(options=options)
    browser.get(start_url)

    return browser


def add_store(conn, name, url):
    """
    Input: Database connection, store name (str), store URL (str)
    Output: Store ID (int)

    Inserts a store into the database or retrieves the ID if it already exists.
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO store (name, website_url)
            VALUES (%s, %s)
            ON CONFLICT (name) DO NOTHING
            RETURNING id;
        """, (name, url))
        res = cur.fetchone()
        if res:
            return res[0]
        cur.execute("SELECT id FROM store WHERE name=%s;", (name,))
        return cur.fetchone()[0]


def add_gpu(conn, description, manufacturer, brand, model,
            vram, store_id, price, club_price, available, img_url, url, existing_gpus):
    """
    Input: Database connection, product details (description, manufacturer, brand, model, vram, etc.),
           store ID, prices, availability, image URL, product URL, and existing GPU set
    Output: None

    Adds a new GPU and its listing to the database if it doesn't exist,
    or updates an existing listing with new data if changed.
    """
    brand = brand.strip().upper()
    key = (manufacturer, brand, model, vram)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, component_id, price, club_price, available
            FROM product_listing
            WHERE url = %s
            LIMIT 1;
        """, (url,))
        listing = cur.fetchone()

        if listing:
            listing_id, component_id, existing_price, existing_club_price, existing_available = listing
            if (existing_price != price or
                    existing_club_price != club_price or
                    existing_available != available):
                cur.execute("""
                    UPDATE product_listing
                    SET price = %s, club_price = %s, available = %s
                    WHERE id = %s;
                """, (price, club_price, available, listing_id))
            existing_gpus.add(key)
            return

        cur.execute("""
            SELECT g.component_id
            FROM gpu g
            JOIN component c ON g.component_id = c.id
            WHERE g.manufacturer = %s
              AND g.brand = %s
              AND g.model = %s
              AND (g.vram IS NOT DISTINCT FROM %s)
            LIMIT 1;
        """, (manufacturer, brand, model, vram))
        row = cur.fetchone()

        if row:
            component_id = row[0]
            existing_gpus.add(key)

        else:
            cur.execute("""
                INSERT INTO component (type)
                VALUES (%s)
                RETURNING id;
            """, ("GPU",))
            component_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO gpu (component_id, manufacturer, brand, model, vram)
                VALUES (%s, %s, %s, %s, %s);
            """, (component_id, manufacturer, brand, model, vram))

            existing_gpus.add(key)

        cur.execute("""
            INSERT INTO product_listing (component_id, store_id, price, club_price, available, description, img_url, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (component_id, store_id, price, club_price, available, description, img_url, url))


def extract_vram(desc):
    """
    Input: Product description (str)
    Output: VRAM size in GB (int) or None

    Extracts the VRAM size from a product description using regex pattern matching.
    """
    desc = desc.upper()

    vram_pattern = re.compile(r'(?<!\d)(?:O)?(\d{1,3})(?=\s?(G|GB|GDDR|GD))')
    matches = vram_pattern.findall(desc)

    if matches:
        vram_values = [int(match[0].lstrip('0') or '0') for match in matches]
        return max(vram_values)

    return None


def extract_model(desc, manufacturer):
    """
    Input: Product description (str), manufacturer (str)
    Output: Normalized GPU model string (e.g. 'RTX 3060 Ti') or None

    Extracts and normalizes the GPU model (prefix, number, and suffix) from the product description.
    """
    desc_upper = desc.upper()

    model_pattern = re.compile(
        r'(GTX|RTX|GT|RX|R5|R)\s?(\d{2,4})([A-Z0-9 ]*)', re.IGNORECASE)

    match = model_pattern.search(desc)
    if not match:
        return None

    prefix = match.group(1).upper()
    number = match.group(2)
    suffix_part = match.group(3).strip().lower()
    first_word = re.split(r'\W+', suffix_part)[0]  # split on non-alphanumeric characters
    first_word = first_word.replace('-', '').replace(' ', '')
    manufacturer = manufacturer.lower() if manufacturer else ""

    if "nvidia" in manufacturer:
        allowed_suffixes = {
            '': '',
            'ti': 'Ti',
            'super': 'Super',
            'tisuper': 'Ti Super',
            'tis': 'Ti Super',
            's': 'Super',
        }
    elif "amd" in manufacturer:
        allowed_suffixes = {
            '': '',
            'x': 'X',
            'xt': 'XT',
            'xtx': 'XTX',
            'gre': 'GRE',
        }
    else:
        allowed_suffixes = {'': ''}

    suffix = ''
    for key in sorted(allowed_suffixes.keys(), key=len, reverse=True):
        if first_word == key:
            suffix = allowed_suffixes[key]
            break

    model_str = f"{prefix} {number}"
    if suffix:
        model_str += f" {suffix}"

    return model_str


def get_price(price_text):
    """
    Input: Raw price text (str)
    Output: Price as integer (int) or 0 if invalid

    Cleans and parses a raw price string into an integer number (in denars).
    """
    cleaned = re.sub(r"[^\d,\.]", "", price_text)
    cleaned = cleaned.replace('.', '').replace(',', '.')

    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def get_manufacturer(product_name):
    """
    Input: Product name or description (str)
    Output: Manufacturer string ('Nvidia' or 'AMD')

    Detects the manufacturer from the product name using predefined NVIDIA keywords.
    """
    product_name_upper = product_name.upper()
    return "Nvidia" if any(keyword in product_name_upper for keyword in NVIDIA_KEYWORDS) else "AMD"
