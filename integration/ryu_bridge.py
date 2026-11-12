import requests

RYU_BASE_URL = "http://127.0.0.1:8080"
TIMEOUT = 5


def get_network_state():
    """Fetch the current network state from the controller."""
    try:
        response = requests.get(
            f"{RYU_BASE_URL}/state",
            timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        print(f"Controller connection error: {error}")
        return None


def send_decision(decision):
    """Send an approved decision to the controller.

    Always returns a dictionary:
      ok           True only if the controller accepted the rule
      message      what the controller said (or why we could not reach it)
      unreachable  True if the controller could not be contacted
      http_status  the controller's HTTP status code, when it replied
    """
    try:
        response = requests.post(
            f"{RYU_BASE_URL}/rule",
            json=decision,
            timeout=TIMEOUT
        )
    except requests.RequestException as error:
        print(f"Controller rule submission error: {error}")
        return {
            "ok": False,
            "unreachable": True,
            "message": f"Controller not reachable: {error}"
        }

    try:
        body = response.json()
    except ValueError:
        body = {}

    if not isinstance(body, dict):
        body = {}

    body.setdefault("ok", response.ok)
    body.setdefault(
        "message",
        body.get("msg") or f"Controller replied HTTP {response.status_code}"
    )
    body["http_status"] = response.status_code
    return body
