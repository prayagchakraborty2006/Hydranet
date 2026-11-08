
import json
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:5000/decision"

# Load deliberately invalid network data
with open("data/invalid_state.json") as file:
    state = json.load(file)

payload = json.dumps(state).encode("utf-8")

request = urllib.request.Request(
    API_URL,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

print("\n===== HYDRANET REJECTION TEST =====")

try:
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read())
        status_code = response.status

except urllib.error.HTTPError as error:
    status_code = error.code
    result = json.loads(error.read())

print("HTTP Status:", status_code)
print("Decision Status:", result["status"])
print("Validated:", result["validated"])
print("Message:", result["message"])
print("Decision:", result.get("decision"))

# Verify that invalid data was rejected
if status_code == 422 and result["status"] == "rejected":
    print("\nTEST PASSED: Invalid network state was rejected.")
    print("No approved route was returned.")
else:
    print("\nTEST FAILED: Unexpected API response.")
