
import json
from llm_agent import validate

# Load our valid network topology
with open("data/test_state.json") as file:
    state = json.load(file)

# Create an unsafe route
# Switch 2 and switch 3 have no direct link
unsafe_decision = {
    "action": "reroute",
    "src_mac": "AA:AA:AA:AA:AA:01",
    "dst_mac": "BB:BB:BB:BB:BB:02",
    "path": [1, 2, 3, 4],
    "reason": "Testing an impossible route"
}

print("\n===== INVALID ROUTE TEST =====")

ok, message = validate(unsafe_decision, state)

print("Route Valid:", ok)
print("Validator Message:", message)

if not ok:
    print("\nTEST PASSED: Unsafe route rejected!")
else:
    print("\nTEST FAILED: Unsafe route was accepted!")
