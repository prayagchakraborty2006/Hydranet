
import re
import math

def validate_network_state(state):

    if not isinstance(state, dict):
        return False, "Network state must be a dictionary"

    required_fields = [
        "hosts",
        "links",
        "paths",
        "port_load_bytes_per_sec",
        "heavy_threshold",
        "blocked"
    ]

    for field in required_fields:
        if field not in state:
            return False, f"Missing required field: {field}"

    # Validate hosts
    hosts = state["hosts"]

    if not isinstance(hosts, dict) or not hosts:
        return False, "Hosts must be a non-empty dictionary"

    for mac, info in hosts.items():

        if not isinstance(mac, str) or not re.fullmatch(
            r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", mac
        ):
            return False, f"Invalid MAC address: {mac}"

        if not isinstance(info, dict):
            return False, f"Invalid host information: {mac}"

        for field in ["switch", "port"]:
            value = info.get(field)

            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return False, f"Invalid {field} for host: {mac}"

    # Validate links
    if not isinstance(state["links"], list):
        return False, "Links must be a list"

    for link in state["links"]:

        if not isinstance(link, dict):
            return False, "Each link must be a dictionary"

        src = link.get("src")
        dst = link.get("dst")

        if any(not isinstance(x, int) or isinstance(x, bool) or x <= 0
               for x in [src, dst]):
            return False, "Link switch IDs must be positive integers"

        if src == dst:
            return False, "A switch cannot link to itself"

    # Validate current paths
    if not isinstance(state["paths"], dict):
        return False, "Paths must be a dictionary"

    for path in state["paths"].values():

        if path is not None and (
            not isinstance(path, list)
            or any(not isinstance(x, int) or isinstance(x, bool) for x in path)
        ):
            return False, "Invalid current path"

    # Validate traffic measurements
    traffic = state["port_load_bytes_per_sec"]

    if not isinstance(traffic, dict):
        return False, "Traffic measurements must be a dictionary"

    for switch, ports in traffic.items():

        if not isinstance(ports, dict):
            return False, f"Invalid port measurements for switch {switch}"

        for port, rate in ports.items():

            if (
                not isinstance(rate, (int, float))
                or isinstance(rate, bool)
                or not math.isfinite(rate)
                or rate < 0
            ):
                return False, f"Invalid traffic rate for switch {switch}, port {port}"

    # Validate heavy traffic threshold
    threshold = state["heavy_threshold"]

    if (
        not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not math.isfinite(threshold)
        or threshold < 0
    ):
        return False, "Heavy threshold must be a non-negative number"

    # Validate blocked hosts
    if not isinstance(state["blocked"], list):
        return False, "Blocked hosts must be a list"

    for mac in state["blocked"]:
        if mac not in hosts:
            return False, f"Unknown blocked host: {mac}"

    return True, "Network state is valid"
