import requests

queries = [
    "hello",
    "what is groundwater?",
    "what is agriculture?",
    "aqufer",           # typo - should fuzzy match to aquifer
    "groudwater",       # typo - should fuzzy match to groundwater
    "explain groundwater depletion",
    "thanks",
    "bye",
]

for q in queries:
    try:
        r = requests.post("http://127.0.0.1:8000/ask", json={"message": q})
        text = r.json()["text"][:150]
        print(f"Q: {q}")
        print(f"A: {text}")
        print(f"Status: {r.status_code}")
        print("---")
    except Exception as e:
        print(f"Q: {q}")
        print(f"ERROR: {e}")
        print("---")
