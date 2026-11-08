import json
import time
import requests

from pydantic import BaseModel, ConfigDict
from typing import Literal, Optional, List


CONTROLLER = "http://10.238.134.142:8080"
OLLAMA = "http://127.0.0.1:11434/api/generate"

MODEL = "qwen3:4b"

CHECK_EVERY = 3
COOLDOWN = 30
MAX_TRIES = 3


# ============================================================
# LLM OUTPUT SCHEMA
# ============================================================

class LLMDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["none", "reroute", "block", "unblock"]

    src_mac: Optional[str] = None
    dst_mac: Optional[str] = None
    path: Optional[List[int]] = None

    reason: str


# ============================================================
# GET NETWORK STATE FROM RYU
# ============================================================

def get_state():
    response = requests.get(
        CONTROLLER + "/state",
        timeout=5
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# HOST TRAFFIC
# ============================================================

def host_rates(state):
    rates = state["port_load_bytes_per_sec"]
    out = {}

    for mac, loc in state["hosts"].items():
        out[mac] = rates.get(
            str(loc["switch"]), {}
        ).get(
            str(loc["port"]), 0
        )

    return out


# ============================================================
# FIND ALL POSSIBLE PATHS
# ============================================================

def all_paths(state, a, b):

    adj = {}

    for link in state["links"]:

        adj.setdefault(
            link["src"],
            set()
        ).add(
            link["dst"]
        )

        adj.setdefault(
            link["dst"],
            set()
        ).add(
            link["src"]
        )

    found = []

    def walk(node, path):

        if node == b:
            found.append(path)
            return

        for nxt in adj.get(node, ()):

            if nxt not in path:
                walk(
                    nxt,
                    path + [nxt]
                )

    walk(a, [a])

    return found


# ============================================================
# DETERMINISTIC VALIDATOR
# ============================================================

def validate(rule, state):

    if not isinstance(rule, dict):

        return False, "rule must be a JSON object"


    action = rule.get("action")


    # --------------------------------------------------------
    # NO ACTION
    # --------------------------------------------------------

    if action == "none":

        return True, "no action needed"


    # --------------------------------------------------------
    # REROUTE
    # --------------------------------------------------------

    if action == "reroute":

        src = rule.get("src_mac")
        dst = rule.get("dst_mac")
        path = rule.get("path")

        hosts = state["hosts"]


        if src not in hosts:

            return False, (
                "src_mac is not a known host"
            )


        if dst not in hosts:

            return False, (
                "dst_mac is not a known host"
            )


        if src == dst:

            return False, (
                "src_mac and dst_mac must differ"
            )


        if (
            not isinstance(path, list)
            or not path
            or not all(
                isinstance(x, int)
                and not isinstance(x, bool)
                for x in path
            )
        ):

            return False, (
                "path must be a list of integers"
            )


        # No loops

        if len(path) != len(set(path)):

            return False, (
                "path contains a loop"
            )


        # Correct source/destination switches

        if path[0] != hosts[src]["switch"]:

            return False, (
                "path must start at the "
                "source host's switch"
            )


        if path[-1] != hosts[dst]["switch"]:

            return False, (
                "path must end at the "
                "destination host's switch"
            )


        # Live links only

        live = {
            frozenset(
                (l["src"], l["dst"])
            )
            for l in state["links"]
        }


        for x, y in zip(
            path,
            path[1:]
        ):

            if frozenset(
                (x, y)
            ) not in live:

                return False, (
                    "no live link between "
                    f"s{x} and s{y}"
                )


                # Candidate path validation

        pair_key = f"{src}->{dst}"

        candidate_paths = all_paths(
            state,
            hosts[src]["switch"],
            hosts[dst]["switch"]
        )

        if path not in candidate_paths:

            return False, (
                "path is not a valid candidate path"
            )


        # Do not accept the existing route again

        current_path = state.get(
            "paths", {}
        ).get(pair_key)

        if current_path and path == current_path:

            return False, (
                "selected path is the current path; "
                "a different path is required"
            )


        return True, "ok"


    # --------------------------------------------------------
    # BLOCK
    # --------------------------------------------------------

    if action == "block":

        mac = rule.get("src_mac")

        hosts = state["hosts"]


        if mac not in hosts:

            return False, (
                "src_mac is not a known host"
            )


        if (
            len(hosts) < 2
            or
            len(
                set(state["blocked"])
                | {mac}
            ) >= len(hosts)
        ):

            return False, (
                "refusing to block every host"
            )


        return True, "ok"


    # --------------------------------------------------------
    # UNBLOCK
    # --------------------------------------------------------

    if action == "unblock":

        mac = rule.get("src_mac")


        if mac not in state["blocked"]:

            return False, (
                "that MAC is not currently blocked"
            )


        return True, "ok"


    return False, (
        f"unknown action {action!r}"
    )


# ============================================================
# BUILD LLM PROMPT
# ============================================================


def build_prompt(state, feedback=None):

    rates = host_rates(state)
    macs = list(state["hosts"])

    # Identify overloaded hosts
    heavy_hosts = [
        mac for mac, rate in rates.items()
        if rate > state["heavy_threshold"]
    ]

    # Select source and destination for rerouting
    reroute_source = heavy_hosts[0] if heavy_hosts else None

    reroute_destination = next(
        (mac for mac in macs if mac != reroute_source),
        None
    )

    # Find possible paths for every host pair
    options = {}

    for a in macs:
        for b in macs:
            if a != b:
                options[f"{a}->{b}"] = all_paths(
                    state,
                    state["hosts"][a]["switch"],
                    state["hosts"][b]["switch"]
                )

    summary = {
        "hosts": state["hosts"],
        "links": [
            [link["src"], link["dst"]]
            for link in state["links"]
        ],
        "current_paths": state["paths"],
        "possible_paths": options,
        "host_port_traffic_bytes_per_sec": rates,
        "heavy_threshold": state["heavy_threshold"],
        "heavy_hosts": heavy_hosts,
        "reroute_source": reroute_source,
        "reroute_destination": reroute_destination,
        "already_blocked": state["blocked"]
    }

    prompt = (
        "You are an SDN traffic engineer.\n\n"

        "Choose exactly ONE action: none, reroute, block, or unblock.\n\n"

        "IMPORTANT DECISION RULES:\n"
        "1. If heavy_hosts is not empty, choose action=reroute.\n"
        "2. Use reroute_source as src_mac.\n"
        "3. Use reroute_destination as dst_mac.\n"
        "4. Choose a path from possible_paths for that exact pair.\n"
        "5. If a current path exists, choose a different path.\n"
        "6. Never choose a path that is not listed.\n"
        "7. If there are no heavy hosts, choose action=none.\n\n"

        "For action=none, src_mac, dst_mac and path must be null.\n"
        "For action=reroute, provide src_mac, dst_mac and path.\n"
        "For action=block or unblock, provide src_mac.\n\n"

        "Use only known MAC addresses and live network links.\n"
        "Never invent network nodes or paths.\n\n"

        "Network state:\n"
        + json.dumps(summary, indent=2)
    )

    if feedback:
        prompt += (
            "\n\nYour previous answer was rejected by "
            "the safety validator:\n"
            f"{feedback}\n"
            "Return a corrected decision."
        )

    return prompt



# ============================================================
# ASK QWEN
# ============================================================

def ask_llm(prompt):

    response = requests.post(

        OLLAMA,

        json={

            "model": MODEL,

            "prompt": prompt,

            "stream": False,

            "format":
                LLMDecision.model_json_schema(),

            "think": False,

            "options": {
                "temperature": 0
            }
        },

        timeout=180
    )


    response.raise_for_status()


    raw = response.json()["response"]


    decision = LLMDecision.model_validate_json(
        raw
    )


    return decision.model_dump()


# ============================================================
# DECISION LOOP
# ============================================================

def decide(state):

    feedback = None


    for attempt in range(
        1,
        MAX_TRIES + 1
    ):

        try:

            rule = ask_llm(
                build_prompt(
                    state,
                    feedback
                )
            )

        except Exception as error:

            feedback = (
                f"invalid LLM decision: {error}"
            )

            print(
                f"  attempt {attempt}: "
                f"bad LLM output: {error}"
            )

            continue


        print(
            "  LLM decision:",
            rule
        )


        ok, msg = validate(
            rule,
            state
        )


        if not ok:

            feedback = msg

            print(
                f"  attempt {attempt}: "
                f"own validator rejected: "
                f"{msg}"
            )

            continue


        # ----------------------------------------------------
        # NO ACTION
        # ----------------------------------------------------

        if rule["action"] == "none":

            print(
                "  ✅ LLM: no action needed "
                f"({rule.get('reason', '')})"
            )

            return


        # ----------------------------------------------------
        # SEND SAFE ACTION TO CONTROLLER
        # ----------------------------------------------------

        payload = {
            k: v
            for k, v in rule.items()
            if k != "reason"
            and v is not None
        }


        try:

            response = requests.post(

                CONTROLLER + "/rule",

                json=payload,

                timeout=5
            )


            response.raise_for_status()

            body = response.json()


        except Exception as error:

            print(
                "  controller error:",
                error
            )

            return


        print(
            "  controller says:",
            response.status_code,
            body
        )


        if body.get("ok"):

            print(
                "  reason:",
                rule.get("reason", "")
            )

            return


        feedback = body.get(
            "message",
            "controller rejected rule"
        )


    print(
        "  ❌ gave up: "
        "controller kept rejecting the decision"
    )


# ============================================================
# CHANGE SIGNATURE
# ============================================================

def signature(state):

    rates = host_rates(state)

    heavy = tuple(
        sorted(
            m
            for m, r in rates.items()
            if r > state["heavy_threshold"]
        )
    )

    return (
        len(state["links"]),
        tuple(state["blocked"]),
        heavy
    )


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    last_sig = None
    last_time = 0


    print(
        "Agent running. Ctrl+C to stop."
    )


    while True:

        try:

            state = get_state()


            if (
                state.get("hosts")
                and
                len(state["hosts"]) >= 2
            ):

                sig = signature(
                    state
                )


                if (
                    sig != last_sig
                    and
                    time.time()
                    - last_time
                    > COOLDOWN
                ):

                    print(
                        "\nChange detected: "
                        "links=%s blocked=%s heavy=%s"
                        % sig
                    )


                    decide(
                        state
                    )


                    try:

                        new_state = get_state()

                        last_sig = signature(
                            new_state
                        )

                    except Exception:

                        last_sig = sig


                    last_time = time.time()


        except Exception as error:

            print(
                "controller unreachable:",
                error
            )


        time.sleep(
            CHECK_EVERY
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
