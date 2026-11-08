
import sys
from pathlib import Path

# Allow imports from the main HydraNet directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_interface import process_network_state
from ryu_bridge import get_network_state


def main():

    print("\n===== HYDRANET LIVE INTEGRATION =====")

    # 1. Fetch state from Ryu
    print("\nFetching network state from Ryu...")

    state = get_network_state()

    if state is None:
        print("ERROR: Could not obtain network state.")
        return

    print("Network state received!")

    # 2. Process state using Qwen and validators
    print("\nSending state to AI pipeline...")

    result = process_network_state(state)

    # 3. Display result
    print("\n===== AI DECISION RESULT =====")

    print("Status:", result["status"])
    print("Validated:", result["validated"])
    print("Message:", result["message"])

    if result["status"] == "accepted":
        print("Approved decision:")
        print(result["decision"])

        print("\nRoute installation is disabled.")
        print("Waiting for verified Ryu integration.")

    else:
        print("\nDecision rejected.")
        print("No route will be installed.")


if __name__ == "__main__":
    main()
