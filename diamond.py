from mininet.topo import Topo

class Diamond(Topo):
    def build(self):
        s1, s2, s3, s4 = [self.addSwitch(f's{i}') for i in range(1, 5)]
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        self.addLink(h1, s1)
        self.addLink(h2, s4)
        self.addLink(s1, s2)
        self.addLink(s2, s4)
        self.addLink(s1, s3)
        self.addLink(s3, s4)

topos = {'diamond': Diamond}
