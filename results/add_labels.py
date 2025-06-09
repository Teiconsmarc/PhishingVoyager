import json

json1_path = 'partial_results_gemini-2.5-flash-preview-05-20.json'
json2_path = 'results_phishintention.json'

with open(json1_path, 'r', encoding='utf-8') as f:
    data1 = json.load(f)

with open(json2_path, 'r', encoding='utf-8') as f:
    data2 = json.load(f)

label_dict = {item['web']: item['label'] for item in data1 if 'web' in item and 'label' in item}

for item in data2:
    web = item.get('url')
    if web in label_dict:
        item['label'] = label_dict[web]

# Guardar el resultado actualizado
with open('results_phishintention.json', 'w', encoding='utf-8') as f:
    json.dump(data2, f, indent=2, ensure_ascii=False)
