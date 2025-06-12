from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException  # Try-Catch

from constants import NVIDIA_KEYWORDS

import re  # Regex
import psycopg2  # SQL


def get_db_connection():
    return psycopg2.connect(
        dbname="gpu_products_db",
        user="postgres",
        password="admin",
        host="localhost",
        port="5432"
    )


def initialize_scraping():
    conn = get_db_connection()
    existing_gpus = load_existing_gpus(conn)
    return conn, existing_gpus


def get_db_connection():
    return psycopg2.connect(
        dbname="gpu_products_db",
        user="postgres",
        password="admin",
        host="localhost",
        port="5432"
    )


def load_existing_gpus(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT g.manufacturer, g.brand, g.model, g.vram
            FROM gpu g
            JOIN component c ON g.component_id = c.id
        """)
        return set((m, b, mo, v) for m, b, mo, v in cur.fetchall())


def initialize_browser(start_url):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    browser = webdriver.Chrome(options=options)
    browser.get(start_url)

    return browser


def add_store(conn, name, url):
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
    # Normalize the string
    desc = desc.upper()

    # Look for patterns like '16GB', '32GDDR6', 'O16G', etc.
    vram_pattern = re.compile(r'(?<!\d)(?:O)?(\d{1,3})(?=\s?(G|GB|GDDR|GD))')
    matches = vram_pattern.findall(desc)

    if matches:
        # Extract the most likely correct match — typically the largest value
        vram_values = [int(match[0].lstrip('0') or '0') for match in matches]
        return max(vram_values)  # Return the largest VRAM found

    return None


def extract_model(desc, manufacturer):
    desc_upper = desc.upper()

    # Match Nvidia/AMD GPU prefixes with numbers: GTX, RTX, RX, GT, R5, R
    model_pattern = re.compile(
        r'(GTX|RTX|GT|RX|R5|R)\s?(\d{2,4})([A-Z0-9 ]*)', re.IGNORECASE)

    match = model_pattern.search(desc)
    if not match:
        return None

    prefix = match.group(1).upper()  # e.g. RTX
    number = match.group(2)  # e.g. 4070
    suffix_raw = match.group(3).strip().replace("-", "").replace(" ", "").lower()  # e.g. 's', 'ti', 'tisuper'

    manufacturer = manufacturer.lower() if manufacturer else ""

    # Define allowed suffixes per manufacturer (normalized to lowercase, no spaces)
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

    # Find suffix that starts the suffix_raw string (some suffixes might be combined or longer)
    suffix = ''
    for key in sorted(allowed_suffixes.keys(), key=len, reverse=True):
        if suffix_raw.startswith(key):
            suffix = allowed_suffixes[key]
            break

    model_str = f"{prefix} {number}"
    if suffix:
        model_str += f" {suffix}"

    return model_str


def get_price(price_text):
    cleaned = re.sub(r"[^\d,\.]", "", price_text)
    cleaned = cleaned.replace('.', '').replace(',', '.')

    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def get_manufacturer(product_name):
    product_name_upper = product_name.upper()
    return "Nvidia" if any(keyword in product_name_upper for keyword in NVIDIA_KEYWORDS) else "AMD"
