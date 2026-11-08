import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_interface import process_network_state

with open(PROJECT_ROOT / "data/test_state.json") as file:
    state = json.load(file)

print("\n===== HYDRANET INTEGRATION PIPELINE TEST =====")

result = process_network_state(state)

print("Status:", result["status"])
print("Validated:", result["validated"])
print("Message:", result["message"])
print("Decision:", result["decision"])

if result["validated"]:
    print("\nTEST PASSED: AI integration pipeline working!")
else:
    print("\nTEST FAILED:", result["message"])
