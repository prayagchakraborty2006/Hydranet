
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_interface import process_network_state
from llm_agent import validate

passed = 0
failed = 0


def check(name, condition):
    global passed, failed

    if condition:
        print(f"PASS: {name}")
        passed += 1
    else:
        print(f"FAIL: {name}")
        failed += 1


print("\n===== HYDRANET SAFETY TEST SUITE =====")

# Test 1: Valid network state through AI pipeline
with open(PROJECT_ROOT / "data/test_state.json") as file:
    state = json.load(file)

result = process_network_state(state)

check(
    "Valid network state accepted by AI pipeline",
    result["status"] == "accepted" and result["validated"] is True
)

# Test 2: Invalid network state
invalid_state = json.loads(json.dumps(state))
invalid_state["port_load_bytes_per_sec"]["1"]["1"] = -500

invalid_result = process_network_state(invalid_state)

check(
    "Invalid network state rejected",
    invalid_result["status"] == "rejected"
    and invalid_result["decision"] is None
)

# Test 3: Impossible route rejected
unsafe_decision = {
    "action": "reroute",
    "src_mac": "AA:AA:AA:AA:AA:01",
    "dst_mac": "BB:BB:BB:BB:BB:02",
    "path": [1, 2, 3, 4],
    "reason": "Testing unsafe route"
}

route_ok, message = validate(unsafe_decision, state)

check(
    "Impossible route rejected by validator",
    route_ok is False
)

print("\n===== FINAL RESULTS =====")
print("Passed:", passed)
print("Failed:", failed)

if failed == 0:
    print("\nALL SAFETY TESTS PASSED!")
else:
    print("\nSOME TESTS FAILED!")
    sys.exit(1)
