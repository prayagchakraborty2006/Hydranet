from os_ken.base import app_manager
from os_ken.controller.handler import set_ev_cls
from os_ken.topology import event
from os_ken.topology.api import get_switch, get_link


class TopoWatcher(app_manager.OSKenApp):

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter(self, ev):
        self.show_topology()

    @set_ev_cls(event.EventLinkAdd)
    def link_add(self, ev):
        self.logger.info("LINK ADDED: s%s -> s%s",
                         ev.link.src.dpid, ev.link.dst.dpid)
        self.show_topology()

    @set_ev_cls(event.EventLinkDelete)
    def link_delete(self, ev):
        self.logger.info("LINK DOWN: s%s -> s%s",
                         ev.link.src.dpid, ev.link.dst.dpid)
        self.show_topology()

    def show_topology(self):
        switches = [s.dp.id for s in get_switch(self)]
        links = [(l.src.dpid, l.dst.dpid) for l in get_link(self)]
        self.logger.info("Switches: %s", switches)
        self.logger.info("Links: %s", links)
