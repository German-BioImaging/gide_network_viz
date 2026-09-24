"""TTL -> graph.json (for index.html) + class_counts.csv (unique entities per class, per publisher and total)."""
import csv
import json
from collections import defaultdict, deque

from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

SDO = Namespace("http://schema.org/")
DWC = Namespace("http://rs.tdwg.org/dwc/terms/")
g = Graph().parse("gide_metadata_combined.ttl")


def local(u):
    return str(u).rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def node_class(n):
    if isinstance(n, Literal):
        return "Keyword"
    types = sorted(local(t) for t in g.objects(n, RDF.type))
    if types:
        return types[0]  # ponytail: first class alphabetically when multi-typed; counts table uses all
    s = str(n)
    if "obolibrary.org/obo/" in s:
        return local(s).split("_")[0]  # NCBITaxon, FBbi, ...
    return "ro-crate" if "w3id.org/ro/crate" in s else "Untyped"


def label(n):
    if isinstance(n, Literal):
        return str(n)
    for p in (SDO.name, DWC.scientificName, SDO.identifier):
        v = g.value(n, p)
        if v is not None:
            return str(v)
    return local(n) if isinstance(n, URIRef) else "_"


datasets = set(g.subjects(RDF.type, SDO.Dataset))

# edges: all non-literal objects + keyword literals
edges = []
for s, p, o in g:
    if p == RDF.type:
        continue
    if isinstance(o, Literal) and p != SDO.keywords:
        continue
    o = Literal(str(o).strip().lower()) if isinstance(o, Literal) else o  # merge keyword case variants
    edges.append((s, local(p), o))

pub_of = {d: list(g.objects(d, SDO.publisher)) for d in datasets}
assert all(len(v) == 1 for v in pub_of.values()), "dataset without exactly one publisher"
pub_of = {d: v[0] for d, v in pub_of.items()}
publishers = sorted(set(pub_of.values()))
print(f"{len(publishers)} publishers:", [str(p) for p in publishers])

# which publishers reach each entity (BFS from datasets, not crossing publishers / other datasets)
out = defaultdict(list)
for s, _, o in edges:
    out[s].append(o)
    if o in datasets and s not in datasets:
        out[o].append(s)  # things *about* a dataset (e.g. RO-Crate CreativeWork) belong to its publisher
reached = defaultdict(set)
for d, pub in pub_of.items():
    seen, q = {d}, deque([d])
    while q:
        for m in out[q.popleft()]:
            if m not in seen and m not in datasets and m not in publishers:
                seen.add(m)
                q.append(m)
    for m in seen:
        reached[m].add(pub)
for p in publishers:
    reached[p].add(p)

# ---- class counts (entity counted once per class it has) ----
nodes = {n for s, _, o in edges for n in (s, o)}
classes_of = {n: ([local(t) for t in g.objects(n, RDF.type)] or [node_class(n)]) for n in nodes}
pub_names = [label(p) if g.value(p, SDO.name) else str(p) for p in publishers]
rows = defaultdict(lambda: defaultdict(int))
for n in nodes:
    for c in classes_of[n]:
        rows[c]["total"] += 1
        for p in reached[n]:
            rows[c][str(p)] += 1
        if len(reached[n]) > 1:
            rows[c]["shared (>=2 publishers)"] += 1
cols = [str(p) for p in publishers] + ["shared (>=2 publishers)", "total"]
with open("class_counts.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["class"] + pub_names + cols[-2:])
    for c in sorted(rows, key=lambda c: -rows[c]["total"]):
        w.writerow([c] + [rows[c][k] for k in cols])
    w.writerow(["ALL ENTITIES"] + [sum(1 for n in nodes if k == "total" or (k in map(str, reached[n])) or (k.startswith("shared") and len(reached[n]) > 1)) for k in cols])

short = [local(p) or str(p) for p in publishers]
print(f"\n{'class':<28}" + "".join(f"{h[:14]:>15}" for h in short + ["shared", "total"]))
for c in sorted(rows, key=lambda c: -rows[c]["total"]):
    print(f"{c:<28}" + "".join(f"{rows[c][k]:>15}" for k in cols))

# ---- graph.json ----
ids = {n: i for i, n in enumerate(sorted(nodes, key=str))}
deg = defaultdict(int)
for s, _, o in edges:
    deg[s] += 1
    deg[o] += 1
pubidx = {p: i for i, p in enumerate(publishers)}
json_nodes = []
for n, i in ids.items():
    d = {"id": i, "c": node_class(n), "l": label(n)[:120], "k": deg[n],
         "p": sorted(pubidx[p] for p in reached[n])}
    if n in pubidx:
        d["pub"] = pubidx[n]
    if isinstance(n, URIRef):
        d["u"] = str(n)
    json_nodes.append(d)
json_links = [[ids[s], ids[o]] for s, _, o in edges]
with open("graph.json", "w") as f:
    json.dump({"publishers": [str(p) for p in publishers], "nodes": json_nodes, "links": json_links}, f, separators=(",", ":"))
print(f"\ngraph.json: {len(json_nodes)} nodes, {len(json_links)} links")
