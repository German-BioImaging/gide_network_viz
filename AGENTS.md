# GIDE network viz

Network of the FoundingGIDE metadata (`gide_metadata_combined.ttl`, from
github.com/foundingGIDE/gide-data-deliverable). Publisher nodes are pinned to the
corners of a regular N-gon; everything else is force-laid-out once, offline. The viewer is
static (positions never change in the browser). Built for a presentation.

## Run

```sh
python3 build_graph.py          # TTL -> graph.json + class_counts.csv (needs rdflib)
npm install && node layout.mjs  # graph.json -> positions.json (d3-force, ~3 min)
python3 -m http.server          # then open http://localhost:8000
```

## Files

- `build_graph.py`: RDF → graph + per-class counts. Change it to change *what* is in the graph.
- `layout.mjs`: the force layout, run once. Change it to change *where* nodes go.
- `index.html`: static d3 v7 canvas viewer. Change it to change *how* the graph looks.
- `graph.json`, `positions.json`, `class_counts.csv`: generated files. Don't edit them by hand.

## Parameters

Each parameter is one decision. `where` says which file and line of code sets it.

```yaml
parameters:
  # --- data: what becomes the graph (build_graph.py) ---
  input_ttl: gide_metadata_combined.ttl
  anchor_predicate: schema:publisher        # its objects are the polygon corners
  node_rule: every IRI / blank node         # literals are only used as labels...
  literal_nodes: [schema:keywords]          # ...except these, which become nodes
  keyword_normalization: strip + lowercase  # merges case variants
  dropped_predicates: [rdf:type]            # the type is stored as the node class, not an edge
  multi_typed_class: first alphabetically   # the counts table counts every class
  untyped_class: obo prefix (NCBITaxon, FBbi, CLO) | "ro-crate" | "Untyped"
  publisher_attribution: >                  # also used for "shared" and for colour by publisher
    follow links out from each dataset, never passing through other datasets or publishers;
    nodes that point *to* a dataset (e.g. RO-Crate CreativeWork) also belong to its publisher
  shared_definition: reached by >= 2 publishers

  # --- layout (layout.mjs, pre-run; the browser never moves nodes) ---
  polygon_radius: 600                       # POLY_R
  polygon_rotation: flat bottom edge if N is even, vertex at top if N is odd   # rot
  placement_rule: >                         # the main decision of the layout
    nodes reached by exactly 1 publisher (incl. all datasets) go OUTSIDE the polygon, near that corner;
    nodes reached by >= 2 publishers stay INSIDE, near the centroid of their publishers' corners
  outside_target: corner * 2.5              # OUT_R
  inside_target: publishers' corner centroid * 0.8
  boundary_gap: unique >= 1.15 * edge, shared <= 0.9 * edge   # hard constraint each tick (polygonForce: OUT, IN)
  target_strength: 0.02                     # forceX / forceY towards the target
  initial_position: target, +-150 jitter
  layout_seed: 42                           # seeded LCG, same output on every run
  pre_run_ticks: 400                        # TICKS
  velocity_decay: 0.6
  link_distance: 20
  link_strength: 1 / min(degree of the two ends)
  charge_strength: -12                      # theta 1.2, distanceMax 600

  # --- appearance (index.html) ---
  node_radius: R_MIN + (R_MAX - R_MIN) * tanh(degree / K)   # rises fast, then levels off; full-graph degree
  R_MIN: 1.5
  R_MAX: 12
  K: 8
  inside_size_factor: 2                     # INSIDE_X: inside nodes are 2x outside nodes
  publisher_radius: 36                      # R_PUB (independent of INSIDE_X)
  legend_classes: [Person, Keyword, Organization, Taxon, ScholarlyArticle, Dataset, Grant, DefinedTerm]  # LEGEND
  others_colour: "#bab0ab"                  # every other class, one checkbox
  publisher_colours: {IDR: "#d7261e" red, SSBD database + repository: "#f39800" orange, BIA: "#8cc63f" light green}  # logo colours, keyed by IRI; labels use a darker shade
  outside_alpha: 0.35                       # OUTSIDE_ALPHA
  edge_alpha: {outside-outside: 0.04, touching inside/publisher: 0.15}
  polygon_outline: dashed grey
  publisher_labels: bold, publisher colour, white halo, 22px on screen at any zoom (LABEL_PX); above top corners, below bottom ones, extending outward
  draw_order: edges, outside nodes, inside nodes (small to large), hover edges, publishers
  panel: [Classes, Publishers, View, Export]  # nothing else
  default_view: whole graph centred and fitted to the window; back via "Reset view", key 0/Home, or double-click empty space
  class_toggle: hide/show only, never re-lays out; "All" checkbox shows/hides every class (half-checked when mixed)
  interactive: inside nodes + publishers only (hover tooltip + edge highlight, double-click opens IRI); zoom/pan everywhere

  # --- output ---
  export_png_scale: 3
  export_svg: current view, one <path> per edge-alpha group
  counts_output: class_counts.csv           # unique entities per class x publisher + shared + total
```

## Known data quirks

- BIA uses the misspelled class `QuantitiveValue` (in its own namespace). The other publishers use `schema:QuantitativeValue`.
- No LabProtocol or BioSample is shared across publishers, because each one has a local UUID. The only links between publishers are keywords, DefinedTerm, articles, orgs, taxa and ORCID people.
- The layout takes about 3 min (the polygon constraint runs for 23k nodes x 400 ticks). Rerun it only when graph.json or layout parameters change.
