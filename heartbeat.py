import time
from os_ken.base import app_manager
from os_ken.lib import hub
from os_ken.controller import ofp_event
from os_ken.controller.handler import set_ev_cls, MAIN_DISPATCHER, DEAD_DISPATCHER


class Heartbeat(app_manager.OSKenApp):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.last = time.time()
        hub.spawn(self.beat)

    def beat(self):
        while True:
            hub.sleep(2)
            now = time.time()
            self.logger.info("HEARTBEAT gap=%.1fs", now - self.last)
            self.last = now

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state(self, ev):
        self.logger.info("SWITCH s%s state=%s",
                         getattr(ev.datapath, 'id', '?'), ev.state)
