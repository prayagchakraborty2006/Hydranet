from flask import Flask, request, jsonify

from ai_interface import process_network_state


app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "online",
        "service": "HydraNet AI"
    })


@app.route("/decision", methods=["POST"])
def decision():

    # Check whether the request contains JSON
    if not request.is_json:

        return jsonify({
            "status": "rejected",
            "validated": False,
            "message": "Request must contain JSON"
        }), 400

    # Read network state
    state = request.get_json()

    # Process it using our AI module
    result = process_network_state(state)

    # Return the result
    if result["validated"]:

        return jsonify(result), 200

    return jsonify(result), 422


if __name__ == "__main__":

    print("HydraNet AI API starting...")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
