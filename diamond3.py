from mininet.topo import Topo

class Diamond3(Topo):
    def build(self):
        s1, s2, s3, s4 = [self.addSwitch('s%d' % i) for i in range(1, 5)]
        h1 = self.addHost('h1')   # attacker
        h2 = self.addHost('h2')   # victim
        h3 = self.addHost('h3')   # legitimate user
        self.addLink(h1, s1)
        self.addLink(h3, s1)
        self.addLink(h2, s4)
        self.addLink(s1, s2)
        self.addLink(s2, s4)
        self.addLink(s1, s3)
        self.addLink(s3, s4)

topos = {'diamond3': Diamond3}
