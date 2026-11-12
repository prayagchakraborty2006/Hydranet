import collections
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import networkx as nx

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, set_ev_cls
from os_ken.lib import hub

POLL_SECONDS = 2
THRESHOLD_BPS = 100000
HTTP_PORT = 8080
MAC_RE = re.compile(r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$')
REROUTE_PRIORITY = 10
BLOCK_PRIORITY = 100


class AIBridge(app_manager.OSKenApp):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last = {}      # (dpid, port) -> (rx_bytes, tx_bytes, time)
        self.packet_totals = {
        "received": 0,
        "transmitted": 0
   }
        self.rates = {}     # dpid -> {port: total bytes/sec}
        self.rx = {}        # dpid -> {port: bytes/sec into the switch}
        self.tx = {}        # dpid -> {port: bytes/sec out of the switch}
        self.blocked = set()
        self.rule_log = collections.deque(maxlen=100)
        hub.spawn(self._poll)
        self._start_http()

    def sp(self):
        return app_manager.lookup_service_brick('ShortestPathSwitch')

    # ---------- HTTP ----------
    def _start_http(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, code, obj):
                body = json.dumps(obj, indent=2).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == '/state':
                    self._send(200, app.build_state())
                elif self.path == '/events':
                    self._send(200, list(app.rule_log))
                elif self.path in ('/', '/index.html'):
                    try:
                        body = open(os.path.expanduser('~/dashboard.html'), 'rb').read()
                    except OSError:
                        body = b'dashboard.html not found in home folder'
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                if self.path != '/rule':
                    return self._send(404, {"error": "not found"})
                try:
                    n = int(self.headers.get('Content-Length', 0))
                    rule = json.loads(self.rfile.read(n))
                except Exception:
                    return self._send(400, {"ok": False,
                                            "error": "body is not valid JSON"})
                ok, msg = app.apply_rule(rule)
                app.add_event(rule, ok, msg)
                app.logger.info("RULE %s -> %s (%s)", rule,
                                "ACCEPTED" if ok else "REJECTED", msg)
                self._send(200 if ok else 422, {"ok": ok, "message": msg})

            def log_message(self, *args):
                pass

        server = HTTPServer(('0.0.0.0', HTTP_PORT), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.logger.info("HTTP API listening on port %s", HTTP_PORT)

    def add_event(self, rule, ok, msg):
        self.rule_log.append({'t': time.time(), 'ok': ok,
                              'rule': json.dumps(rule), 'msg': msg})

    # ---------- helpers ----------
    def host_sent_recv(self, sp, mac):
        d, p = sp.hosts[mac]
        sent = self.rx.get(d, {}).get(p, 0.0)   # host -> switch
        recv = self.tx.get(d, {}).get(p, 0.0)   # switch -> host
        return sent, recv

    def link_load(self, sp, a, b):
        pa, pb = sp.G[a][b][a], sp.G[a][b][b]
        return max(self.rates.get(a, {}).get(pa, 0.0),
                   self.rates.get(b, {}).get(pb, 0.0))

    # ---------- sandbox: simulate the rule on a copy of the network ----------
    def sandbox_reroute(self, sp, path):
        G = sp.G.copy()
        switches = {l[0] for m, l in sp.hosts.items() if m not in self.blocked}
        for a in switches:
            for b in switches:
                if a != b and not nx.has_path(G, a, b):
                    return False, "network is already split between s%s and s%s" % (a, b)
        for x, y in zip(path, path[1:]):
            load = self.link_load(sp, x, y)
            if load > THRESHOLD_BPS:
                return False, ("link s%s-s%s already carries %.0f B/s "
                               "(over threshold), pick a quieter path" % (x, y, load))
        return True, "sandbox ok"

    def sandbox_block(self, sp, mac, force):
        sent, _ = self.host_sent_recv(sp, mac)
        if sent < THRESHOLD_BPS and not force:
            return False, ("host sends only %.0f B/s, below threshold: "
                           "no evidence of attack" % sent)
        return True, "sandbox ok"

    # ---------- validation + apply ----------
    def apply_rule(self, rule):
        sp = self.sp()
        if sp is None:
            return False, "shortest-path app not running"
        if not isinstance(rule, dict):
            return False, "rule must be a JSON object"
        action = rule.get("action")
        if action == "reroute":
            return self._reroute(sp, rule)
        if action == "block":
            return self._block(sp, rule)
        if action == "unblock":
            return self._unblock(sp, rule)
        return False, "unknown action %r (use reroute/block/unblock)" % action

    def _reroute(self, sp, rule):
        src, dst = rule.get("src_mac"), rule.get("dst_mac")
        path = rule.get("path")
        if src not in sp.hosts or dst not in sp.hosts:
            return False, "src_mac or dst_mac is not a known host"
        if (not isinstance(path, list) or len(path) < 1
                or not all(isinstance(x, int) for x in path)):
            return False, "path must be a list of switch ids"
        if len(set(path)) != len(path):
            return False, "path contains a loop"
        if path[0] != sp.hosts[src][0] or path[-1] != sp.hosts[dst][0]:
            return False, "path must start at src host's switch and end at dst host's switch"
        for a, b in zip(path, path[1:]):
            if not sp.G.has_edge(a, b):
                return False, "no live link between s%s and s%s" % (a, b)
        if any(p not in sp.datapaths for p in path):
            return False, "path uses a switch that is not connected"
        ok, msg = self.sandbox_reroute(sp, path)
        if not ok:
            return False, "sandbox: " + msg
        self._install(sp, path, dst, sp.hosts[dst][1])
        self._install(sp, list(reversed(path)), src, sp.hosts[src][1])
        return True, "reroute installed on path %s (%s)" % (path, msg)

    def _install(self, sp, path, dst_mac, last_port):
        for i, dpid in enumerate(path):
            dp = sp.datapaths[dpid]
            parser = dp.ofproto_parser
            out = last_port if i == len(path) - 1 else sp.G[dpid][path[i + 1]][dpid]
            sp.add_flow(dp, REROUTE_PRIORITY,
                        parser.OFPMatch(eth_dst=dst_mac),
                        [parser.OFPActionOutput(out)])

    def _block(self, sp, rule):
        mac = str(rule.get("src_mac", "")).lower()
        if not MAC_RE.match(mac):
            return False, "src_mac is not a valid MAC address"
        if mac not in sp.hosts:
            return False, "src_mac is not a known host"
        if len(self.blocked | {mac}) >= len(sp.hosts):
            return False, "refusing to block every host"
        ok, msg = self.sandbox_block(sp, mac, bool(rule.get("force")))
        if not ok:
            return False, "sandbox: " + msg
        for dp in sp.datapaths.values():
            parser = dp.ofproto_parser
            sp.add_flow(dp, BLOCK_PRIORITY, parser.OFPMatch(eth_src=mac), [])
        self.blocked.add(mac)
        return True, "blocked traffic from %s on all switches" % mac

    def _unblock(self, sp, rule):
        mac = str(rule.get("src_mac", "")).lower()
        if mac not in self.blocked:
            return False, "that MAC is not currently blocked"
        for dp in sp.datapaths.values():
            ofp, parser = dp.ofproto, dp.ofproto_parser
            dp.send_msg(parser.OFPFlowMod(
                datapath=dp, command=ofp.OFPFC_DELETE_STRICT,
                priority=BLOCK_PRIORITY, out_port=ofp.OFPP_ANY,
                out_group=ofp.OFPG_ANY, match=parser.OFPMatch(eth_src=mac)))
        self.blocked.discard(mac)
        return True, "unblocked %s" % mac

    # ---------- port statistics ----------
    def _poll(self):
        while True:
            sp = self.sp()
            if sp:
                for dp in list(sp.datapaths.values()):
                    dp.send_msg(dp.ofproto_parser.OFPPortStatsRequest(
                        dp, 0, dp.ofproto.OFPP_ANY))
            hub.sleep(POLL_SECONDS)
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply(self, ev):
        dpid = ev.msg.datapath.id
        now = time.time()

        for st in ev.msg.body:
            if st.port_no > 0xffffff00:
                continue

            key = (dpid, st.port_no)

            self.packet_totals["received"] += 0
            self.packet_totals["transmitted"] += 0

            if key in self.last:
                old = self.last[key]
                prx, ptx, prxp, ptxp, pt = old

                dt = max(now - pt, 0.001)

                rx = (st.rx_bytes - prx) / dt
                tx = (st.tx_bytes - ptx) / dt

                self.rx.setdefault(dpid, {})[st.port_no] = round(rx, 1)
                self.tx.setdefault(dpid, {})[st.port_no] = round(tx, 1)
                self.rates.setdefault(dpid, {})[st.port_no] = round(rx + tx, 1)
                rx_packets = max(0, st.rx_packets - prxp)
                tx_packets = max(0, st.tx_packets - ptxp)

                self.packet_totals["received"] += rx_packets
                self.packet_totals["transmitted"] += tx_packets

            self.last[key] = (
                st.rx_bytes,
                st.tx_bytes,
                st.rx_packets,
                st.tx_packets,
                now
            )

    # ---------- state snapshot ----------
    def build_state(self):
        sp = self.sp()
        if sp is None:
            return {"error": "shortest-path app not running"}

        links, link_load, congested = [], [], []
        for s, d in sp.G.edges():
            links.append({"src": s, "dst": d,
                          "src_port": sp.G[s][d][s], "dst_port": sp.G[s][d][d]})
            ld = self.link_load(sp, s, d)
            name = "%s-%s" % (s, d)
            link_load.append({"link": name, "bytes_per_sec": ld})
            if ld > THRESHOLD_BPS:
                congested.append(name)

        hosts = {m: {"switch": l[0], "port": l[1]} for m, l in sp.hosts.items()}

        host_traffic = {}
        for m in sp.hosts:
            sent, recv = self.host_sent_recv(sp, m)
            host_traffic[m] = {"sent_bps": sent, "recv_bps": recv}
        heavy = sorted((m for m, t in host_traffic.items()
                        if t["sent_bps"] > THRESHOLD_BPS),
                       key=lambda m: -host_traffic[m]["sent_bps"])

        paths, dead = {}, []
        for a in sp.hosts:
            for b in sp.hosts:
                if a != b:
                    try:
                        p = nx.shortest_path(sp.G, sp.hosts[a][0], sp.hosts[b][0])
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        p = None
                        dead.append("%s->%s" % (a, b))
                    paths["%s->%s" % (a, b)] = p

        alerts = []
        for m in heavy:
            t = host_traffic[m]
            alerts.append("HEAVY SENDER %s sends %.0f B/s, receives %.0f B/s"
                          % (m, t["sent_bps"], t["recv_bps"]))
        for c in congested:
            alerts.append("CONGESTED LINK s%s" % c)
        for d in dead:
            alerts.append("NO PATH %s" % d)

        return {"switches": sorted(sp.G.nodes()), "links": links,
                "hosts": hosts, "paths": paths,
                "blocked": sorted(self.blocked),
                "host_traffic": host_traffic,
                "link_load": link_load,
                "heavy_hosts": heavy,
                "congested_links": congested,
                "alerts": alerts,
                "port_load_bytes_per_sec": {str(k): v for k, v in self.rates.items()},
                "packet_totals": dict(self.packet_totals),
                "heavy_threshold": THRESHOLD_BPS}
