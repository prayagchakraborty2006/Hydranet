from llm_agent import build_prompt, ask_llm, validate
from state_validator import validate_network_state


MAX_ATTEMPTS = 3


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

        # 3. Build the original prompt
        prompt = build_prompt(state)

        # 4. Allow Qwen up to 3 attempts
        for attempt in range(1, MAX_ATTEMPTS + 1):

            print(f"\nAI decision attempt {attempt}/{MAX_ATTEMPTS}")

            # Ask Qwen
            rule = ask_llm(prompt)

            # Independently validate the decision
            ok, message = validate(rule, state)

            if ok:

                # 5. Remove explanation before returning action
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
                    "reason": rule.get("reason", ""),
                    "attempts": attempt
                }

            # 6. Give Qwen validation feedback
            print(f"Decision rejected: {message}")

            prompt += (
                "\n\nIMPORTANT: Your previous decision was rejected "
                "by the independent validator.\n"
                f"Validation error: {message}\n"
                "Correct your previous decision using the original "
                "network state and the allowed paths.\n"
                "Do not repeat the rejected decision. "
                "Return only a valid JSON decision."
            )

        # 7. Reject if all attempts fail
        return {
            "status": "rejected",
            "validated": False,
            "message": (
                f"Decision failed validation after "
                f"{MAX_ATTEMPTS} attempts. Last error: {message}"
            ),
            "decision": None,
            "attempts": MAX_ATTEMPTS
        }

    except Exception as error:

        # 8. Fail safely if anything goes wrong
        return {
            "status": "rejected",
            "validated": False,
            "message": str(error),
            "decision": None
        }
