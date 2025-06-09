import json

input_file = 'combined_sites.jsonl'
output_file = 'filtered_phishing.jsonl'

with open(input_file, 'r', encoding='utf-8') as fin, open(output_file, 'w', encoding='utf-8') as fout:
    for line in fin:
        try:
            data = json.loads(line.strip())
            if data.get("label") == "phishing" or data.get("label") == 1:
                fout.write(json.dumps(data, ensure_ascii=False) + '\n')
        except json.JSONDecodeError as e:
            print(f"Error decoding line: {e}")