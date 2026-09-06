from flask import Flask, request, jsonify
import os
import random
import yaml

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plans.yaml')

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
            return data if data is not None else []
        except Exception:
            return []

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

@app.route('/api/plans', methods=['GET', 'POST'])
def handle_plans():
    if request.method == 'POST':
        save_data(request.json)
        return jsonify({"status": "success"})
    return jsonify(load_data())

@app.route('/api/random', methods=['GET'])
def get_random_plan():
    plans = load_data()
    if not plans:
        return jsonify({"error": "No plans available"}), 404

    # Selects a random plan from plans.yaml
    return jsonify(random.choice(plans))

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001)
