#!/bin/bash
# Clean reset between HydraNet demos.
# Stops the controller and clears Mininet/Open vSwitch leftovers.
# It does NOT touch Flask (api_server.py) or Ollama.
echo "Stopping controller..."
pkill -f run_controller.py
echo "Cleaning Mininet and Open vSwitch..."
sudo mn -c
echo
echo "Clean. Now start, in this order:"
echo "  Terminal 1: python3 run_controller.py"
echo "  Terminal 2: sudo mn --custom diamond.py --topo diamond --controller=remote,ip=127.0.0.1,port=6653 --switch ovsk,protocols=OpenFlow13   (then: pingall)"
