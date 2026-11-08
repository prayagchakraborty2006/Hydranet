
from ryu_bridge import get_network_state, send_decision

print("===== HYDRANET RYU BRIDGE TEST =====")

print("1. Ryu state function:", callable(get_network_state))
print("2. Ryu decision function:", callable(send_decision))

print("\nBridge functions loaded successfully!")
