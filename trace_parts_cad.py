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


# TraceParts login credentials
EMAIL = "stplvivek@gmail.com"
PASSWORD = "Welcome@321"

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
                host="13.201.205.150",
                port=3306,
                user="gd_data",
                password="GD@2025@softage",
                database="tracepart",
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
# ============================================================

def start_driver():
    """
    Starts an undetected Chrome WebDriver instance.

    Uses anti-detection techniques to bypass automation checks.

    Returns
    -------
    WebDriver
        Running Chrome driver instance.
    """

    while True:
        driver = None
        try:
            options = Options()
            options.add_argument("--profile-directory=Default")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--lang=en-US")

            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            driver = uc.Chrome()

            # Remove Selenium webdriver flag
            driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """)

            time.sleep(2)
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


# ============================================================
# DOWNLOAD LOGIC
# ============================================================

# def download_cad(driver,filename, part_url):
#     try:
#         driver.get(part_url)
#         driver.implicitly_wait(5)

#         human_delay(2,4)
#         # human_scroll(driver)
#         check_cloudflare(driver)

#         dropdown = WebDriverWait(driver,10).until(
#             EC.element_to_be_clickable((By.ID,"dropdown-cad-format")))
        
#         human_click(driver, dropdown)
#         human_delay()
#         try:
#             option = WebDriverWait(driver,10).until(
#                 EC.presence_of_element_located((By.XPATH,"//div[normalize-space()='STEP AP242']")))
            
#             driver.execute_script("arguments[0].scrollIntoView(true);", option)
#             human_delay()
#             human_click(driver, option)
#             print("STEP AP242 selected")
#             driver.implicitly_wait(3)
#             time.sleep(2)
#             driver.find_element(By.XPATH, "//button[@id='direct-cad-download']/i").click()  # Click outside to close dropdown
#         except Exception as e:
#             print("Desired format option not found:", e)

#         try:
#             notification_pane = WebDriverWait(driver, 10).until(
#                 EC.element_to_be_clickable((By.XPATH, '//div[@class="notif-container"]/i[@id="dashboard-button"]')))
#             human_click(driver, notification_pane)
#             time.sleep(3)
#         except Exception as e:
#             print("Notification pane button not found:")

        
#         file_href = get_download_link(driver)
#         print(file_href)
#         download_file(file_href, filename)

#     except Exception as e:
#         print("Error during download initiation:", e)
#         return

def download_cad(driver,filename, part_url):
    if not prepare_download(driver, part_url):
        print("Preparation for download failed.")
        return

    file_href = get_download_link(driver)
    if file_href:
        download_file(file_href, filename)
    else:
        print("Download link not found, skipping file.")

def open_product_page(driver, part_url):
    """
    Opens the product page and handles initial delays + Cloudflare.
    """
    driver.get(part_url)
    driver.implicitly_wait(5)

    human_delay(2, 4)
    check_cloudflare(driver)

def open_cad_dropdown(driver):
    """
    Click CAD format dropdown.
    """
    dropdown = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "dropdown-cad-format"))
    )

    human_click(driver, dropdown)
    human_delay()

    return dropdown

def select_step_format(driver):
    """
    Selects STEP AP242 format from dropdown.
    """
    while True:
        try:
            option = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[normalize-space()='STEP AP242']")
                )
            )

            driver.execute_script("arguments[0].scrollIntoView(true);", option)
            human_delay()

            human_click(driver, option)

            print("STEP AP242 selected")

            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//button[@id='direct-cad-download']/i"))
            ).click()

            return True

        except Exception as e:
            print("Desired format option not found retrying")
            driver.refresh()
            driver.implicitly_wait(5)
            open_cad_dropdown(driver)
    
def open_notification_pane(driver):
        while True:
            """
            Opens the notification/download panel.
            """
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

        select_step_format(driver)

        open_notification_pane(driver)

        return True

    except Exception as e:
        print("Error in prepare_download:", e)
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
        time.sleep(2)
        # btn_link = driver.find_element(By.XPATH, '(//div[@class="download-item-container"]/a[contains(@href,"downloads")])[1]').get_attribute("href")
        # print(f"Download link: {btn_link}")
        print("Starting file download for file_name: ", filename)
        response = requests.get(btn_link)
        file_name = os.path.join("trace_parts", filename)
        if response.status_code == 200:
            with open(file_name, "wb") as f:
                f.write(response.content)
            print("Download completed successfully.")
        else:
            print("Download failed.", response.status_code)

    except Exception as e:
        print("Download confirmation failed:",  response.status_code)
    time.sleep(5)



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
    """
    One full session:
    - start browser
    - login
    - download 7 files
    - close browser
    """

    global offset

    driver = start_driver()
    login(driver)
    check_cloudflare(driver)

    print("Session started")

    # Fetch only 7 records (important)
    url_list = get_url_list()[:7]

    for filename, part_url in url_list:
        try:
            download_cad(driver, filename, part_url)

            # update progress
            offset += 1
            save_offset(offset)

            # small delay between downloads
            time.sleep(random.uniform(2, 5))

        except Exception as e:
            print("Download failed:", e)

    driver.quit()
    print("Session completed, driver closed.")



# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    while True:
        try:
            run_session()

            # wait 5–15 minutes before next session
            sleep_time = random.randint(300, 900)
            print(f"Waiting {sleep_time//60} minutes before next session...")
            time.sleep(sleep_time)

        except Exception as e:
            print("Error in main loop:", e)
            time.sleep(30)


if __name__ == "__main__":
    main()