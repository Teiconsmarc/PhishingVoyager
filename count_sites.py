import json
from collections import Counter

INPUT_FILE = 'results/partial_results_gemini-2.5-flash-preview-05-20.json'  # Cambia por tu nombre de archivo

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

seen_ids = set()
predicted_counter = Counter()
matched_label_predicted_counter = Counter()

for item in data:
    item_id = item.get('id')
    predicted = item.get('predicted')
    label = item.get('label')

    if item_id is not None and item_id not in seen_ids:
        seen_ids.add(item_id)
        
        if predicted in [0, 1]:
            predicted_counter[predicted] += 1
            
            if label in [0, 1]:
                key = f"label={label}, predicted={predicted}"
                matched_label_predicted_counter[key] += 1

# Mostrar resultados
print(f"Predicted = 0: {predicted_counter[0]}")
print(f"Predicted = 1: {predicted_counter[1]}")
print(f"Total únicos con predicted 0 o 1: {sum(predicted_counter.values())}")
print("\nCoincidencias con label:")
for key, count in matched_label_predicted_counter.items():
    print(f"{key}: {count}")
