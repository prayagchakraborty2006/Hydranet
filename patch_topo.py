import os
p = os.path.expanduser('~/sp_controller.py')
s = open(p).read()
a = s.index('    # ---------- topology tracking ----------')
b = s.index('    # ---------- packet handling ----------')
new = '''    # ---------- topology tracking ----------
    def add_edge(self, l):
        s, d = l.src.dpid, l.dst.dpid
        self.G.add_node(s)
        self.G.add_node(d)
        self.G.add_edge(s, d)
        self.G[s][d][s] = l.src.port_no
        self.G[s][d][d] = l.dst.port_no
        self.link_ports.setdefault(s, set()).add(l.src.port_no)
        self.link_ports.setdefault(d, set()).add(l.dst.port_no)

    @set_ev_cls(event.EventLinkAdd)
    def link_add(self, ev):
        self.add_edge(ev.link)
        self.logger.info("GRAPH edges: %s", list(self.G.edges()))

    @set_ev_cls(event.EventLinkDelete)
    def link_delete(self, ev):
        # LLDP timeouts are unreliable here, so only log them.
        self.logger.info("LLDP timeout s%s -> s%s (ignored, waiting for port-down)",
                         ev.link.src.dpid, ev.link.dst.dpid)

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        port = msg.desc.port_no
        down = (msg.desc.state & ofp.OFPPS_LINK_DOWN) or \\
               (msg.desc.config & ofp.OFPPC_PORT_DOWN)
        if not down:
            return
        removed = []
        for x, y, data in list(self.G.edges(data=True)):
            if (x == dp.id and data.get(x) == port) or \\
               (y == dp.id and data.get(y) == port):
                self.G.remove_edge(x, y)
                removed.append((x, y))
        if removed:
            self.logger.info("LINK DOWN (port-down on s%s port %s): %s",
                             dp.id, port, removed)
            self.logger.info("GRAPH edges: %s", list(self.G.edges()))
            self.delete_all_flows()
            self.logger.info("Old flows cleared; paths recompute on next packet")

'''
open(p, 'w').write(s[:a] + new + s[b:])
print("patched")
