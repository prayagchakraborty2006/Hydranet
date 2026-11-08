
from llm_agent import build_prompt, ask_llm, validate
from state_validator import validate_network_state


def process_network_state(state):

    # 1. Check that input is a dictionary
    if not isinstance(state, dict):
        return {
            "status": "rejected",
            "validated": False,
            "message": "Network state must be a JSON object",
            "decision": None
        }

    try:

        # 2. Validate incoming network state
        state_ok, state_message = validate_network_state(state)

        if not state_ok:
            return {
                "status": "rejected",
                "validated": False,
                "message": state_message,
                "decision": None
            }

        # 3. Build prompt for Qwen
        prompt = build_prompt(state)

        # 4. Ask Qwen for a decision
        rule = ask_llm(prompt)

        # 5. Validate the decision independently
        ok, message = validate(rule, state)

        # 6. Reject unsafe decisions
        if not ok:
            return {
                "status": "rejected",
                "validated": False,
                "message": message,
                "decision": None
            }

        # 7. Remove explanation before returning action
        decision = {
            key: value
            for key, value in rule.items()
            if key != "reason"
        }

        return {
            "status": "accepted",
            "validated": True,
            "message": message,
            "decision": decision,
            "reason": rule.get("reason", "")
        }

    except Exception as error:

        # 8. Fail safely if anything goes wrong
        return {
            "status": "rejected",
            "validated": False,
            "message": str(error),
            "decision": None
        }
