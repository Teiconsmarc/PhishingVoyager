import json
import random

benign_path = 'benign_sites.json'
phishing_path = 'phishing_sites.json'
output_path = 'combined_sites_counts.jsonl'


def load_benign_sites(path, max_sites=500):
    with open(path, 'r') as f:
        data = json.load(f)
    return random.sample(data, min(max_sites, len(data)))
    
def load_phishing_sites(path):
    with open(path, 'r') as f:
        data = json.load(f)
    
    formatted = []
    for entry in data:
        phish_id = str(entry["phish_id"])
        formatted.append({
            "web_name": f"task--{phish_id}",
            "id": f"task--{phish_id}",
            "web": entry["url"],
            "label": "phishing"
        })
    return formatted

def main():
    benign_sites = load_benign_sites(benign_path, max_sites=500)
    phishing_sites = load_phishing_sites(phishing_path)

    combined = benign_sites + phishing_sites
    random.shuffle(combined)

    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in combined:
            f.write(json.dumps(entry) + '\n')

    print(f"Dataset combination complete: {len(combined)} saved entries in {output_path}")
    print(f"Benign: {len(benign_sites)} | Phishing: {len(phishing_sites)}")

if __name__=='__main__':
    main()
