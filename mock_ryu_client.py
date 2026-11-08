
import json
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:5000"

# 1. Check whether HydraNet AI is online
print("\n===== RYU HEALTH CHECK =====")

try:
    with urllib.request.urlopen(
        API_URL + "/health"
    ) as response:

        health = json.loads(response.read())

        print("API Status:", health["status"])
        print("Service:", health["service"])

except Exception as error:
    print("Cannot connect to HydraNet AI:", error)
    raise SystemExit(1)


# 2. Load simulated network state
print("\n===== SENDING NETWORK STATE =====")

with open("data/test_state.json") as file:
    network_state = json.load(file)

payload = json.dumps(network_state).encode("utf-8")

request = urllib.request.Request(
    API_URL + "/decision",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)


# 3. Send network state to AI
try:
    with urllib.request.urlopen(request) as response:

        result = json.loads(response.read())

        print("HTTP Status:", response.status)
        print("Decision Status:", result["status"])
        print("Validated:", result["validated"])
        print("Decision:", json.dumps(
            result["decision"], indent=2
        ))

except urllib.error.HTTPError as error:

    result = json.loads(error.read())

    print("HTTP Status:", error.code)
    print("Decision Status:", result["status"])
    print("Message:", result["message"])

except Exception as error:
    print("Communication error:", error)

# 4. Simulate installation and record approved routing rule

import os
from datetime import datetime, timezone

print("\n===== RYU ROUTE INSTALLATION =====")

if result["status"] == "accepted":

    decision = result["decision"]

    if decision and decision["action"] == "reroute":

        src = decision["src_mac"]
        dst = decision["dst_mac"]
        path = decision["path"]

        print("Installing route...")
        print("Source:", src)
        print("Destination:", dst)
        print("Approved path:", path)

        print("SIMULATION: Route installation successful!")

        # 5. Save the approved route in a JSON file

        os.makedirs("data", exist_ok=True)

        log_file = "data/installed_routes.json"

        if os.path.exists(log_file):
            with open(log_file, "r") as file:
                try:
                    records = json.load(file)
                except json.JSONDecodeError:
                    records = []
        else:
            records = []

        if not isinstance(records, list):
            records = []

        records.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": src,
            "destination": dst,
            "path": path,
            "status": "simulated_installation"
        })

        with open(log_file, "w") as file:
            json.dump(records, file, indent=2)

        print("Route decision saved to:", log_file)

    else:
        print("No rerouting required.")

else:
    print("Route installation rejected.")
