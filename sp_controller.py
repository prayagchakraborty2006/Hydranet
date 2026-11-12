import networkx as nx

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, arp, ether_types
from os_ken.topology import event
from os_ken.topology.api import get_switch, get_link


class ShortestPathSwitch(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.G = nx.Graph()
        self.datapaths = {}      # dpid -> datapath
        self.hosts = {}          # mac -> (dpid, port)
        self.link_ports = {}     # dpid -> set of ports that face other switches

    # ---------- switch connect: table-miss rule ----------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        self.datapaths[dp.id] = dp
        self.G.add_node(dp.id)
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                          ofp.OFPCML_NO_BUFFER)]
        self.add_flow(dp, 0, match, actions)

    def add_flow(self, dp, priority, match, actions):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority,
                                      match=match, instructions=inst))

    def delete_all_flows(self):
        """Remove only host-destination flows (Dijkstra + reroute rules).
        Keeps the table-miss rule, the LLDP rule and block rules intact."""
        for dp in self.datapaths.values():
            ofp, parser = dp.ofproto, dp.ofproto_parser
            for mac in list(self.hosts):
                dp.send_msg(parser.OFPFlowMod(
                    datapath=dp, command=ofp.OFPFC_DELETE,
                    out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY,
                    match=parser.OFPMatch(eth_dst=mac)))

    # ---------- topology tracking ----------
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
        down = (msg.desc.state & ofp.OFPPS_LINK_DOWN) or \
               (msg.desc.config & ofp.OFPPC_PORT_DOWN)
        if not down:
            return
        removed = []
        for x, y, data in list(self.G.edges(data=True)):
            if (x == dp.id and data.get(x) == port) or \
               (y == dp.id and data.get(y) == port):
                self.G.remove_edge(x, y)
                removed.append((x, y))
        if removed:
            self.logger.info("LINK DOWN (port-down on s%s port %s): %s",
                             dp.id, port, removed)
            self.logger.info("GRAPH edges: %s", list(self.G.edges()))
            self.delete_all_flows()
            self.logger.info("Old flows cleared; paths recompute on next packet")

    # ---------- packet handling ----------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        if eth.dst.startswith('33:33'):      # ignore IPv6 multicast noise
            return

        src, dst = eth.src, eth.dst

        # learn host location only on host-facing ports
        if in_port not in self.link_ports.get(dp.id, set()):
            if self.hosts.get(src) != (dp.id, in_port):
                # one host per host-facing port: forget any older MAC on this port
                for old, loc in list(self.hosts.items()):
                    if loc == (dp.id, in_port) and old != src:
                        del self.hosts[old]
                        self.logger.info("HOST forgotten (replaced by %s): %s", src, old)
                self.hosts[src] = (dp.id, in_port)
                self.logger.info("HOST learned: %s at s%s port %s",
                                 src, dp.id, in_port)

        # broadcast / unknown destination: flood on host ports only
        if dst == 'ff:ff:ff:ff:ff:ff' or dst not in self.hosts:
            if in_port in self.link_ports.get(dp.id, set()):
                # arrived from another switch: deliver to local hosts only
                self.flood_host_ports(dp, msg, in_port)
            else:
                # arrived from a host: send to local hosts and all neighbours once
                self.flood_everywhere_from_edge(dp, msg, in_port)
            return

        # known destination: compute path and install flows
        self.install_path(src, dst)
        # forward this first packet along the path
        dst_dpid, dst_port = self.hosts[dst]
        out_port = self.next_port(dp.id, dst)
        if out_port is not None:
            actions = [parser.OFPActionOutput(out_port)]
            data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
            dp.send_msg(parser.OFPPacketOut(
                datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
                actions=actions, data=data))

    def host_ports(self, dpid):
        dp = self.datapaths[dpid]
        ports = set()
        for p in dp.ports.keys():
            if p < dp.ofproto.OFPP_MAX and p not in self.link_ports.get(dpid, set()):
                ports.add(p)
        return ports

    def flood_host_ports(self, dp, msg, in_port):
        parser = dp.ofproto_parser
        actions = [parser.OFPActionOutput(p)
                   for p in self.host_ports(dp.id) if p != in_port]
        if actions:
            data = msg.data if msg.buffer_id == dp.ofproto.OFP_NO_BUFFER else None
            dp.send_msg(parser.OFPPacketOut(
                datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
                actions=actions, data=data))

    def flood_everywhere_from_edge(self, dp, msg, in_port):
        """Packet from a host: send it out the host ports of EVERY switch once.
        Uses the controller to avoid loops (no switch-to-switch flooding)."""
        for dpid, other in self.datapaths.items():
            parser = other.ofproto_parser
            ofp = other.ofproto
            ports = self.host_ports(dpid)
            if dpid == dp.id:
                ports = ports - {in_port}
            actions = [parser.OFPActionOutput(p) for p in ports]
            if actions:
                other.send_msg(parser.OFPPacketOut(
                    datapath=other, buffer_id=ofp.OFP_NO_BUFFER,
                    in_port=ofp.OFPP_CONTROLLER,
                    actions=actions, data=msg.data))

    # ---------- path logic ----------
    def next_port(self, dpid, dst_mac):
        dst_dpid, dst_port = self.hosts[dst_mac]
        if dpid == dst_dpid:
            return dst_port
        try:
            path = nx.shortest_path(self.G, dpid, dst_dpid)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
        return self.G[dpid][path[1]][dpid]

    def install_path(self, src_mac, dst_mac):
        if src_mac not in self.hosts or dst_mac not in self.hosts:
            return
        for a, b in ((src_mac, dst_mac), (dst_mac, src_mac)):
            src_dpid, _ = self.hosts[a]
            dst_dpid, dst_port = self.hosts[b]
            try:
                path = nx.shortest_path(self.G, src_dpid, dst_dpid)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                self.logger.info("No path s%s -> s%s", src_dpid, dst_dpid)
                return
            self.logger.info("PATH %s -> %s : %s", a, b, path)
            for i, dpid in enumerate(path):
                dp = self.datapaths[dpid]
                parser = dp.ofproto_parser
                if i == len(path) - 1:
                    out_port = dst_port
                else:
                    out_port = self.G[dpid][path[i + 1]][dpid]
                match = parser.OFPMatch(eth_dst=b)
                actions = [parser.OFPActionOutput(out_port)]
                self.add_flow(dp, 1, match, actions)
