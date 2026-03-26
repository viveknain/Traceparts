"""
TraceParts CAD Downloader

This script automates login and CAD file downloads from TraceParts using Selenium.
It retrieves product URLs from a MySQL database, visits each page, selects the
STEP AP242 CAD format, and downloads the file.

Key Features:
- Uses undetected_chromedriver to reduce bot detection
- Mimics human interaction (typing, scrolling, clicking)
- Handles Cloudflare verification pages
- Reads URLs in batches from MySQL
- Saves download progress to avoid reprocessing
"""

import json

import requests
import random
import time
import os
import mysql.connector

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import undetected_chromedriver as uc

# ============================================================
# CONFIGURATION
# ============================================================

with open('credentials.json', 'r') as f:
    creds = json.load(f)

# TraceParts login credentials
EMAIL = creds.get("email")
PASSWORD = creds.get("password")

# Example product URL (not used in batch mode)
PRODUCT_URL = "https://www.traceparts.com/en/product/ganternormteile-gn-1113-key-rings-stainless-steel?CatalogPath=TRACEPARTS%3ATP01001&Product=90-17042025-049598"

# Number of records fetched per database batch
BATCH_SIZE = 7

# File used to track last processed database offset
PROGRESS_FILE = "progress.txt"


# ============================================================
# PROGRESS MANAGEMENT
# ============================================================

def load_offset():
    """
    Reads the last processed offset from the progress file.

    Returns
    -------
    int
        The last saved offset value.
        Returns 0 if the file does not exist.
    """
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return int(f.read())
    return 0


def save_offset(offset):
    """
    Saves the current database offset to a file.

    Parameters
    ----------
    offset : int
        Current position in database records.
    """
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(offset))


# Load starting offset
offset = load_offset()

print(f"Starting from database offset: {offset}")
# ============================================================
# DATABASE CONNECTION
# ============================================================

def db_connector():
    """
    Establishes a persistent connection to the MySQL database.

    Retries automatically if the connection fails.

    Returns
    -------
    mysql.connector.connection
        Active database connection.
    """
    while True:
        try:
            connection = mysql.connector.connect(
                host="ip",
                port=port,
                user="user",
                password="password",
                database="dbname",
                connection_timeout=10
            )

            if connection.is_connected():
                print("Connected to MySQL")
                return connection

        except mysql.connector.Error as e:
            print("Database connection failed:", e)
            print("Retrying in 10 seconds...")
            time.sleep(10)


# ============================================================
# HUMAN-LIKE INTERACTION UTILITIES
# ============================================================

def human_delay(a=1.5, b=3.5):
    """
    Introduces a random delay to simulate human behavior.
    """
    time.sleep(random.uniform(a, b))


def human_typing(element, text):
    """
    Types text into an input element character-by-character.

    Parameters
    ----------
    element : WebElement
        Input field element
    text : str
        Text to type
    """
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(0.07, 0.22))


def human_click(driver, element):
    """
    Moves cursor to an element and clicks it with a small delay.

    Parameters
    ----------
    driver : WebDriver
    element : WebElement
    """
    actions = ActionChains(driver)
    actions.move_to_element(element).pause(random.uniform(0.5, 1.3)).click().perform()
    human_delay()


def human_scroll(driver):
    """
    Scrolls down the page randomly to mimic human browsing.
    """
    for _ in range(random.randint(2, 4)):
        driver.execute_script(f"window.scrollBy(0,{random.randint(300,700)})")
        human_delay(1, 2)


# ============================================================
# DRIVER INITIALIZATION
# ====import undetected_chromedriver as uc

def start_driver():
    while True:
        driver = None
        try:
            options = uc.ChromeOptions()

            options.add_argument("--lang=en-US")

            # ✅ Disable password manager & save popup
            prefs = {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "profile.password_manager_leak_detection": False
            }
            options.add_experimental_option("prefs", prefs)

            driver = uc.Chrome(options=options)

            driver.maximize_window()
            print("Driver started successfully")
            return driver

        except Exception as e:
            print("Driver start failed:", e)
            if driver:
                try:
                    driver.quit()
                except:
                    pass

            print("Retrying in 5 seconds...")
            time.sleep(5)

# ============================================================
# LOGIN PROCESS
# ============================================================

def login(driver):
    """
    Logs into TraceParts using provided credentials.

    Parameters
    ----------
    driver : WebDriver
    """

    driver.get("https://www.traceparts.com/en/sign-in")
    driver.implicitly_wait(10)

    human_delay(3, 5)

    # Handle cookie banner
    try:
        driver.find_element(By.XPATH, '//span[text()="Continue without agreeing"]').click()
        print("Cookie banner dismissed.")
    except:
        print("No cookie banner found.")

    # Enter email
    email = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//input[@autocomplete='Email']"))
    )

    human_click(driver, email)
    time.sleep(1)
    email.clear()
    time.sleep(1.5)

    human_typing(email, EMAIL)

    # Enter password
    password = driver.find_element(By.XPATH, "//input[@type='password']")

    if not password.get_attribute("value"):
        human_click(driver, password)
        human_typing(password, PASSWORD)

    # Click login
    try:
        login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        human_click(driver, login_btn)
        human_delay(2, 4)

        driver.implicitly_wait(3)
        time.sleep(3)

    except Exception as e:
        print("Login button not found or click failed:", e)

    # Submit form via keyboard
    email.click()
    email.send_keys(Keys.ENTER)

    print("Login completed, waiting for page to load...")

# ============================================================
# CLOUDFLARE HANDLING
# ============================================================

def handle_cloudflare(driver):
    """
    Detects and waits for Cloudflare verification pages.

    Returns
    -------
    bool
        True if verification was detected and handled.
    """

    try:
        print("Checking for Cloudflare verification...")

        WebDriverWait(driver, 10).until_not(
            EC.presence_of_element_located(
                (By.XPATH, "//h2[text()='Performing security verification']")
            )
        )

        driver.refresh()

        print("Cloudflare verification detected.")
        print("Please solve the captcha manually...")
        print("Verification completed.")

        return True

    except:
        print("No Cloudflare verification detected.")
        time.sleep(5)


def check_cloudflare(driver):
    """
    Attempts Cloudflare verification handling multiple times.
    """
    try:
        for x in range(2):
            res = handle_cloudflare(driver)
            if res:
                print("Cloudflare verification handled successfully.")
                break
    except:
        return False


def safe_execute(func, *args, retries=3, delay=2):
    for attempt in range(retries):
        try:
            print(f"[TRY {attempt+1}] {func.__name__}")
            return func(*args)
        except Exception as e:
            print(f"[ERROR] {func.__name__}: {e}")
            time.sleep(delay)
    return None


# ============================================================
# DOWNLOAD LOGIC
# ============================================================

def download_cad(driver, filename, part_url):
    try:
        print(f"\n[START] Processing: {filename}")

        if not prepare_download(driver, part_url):
            print("[FAIL] prepare_download failed")
            return False

        file_href = get_download_link(driver)

        if not file_href:
            print("[FAIL] No download link")
            return False

        success = download_file(file_href, filename)

        if success:
            print(f"[SUCCESS] {filename}")
            return True

        return False

    except Exception as e:
        print(f"[ERROR] download_cad: {e}")
        return False

def open_product_page(driver, part_url):
    """
    Opens the product page and handles initial delays + Cloudflare.
    """
    driver.get(part_url)
    driver.implicitly_wait(5)
    print(f"Opened product page: {part_url}")
    human_delay(2, 4)
    res = check_cloudflare(driver)
    return res

def open_cad_dropdown(driver):
    """
    Click CAD format dropdown.
    """
    dropdown = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "dropdown-cad-format"))
    )
    print("CAD format dropdown found, clicking to open.")
    human_click(driver, dropdown)
    human_delay()

    return dropdown

def select_step_format(driver):
    for attempt in range(3):
        try:
            print(f"[STEP SELECT] Attempt {attempt+1}")

            option = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[normalize-space()='STEP AP242']")
                )
            )

            driver.execute_script("arguments[0].scrollIntoView(true);", option)
            human_click(driver, option)

            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "direct-cad-download"))
            ).click()

            print("[OK] STEP selected")
            return True

        except Exception as e:
            print("[RETRY] STEP selection failed:", e)
            driver.refresh()
            time.sleep(2)

    print("[FAIL] STEP selection failed after retries")
    return False
    
def open_notification_pane(driver):
        i = 0
        while i<3:
            """
            Opens the notification/download panel.
            """
            print(f"Attempting to open notification pane, attempt {i}")
            try:
                notification_pane = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        '//div[@class="notif-container"]/i[@id="dashboard-button"]'
                    ))
                )

                human_click(driver, notification_pane)
                human_delay(2, 3)

                return True

            except Exception as e:
                i += 1
                print("Notification pane button not found, retrying")
                

def prepare_download(driver, part_url):
    """
    Full flow:
    - open page
    - select CAD format
    - open notification panel
    """

    try:
        open_product_page(driver, part_url)

        open_cad_dropdown(driver)

        res = select_step_format(driver)
        print(res)
        if res:
            open_notification_pane(driver)

        return True
    except Exception as e:
        print("Error in prepare_download:")
        return False
    
    
def get_download_link(driver):
    try:
        btn_link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '(//div[@class="download-item-container"]/a[contains(@href,"downloads")])[1]'))
        ).get_attribute("href")
        print(f"Download link: {btn_link}")
        return btn_link
    except Exception as e:
        print("Download link not found:", e)
        return None


def download_file(btn_link, filename):
    try:
        print(f"[DOWNLOAD] {filename}")

        response = requests.get(btn_link, timeout=(10, 60))

        if response.status_code == 200:
            file_path = os.path.join("trace_parts", filename)

            with open(file_path, "wb") as f:
                f.write(response.content)

            print("[OK] File saved")
            return True

        else:
            print(f"[FAIL] Status: {response.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] download_file: {e}")
        return False


# ============================================================
# FETCH URLS FROM DATABASE
# ============================================================

def get_url_list():
    """
    Retrieves a batch of product URLs from the database.

    Returns
    -------
    list of tuple
        [(filename, part_url), ...]
    """

    while True:
        try:
            connection = db_connector()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT filename, part_url FROM tracepart.parts LIMIT %s OFFSET %s;",
                (BATCH_SIZE, offset)
            )

            urls = cursor.fetchall()
            url_list = [(item[0], item[1]) for item in urls]

            print(f"Fetched {len(url_list)} URLs from database.")

            return url_list

        except mysql.connector.Error as e:
            print("Database query failed:", e)
            print("Retrying in 10 seconds...")
            time.sleep(10)


def run_session():
    global offset

    driver = None

    try:
        driver = start_driver()
        login(driver)
        check_cloudflare(driver)

        print("[SESSION STARTED]")

        url_list = get_url_list()

        if not url_list:
            print("[INFO] No URLs found")
            return

        for filename, part_url in url_list:

            success = safe_execute(download_cad, driver, filename, part_url)

            if success:
                offset += 1
                save_offset(offset)
                print(f"[PROGRESS] Offset updated → {offset}")

            else:
                print(f"[SKIP] {filename}")

            time.sleep(random.uniform(2, 4))

    except Exception as e:
        print("[FATAL ERROR] run_session:", e)

    finally:
        if driver:
            try:
                driver.quit()
                print("[DRIVER CLOSED]")
            except:
                pass


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    while True:
        try:
            print("\n========== NEW SESSION ==========")
            run_session()

            sleep_time = random.randint(300, 600)
            print(f"[WAIT] {sleep_time}s before next run")

            time.sleep(sleep_time)

        except Exception as e:
            print("[MAIN ERROR]:", e)
            time.sleep(30)


if __name__ == "__main__":
    main()
