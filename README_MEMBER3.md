# HydraNet — AI-Powered SDN Traffic Controller

## 1. Project Overview

HydraNet is a Smart Software-Defined Networking (SDN) traffic management project that uses a locally hosted Large Language Model (LLM) to recommend network routing decisions.

The system combines:
- Ryu SDN controller (intended network controller)
- Mininet (network emulation)
- Ollama with Qwen3 4B (local LLM)
- Python-based route validation and safety checks
- Flask API for AI decision processing

**Core principle:** The LLM proposes network decisions, but deterministic Python validation decides whether a proposed decision is safe to accept.

## 2. System Architecture

Expected architecture:

Mininet → Ryu Controller → Network State JSON → AI Interface → Qwen3 4B → Structured Decision → Route Validator → Ryu Controller

The LLM does not directly control switches. Decisions must pass validation before being considered acceptable.

## 3. Main Components

| File | Responsibility |
|---|---|
| `llm_agent.py` | Generates structured LLM decisions and validates proposed actions |
| `ai_interface.py` | Connects network-state validation, LLM processing, and route validation |
| `state_validator.py` | Checks the structure and values of incoming network state |
| `api_server.py` | Provides Flask endpoints for health checks and decision processing |
| `integration/ryu_bridge.py` | Communicates with the expected Ryu state and rule endpoints |
| `integration/live_runner.py` | Runs the AI pipeline using state received from Ryu |
| `mock_ryu_client.py` | Tests the pipeline using simulated Ryu responses |
| `experiments/benchmark.py` | Measures LLM, validation, and pipeline latency |

## 4. Technology Stack

- Python
- Ollama
- Qwen3 4B
- Flask
- Pydantic
- Requests
- Ryu SDN Controller (integration pending verification)
- Mininet (integration pending verification)

## 5. Safety and Validation

The project implements deterministic checks before accepting a proposed network decision.

Checks include:
- Valid action type
- Known source and destination hosts
- Valid route endpoints
- No repeated switches in a route
- Only existing network links
- Route must be a valid candidate path
- No unnecessary repeated route
- Valid block and unblock requests
- Valid network-state structure and traffic measurements

Invalid network states and unsafe route proposals are rejected.

## 6. Testing

The following tests have been completed using local test data and the mock integration:

- LLM structured decision generation
- Network-state validation
- Valid route acceptance
- Invalid route rejection
- Invalid network-state rejection
- Flask API health and decision endpoints
- Mock Ryu client
- AI integration pipeline
- Safety test suite

The safety suite passed all three checks:
- Valid network state accepted
- Invalid network state rejected
- Impossible route rejected

## 7. Preliminary Performance Benchmark

Benchmark configuration:
- Model: Qwen3 4B
- Number of measured runs: 3
- Network input: `data/test_state.json`

| Metric | Average |
|---|---:|
| LLM decision latency | 2667.86 ms |
| Route validation latency | 0.01 ms |
| Total pipeline latency | 2520.23 ms |

Decision acceptance: 3/3
Success rate: 100%

Raw benchmark measurements are stored in:

`experiments/benchmark_results.csv`

These are preliminary results from a small test setup, not a large-scale network performance evaluation.

## 8. Project Structure

```text
HydraNet/
├── ai/
├── data/
├── experiments/
├── integration/
├── learning/
├── .venv/
├── ai_interface.py
├── api_server.py
├── llm_agent.py
├── state_validator.py
├── mock_ryu_client.py
└── README.md
```

## 9. Setup

Activate the Python virtual environment:

```bash
source .venv/bin/activate
```

Install the required packages if they are not already installed:

```bash
pip install flask requests pydantic
```

Ensure Ollama is running and Qwen3 4B is available:

```bash
ollama list
```

If the model is not installed:

```bash
ollama pull qwen3:4b
```

## 10. Running the AI API

Start the Flask API:

```bash
python api_server.py
```

The health endpoint is:

`http://127.0.0.1:5000/health`

## 11. Running Tests

Run the integration and safety checks:

```bash
python integration/test_live_pipeline.py
python integration/test_safety_suite.py
python test_valid_route.py
python test_invalid_route.py
python test_rejection.py
```

Run the performance benchmark:

```bash
python experiments/benchmark.py
```

## 12. Current Limitations and Future Work

The AI pipeline, validation logic, Flask API, mock integration, and preliminary benchmark have been tested locally.

The real Ryu controller connection and actual OpenFlow route installation have not yet been verified. The live integration depends on confirming the controller's `/state` and `/rule` endpoints and matching their network-state format.

Future work:
- Verify integration with the actual Ryu controller.
- Test using a real Mininet-emulated topology.
- Verify route installation through OpenFlow.
- Measure network performance under congestion and link failures.
- Expand benchmark scenarios and repeat measurements.
- Compare LLM-assisted routing with a conventional routing baseline.

## 13. Research Contribution

HydraNet explores the use of a locally hosted LLM for network routing recommendations while maintaining a deterministic safety boundary.

The main research idea is:

**LLM-based decision generation + structured output + deterministic route validation.**

This approach aims to combine flexible AI-based decision support with predictable safety checks before network actions are considered for execution.
