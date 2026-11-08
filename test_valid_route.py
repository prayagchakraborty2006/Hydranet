import json
from llm_agent import validate

with open("data/test_state.json") as file:
    state = json.load(file)

valid_decision = {
    "action": "reroute",
    "src_mac": "AA:AA:AA:AA:AA:01",
    "dst_mac": "BB:BB:BB:BB:BB:02",
    "path": [1, 3, 4],
    "reason": "Testing a valid alternative route"
}

print("\n===== VALID ROUTE TEST =====")

ok, message = validate(valid_decision, state)

print("Route Valid:", ok)
print("Validator Message:", message)

if ok:
    print("\nTEST PASSED: Valid route accepted!")
else:
    print("\nTEST FAILED: Valid route rejected!")
