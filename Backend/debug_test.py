import requests

queries = [
    "What is groundwater?",
    "What is agriculture?",
    "Explain groundwater depletion",
    "What causes water scarcity?",
    "What is rainfall recharge?",
    "define aquifer",
    "tell me about water conservation",
]

for q in queries:
    r = requests.post("http://localhost:8000/ask", json={"message": q})
    data = r.json()
    text = data["text"][:150].replace("\n", " ")
    print(f"Q: {q}")
    print(f"A: {text}")
    print("---")
