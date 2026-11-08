
import json
from ai_interface import process_network_state


with open("data/test_state.json") as f:
    state = json.load(f)


print("===== HYDRANET AI INTERFACE TEST =====")

result = process_network_state(state)

print(json.dumps(result, indent=2))


if result["validated"]:
    print("\nSUCCESS: Safe decision returned to controller!")

else:
    print("\nDECISION REJECTED: No action should be executed!")
