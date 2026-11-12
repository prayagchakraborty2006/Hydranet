
import sys
import threading
import time
from pathlib import Path

from flask import Flask, request, jsonify

PROJECT_ROOT = Path(__file__).resolve().parent
INTEGRATION_DIR = PROJECT_ROOT / "integration"
sys.path.insert(0, str(INTEGRATION_DIR))

from ai_interface import process_network_state
from ryu_bridge import get_network_state, send_decision

app = Flask(__name__)

# Store the latest AI execution result
status_lock = threading.Lock()
run_lock = threading.Lock()

latest_status = {
    "running": False,
    "last_run": None,
    "network_state": None,
    "ai_result": None,
    "controller_result": None
}

ALLOWED_ORIGINS = {
    "http://127.0.0.1:8080",
    "http://localhost:8080"
}


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")

    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Vary"] = "Origin"

    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "service": "HydraNet AI"
    })


@app.route("/decision", methods=["POST"])
def decision():
    if not request.is_json:
        return jsonify({
            "status": "rejected",
            "validated": False,
            "message": "Request must contain JSON"
        }), 400

    state = request.get_json()
    result = process_network_state(state)

    if result["validated"]:
        return jsonify(result), 200

    return jsonify(result), 422


@app.route("/status", methods=["GET"])
def get_status():
    with status_lock:
        return jsonify(latest_status)


@app.route("/run", methods=["POST"])
def run_ai():

    if not run_lock.acquire(blocking=False):
        return jsonify({
            "status": "running",
            "message": "An AI analysis is already in progress."
        }), 409

    try:
        with status_lock:
            latest_status["running"] = True

        print("\n===== HYDRANET DASHBOARD AI RUN =====")

        # 1. Fetch live network state
        print("\nFetching controller state...")
        state = get_network_state()

        if state is None or "error" in state:
            result = {
                "status": "rejected",
                "validated": False,
                "message": "Could not obtain valid network state.",
                "decision": None
            }

            controller_result = None

        else:
            # 2. Process and validate through AI pipeline
            print("\nRunning AI pipeline...")
            result = process_network_state(state)

            controller_result = None

            # 3. Submit only approved reroute decisions
            if result.get("status") == "accepted" and result.get("validated"):

                action = result.get("decision", {}).get("action")

                if action == "reroute":
                    print("\nSubmitting approved reroute...")
                    controller_result = send_decision(result["decision"])
                    controller_result["attempted"] = True

                elif action == "none":
                    controller_result = {
                        "ok": True,
                        "attempted": False,
                        "message": "No network changes required."
                    }

                else:
                    controller_result = {
                        "ok": False,
                        "attempted": False,
                        "message": "This action is not enabled for automatic submission."
                    }

        # 4. Cache result for dashboard
        with status_lock:
            latest_status.update({
                "running": False,
                "last_run": time.time(),
                "network_state": state,
                "ai_result": result,
                "controller_result": controller_result
            })

        print("\n===== AI RUN COMPLETED =====")
        print("Status:", result.get("status"))
        print("Decision:", result.get("decision"))
        print("Controller:", controller_result)

        return jsonify({
            "status": "completed",
            "ai_result": result,
            "controller_result": controller_result
        }), 200

    except Exception as error:
        print("AI RUN ERROR:", error)

        with status_lock:
            latest_status.update({
                "running": False,
                "last_run": time.time(),
                "ai_result": {
                    "status": "error",
                    "validated": False,
                    "message": str(error)
                }
            })

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500

    finally:
        with status_lock:
            latest_status["running"] = False

        run_lock.release()


if __name__ == "__main__":
    print("HydraNet AI API starting...")
    app.run(host="127.0.0.1", port=5000, debug=False)
