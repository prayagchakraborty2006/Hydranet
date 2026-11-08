
import json
from llm_agent import validate

with open("data/test_state.json") as file:
    state = json.load(file)

src = "AA:AA:AA:AA:AA:01"
dst = "BB:BB:BB:BB:BB:02"

tests = [
    {
        "name": "Existing path should be rejected",
        "rule": {
            "action": "reroute",
            "src_mac": src,
            "dst_mac": dst,
            "path": [1, 2, 4]
        },
        "expected": False
    },
    {
        "name": "Alternative path should be accepted",
        "rule": {
            "action": "reroute",
            "src_mac": src,
            "dst_mac": dst,
            "path": [1, 3, 4]
        },
        "expected": True
    },
    {
        "name": "Invalid link should be rejected",
        "rule": {
            "action": "reroute",
            "src_mac": src,
            "dst_mac": dst,
            "path": [1, 2, 3, 4]
        },
        "expected": False
    },
    {
        "name": "Unknown source host should be rejected",
        "rule": {
            "action": "reroute",
            "src_mac": "CC:CC:CC:CC:CC:03",
            "dst_mac": dst,
            "path": [1, 3, 4]
        },
        "expected": False
    },
    {
        "name": "Path containing a loop should be rejected",
        "rule": {
            "action": "reroute",
            "src_mac": src,
            "dst_mac": dst,
            "path": [1, 2, 1, 3, 4]
        },
        "expected": False
    },
    {
        "name": "Incorrect starting switch should be rejected",
        "rule": {
            "action": "reroute",
            "src_mac": src,
            "dst_mac": dst,
            "path": [2, 4]
        },
        "expected": False
    }
]

passed = 0

print("\n===== HYDRANET VALIDATOR TESTS =====\n")

for test in tests:
    valid, message = validate(test["rule"], state)
    success = valid == test["expected"]

    if success:
        passed += 1

    print(f"Test: {test['name']}")
    print(f"Expected: {test['expected']}")
    print(f"Actual:   {valid}")
    print(f"Message:  {message}")
    print("Result:   ", "PASS" if success else "FAIL")
    print("-" * 45)

print(f"\nSUMMARY: {passed}/{len(tests)} tests passed")

if passed == len(tests):
    print("All validator tests passed!")
else:
    print("Some tests failed. Check the results above.")
