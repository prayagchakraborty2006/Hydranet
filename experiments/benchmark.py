
import json
import time
import statistics
import csv
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_interface import process_network_state
from llm_agent import build_prompt, ask_llm, validate

ROOT = Path(__file__).resolve().parent.parent
REPEATS = 3

# Load test network
with open(ROOT / "data/test_state.json") as file:
    state = json.load(file)

print("\n===== HYDRANET PERFORMANCE BENCHMARK =====")
print("Number of measured runs:", REPEATS)


def measure(function, repeats):
    times = []

    for _ in range(repeats):
        start = time.perf_counter()
        result = function()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    return times


# 1. Measure LLM decision latency
prompt = build_prompt(state)

llm_times = measure(
    lambda: ask_llm(prompt),
    REPEATS
)

# 2. Measure deterministic route validation
decision = {
    "action": "reroute",
    "src_mac": "AA:AA:AA:AA:AA:01",
    "dst_mac": "BB:BB:BB:BB:BB:02",
    "path": [1, 3, 4],
    "reason": "Benchmark validation"
}

validation_times = measure(
    lambda: validate(decision, state),
    1000
)

# 3. Measure complete AI pipeline
pipeline_results = []
pipeline_times = []

for _ in range(REPEATS):
    start = time.perf_counter()
    result = process_network_state(state)
    elapsed = (time.perf_counter() - start) * 1000

    pipeline_times.append(elapsed)
    pipeline_results.append(result)


def report(name, values):
    print(f"\n{name}")
    print(f"  Average: {statistics.mean(values):.2f} ms")
    print(f"  Median:  {statistics.median(values):.2f} ms")
    print(f"  Minimum: {min(values):.2f} ms")
    print(f"  Maximum: {max(values):.2f} ms")


report("LLM DECISION LATENCY", llm_times)
report("ROUTE VALIDATION LATENCY", validation_times)
report("TOTAL PIPELINE LATENCY", pipeline_times)

accepted = sum(
    1 for result in pipeline_results
    if result["status"] == "accepted" and result["validated"]
)

print("\n===== SUCCESS RATE =====")
print(f"Accepted: {accepted}/{REPEATS}")
print(f"Success rate: {accepted / REPEATS * 100:.2f}%")


# Save raw measurements for research
output_file = ROOT / "experiments/benchmark_results.csv"

with open(output_file, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["metric", "run", "latency_ms"])

    for name, values in [
        ("llm", llm_times),
        ("validation", validation_times),
        ("pipeline", pipeline_times)
    ]:
        for index, value in enumerate(values, start=1):
            writer.writerow([name, index, f"{value:.4f}"])

print("\nRaw measurements saved to:", output_file)
