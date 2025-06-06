import os
import requests
import logging
from requests.exceptions import RequestException
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

def save_site_snapshot(task, output_dir="webs_output", timeout=30):
    """
    Save HTML code and a screenshot of the web site of a certain task
    """

    web_name = task['web_name']
    url = task['web']
    out_path = os.path.join(output_dir, web_name)

    if not os.path.exists(out_path):
        os.makedirs(out_path, exist_ok=True)
    else:
        return

    # Save URL
    with open(os.path.join(out_path, 'info.txt'), 'w', encoding='utf-8') as f_info:
        f_info.write(url)

    # Save HTML
    try:
        response = requests.get(url, timeout=timeout)
        with open(os.path.join(out_path, 'html.txt'), 'w', encoding='utf-8') as f_html:
            f_html.write(response.text)
    except Exception as e:
        with open(os.path.join(out_path, 'html_error.txt'), 'w', encoding='utf-8') as f_err:
            f_err.write(f"Error fetching HTML: {e}\n")

    # Screenshot
    chrome_options= Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1280,800")

    try:
        service = Service("/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        try:
            driver.get(url)
            sleep(2)
            screenshot_path = os.path.join(out_path, 'shot.png')
            driver.save_screenshot(screenshot_path)
        except WebDriverException as e:
            with open(os.path.join(out_path, 'screenshot_error.txt'), 'w', encoding='utf-8') as f_err:
                f_err.write(f"Screenshot error: {e}\n")
        finally:
            driver.quit()

    except Exception as e:
        with open(os.path.join(out_path, 'webdriver_error.txt'), 'w', encoding='utf-8') as f_err:
            f_err.write(f"WebDriver init error: {e}\n")

def check_page_availability(task):
    """
    Checks if a webpage is available. 
    It returns True if the webapage is okay, False otherwise.
    """

    url = task["web"]

    #First we check the HTTP requests (HTTP < 400)
    try:
        response = requests.get(url, timeout=30)
        if response.status_code >= 400:
            raise RequestException(f"HTTP error: {response.status_code}")

    except RequestException as e:
        logging.warning(f"[TASK {task['id']}] Page unavailable: {task['web']}")
        return False

    #After the requests we check that the pages loads correctly
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1280,800")

    try:
        driver = webdriver.Chrome(service=Service("/usr/local/bin/chromedriver"), options=chrome_options)
        driver.set_page_load_timeout(20)

        try:
            driver.get(url)
            sleep(2)
            body_text = driver.page_source.lower()

            error_indicators = [
                "this page isn’t working",
                "this site can’t be reached",
                "http error",
                "dns_probe_finished_nxdomain",
                "err_name_not_resolved",
                "net::err",
                "webpage is not available",
                "site can’t be reached",
                "error 496",
                "temporarily unavailable",
                "url terminated"
            ]

            if any(err in body_text for err in error_indicators):
                logging.warning(f"Domain not available: {(err in body_text for err in error_indicators)}")
                return False

        except (TimeoutException, WebDriverException) as e:
            logging.warning(f"Page not working: {e}")
            return False

        finally:
            driver.quit()

    except Exception as e:
        logging.warning(f"[Availability check] Error creating WebDriver: {e}")
        return False

    return True