import requests
import csv
import json
import zipfile
import time
import os
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

TRANCOLIST_URL = "https://tranco-list.eu/top-1m.csv.zip"
PHISHTANK_URL = "http://data.phishtank.com/data/online-valid.json"
TIMEOUT = 5
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def is_url_available(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return resp.status_code < 400
    except:
        return False

def get_tranco_sites(n=1000):
    print("Downloading Tranco domains...")
    resp = requests.get(TRANCOLIST_URL)
    with open("top-1m.csv.zip", "wb") as f:
        f.write(resp.content)

    with zipfile.ZipFile("top-1m.csv.zip", "r") as zip_ref:
        zip_ref.extractall(".")

    available_sites = []
    with open("top-1m.csv", newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header if present
        for i, row in enumerate(reader):
            print(f"{len(available_sites)}")
            domain = row[1]
            url = f"https://{domain}"
            if is_url_available(url):
                web_entry = {
                    "web_name": f"task-{i}",
                    "id": f"task--{i}",
                    "web": url,
                    "label": "benign"
                }
                available_sites.append(web_entry)
            if len(available_sites) >= n:
                break
    print(f"{len(available_sites)} legitimate domains saved.")
    return available_sites

def get_phish_tank_database():
    url = 'http://data.phishtank.com/data/online-valid.json'
    output_path = "./data/phish_tank_database.json"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        response = requests.get(url)
        response.raise_for_status()

        print('Response Ok')
        data = response.content.decode("utf-8")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(data)

        return data
    
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error: {err}")
    except requests.exceptions.ConnectionError:
        print("Unable to connect")
    except requests.exceptions.Timeout:
        print("Timeout")
    except requests.exceptions.RequestException as e:
        print(f"Unexpected error: {e}")
    except ValueError:
        print("Not able to decode JSON")

    return None

def load_phishtank_json(path="./data/phish_tank_database.json", final_count=1000, max_attempts=1500):
    print("Loading phishing sites from PhishTank JSON...")
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    phishing_sites = []
    checked = 0

    for entry in data:
        if entry.get("verified") != "yes" or entry.get("online") != "yes":
            continue

        url = entry.get("url")
        if not url:
            continue

        if is_url_available(url):
            entry["label"] = "phishing"
            phishing_sites.append(entry)

        checked += 1
        if len(phishing_sites) >= final_count:
            break
        if checked >= max_attempts:
            print("Alcanzado el límite de intentos.")
            break

        print(len(phishing_sites))

    print(f"{len(phishing_sites)} sitios de phishing válidos encontrados.")
    return phishing_sites

def save_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    tranco_data = get_tranco_sites(1000)
    save_json(tranco_data, "benign_sites.json")
    
    get_phish_tank_database()
    phish_data = load_phishtank_json("./data/phish_tank_database.json", final_count=1000, max_attempts=1500)
    save_json(phish_data, "phishing_sites.json")

