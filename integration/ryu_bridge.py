
import requests

RYU_BASE_URL = "http://10.238.134.142:8080"
TIMEOUT = 5


def get_network_state():
    """Fetch the current network state from Ryu."""
    try:
        response = requests.get(
            f"{RYU_BASE_URL}/state",
            timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        print(f"Ryu connection error: {error}")
        return None


def send_decision(decision):
    """Send an approved routing decision to Ryu."""
    try:
        response = requests.post(
            f"{RYU_BASE_URL}/rule",
            json=decision,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        print(f"Ryu rule submission error: {error}")
        return None
