import json
import sys
from starlette.testclient import TestClient
from app.main import app

sys.stdout.reconfigure(encoding='utf-8')

client = TestClient(app)

queries = [
    "What is UniGraph IQ Enterprise 2.0 and how does the QA Guardian work?",
    "Which products in our catalog are ready to publish right now?",
    "Show me products with attribute conflicts that need review",
    "What contactors or motor control products do we have?",
    "What syndication export formats does the platform support?",
    "Show source evidence for voltage ratings"
]

print("=" * 70)
print("RUNNING DETAILED COPILOT INTELLIGENCE TESTS")
print("=" * 70)

for q in queries:
    print(f"\n[QUERY]: {q}")
    resp = client.post("/api/copilot", json={"question": q})
    assert resp.status_code == 200, f"Error {resp.status_code}: {resp.text}"
    data = resp.json()
    print("-" * 50)
    print(f"[ANSWER]:\n{data.get('answer', '')}")
    if data.get('products'):
        skus = [p.get('sku') for p in data['products'][:5]]
        print(f"[ATTACHED PRODUCTS]: {', '.join(skus)}")
    if data.get('evidence'):
        print(f"[ATTACHED EVIDENCE CHUNKS]: {len(data['evidence'])} snippets")
    print("-" * 50)

print("\n>>> ALL COPILOT TESTS PASSED SUCCESSFULLY! <<<")
