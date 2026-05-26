import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    try:
        r = requests.get(url, timeout=5)
        print(f"GET {endpoint} - Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  Success (keys: {list(data.keys()) if isinstance(data, dict) else 'list'})")
            # Print a tiny sample
            if isinstance(data, dict):
                first_key = list(data.keys())[0]
                val = data[first_key]
                print(f"  Sample [{first_key}]: {str(val)[:200]}")
            else:
                print(f"  Sample: {str(data)[:200]}")
        else:
            print(f"  FAILED: {r.text[:200]}")
    except Exception as e:
        print(f"GET {endpoint} - ERROR: {e}")

def test_post(endpoint, payload):
    url = f"{BASE_URL}{endpoint}"
    try:
        r = requests.post(url, json=payload, timeout=5)
        print(f"POST {endpoint} - Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  Success (keys: {list(data.keys()) if isinstance(data, dict) else 'list'})")
            print(f"  Sample: {str(data)[:200]}")
        else:
            print(f"  FAILED: {r.text[:200]}")
    except Exception as e:
        print(f"POST {endpoint} - ERROR: {e}")

print("=== STARTING ENDPOINT TESTS ===")
test_get("/api/ml/overview-stats")
test_get("/api/ml/district-distribution")
test_get("/api/ml/top-risk-districts")
test_get("/api/ml/trend-analysis")
test_get("/api/ml/model-stats")

test_post("/api/ml/compare-districts", {"locations": ["punjab", "bihar"]})
test_post("/api/ml/predict-risk", {"extraction_pct": 110.0, "state": "punjab"})
test_post("/api/ml/predict-groundwater", {"year": 2025, "state": "punjab"})
test_post("/api/ml/simulate-digital-twin", {"state": "punjab"})
print("=== END OF ENDPOINT TESTS ===")
