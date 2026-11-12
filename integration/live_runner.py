import sys
from pathlib import Path

# Allow imports from the main HydraNet directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_interface import process_network_state
from ryu_bridge import get_network_state, send_decision


def main():

    print("\n===== HYDRANET LIVE INTEGRATION =====")

    # 1. Fetch live network state
    print("\nFetching network state from controller...")

    state = get_network_state()

    if state is None:
        print("ERROR: Could not obtain network state.")
        return

    print("Network state received!")

    # 2. Process state using Qwen and validators
    print("\nSending state to AI pipeline...")

    result = process_network_state(state)

    # 3. Display AI decision
    print("\n===== AI DECISION RESULT =====")

    print("Status:", result["status"])
    print("Validated:", result["validated"])
    print("Message:", result["message"])

    if result["status"] != "accepted" or not result["validated"]:
        print("\nDecision rejected. Nothing sent to controller.")
        return

    decision = result["decision"]

    print("\nApproved decision:")
    print(decision)

    # 4. Only allow rerouting for now
    if decision.get("action") == "none":
        print("\nNo network changes required.")
        return

    if decision.get("action") != "reroute":
        print("\nAction not enabled for automatic submission.")
        return

    # 5. Submit approved reroute to controller
    print("\nSubmitting reroute to controller...")

    controller_result = send_decision(decision)

    if controller_result is None:
        print("\nERROR: Controller did not return a response.")
        return

    print("\n===== CONTROLLER RESPONSE =====")
    print("Accepted:", controller_result.get("ok"))
    print("Message:", controller_result.get("message"))


if __name__ == "__main__":
    main()
