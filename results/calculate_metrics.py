import json
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

json_path = 'results_phishintention.json'
output_metrics_path = 'phishintention_metrics.txt'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

valid_data = [
    (int(item["label"]), int(item["is_phishing"]))
    for item in data
    if str(item.get("label")) in {"0", "1"} and str(item.get("is_phishing")) in {"0", "1"}
]

y_true = [label for label, pred in valid_data]
y_pred = [pred for label, pred in valid_data]

accuracy = accuracy_score(y_true, y_pred)
precision = precision_score(y_true, y_pred, zero_division=0)
recall = recall_score(y_true, y_pred, zero_division=0)
f1 = f1_score(y_true, y_pred, zero_division=0)

with open(output_metrics_path, 'w', encoding='utf-8') as f:
    f.write("Evaluation metrics:\n")
    f.write(f"✔ Accuracy : {accuracy:.4f}\n")
    f.write(f"✔ Precision: {precision:.4f}\n")
    f.write(f"✔ Recall   : {recall:.4f}\n")
    f.write(f"✔ F1 Score : {f1:.4f}\n")

print(f"Metrics saved in: {output_metrics_path}")
