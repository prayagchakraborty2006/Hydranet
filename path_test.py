import networkx as nx

G = nx.Graph()
G.add_edges_from([(1, 2), (1, 3), (2, 4), (3, 4)])

print("Normal path     :", nx.shortest_path(G, 1, 4))

G.remove_edge(1, 2)   # simulates 'link s1 s2 down'
print("After s1-s2 down:", nx.shortest_path(G, 1, 4))

G.add_edge(1, 2)      # simulates 'link s1 s2 up'
print("After s1-s2 up  :", nx.shortest_path(G, 1, 4))
