"""
abuse_sentinel.py - Module 3: Abuse-Ring Sentinel (Weighted Graph Scoring)

Finds clusters of customers sharing a device fingerprint, IP address, or
delivery address -- a defensive signal for coordinated multi-accounting
abuse (promo stacking, return fraud). Evaluated against seeded ring
membership ground truth from the generator.

Previously this was pure connected-components with a hard size cutoff --
binary in/out, no ranking, no weighting, so a legitimate shared office
address produced the exact same signal as a real abuse ring. This version:

  1. Weights edges by identifier type (shared device > shared IP > shared
     address, since IP/address are far more likely to be legitimately
     shared -- a family's home WiFi, a co-working space).
  2. Runs Louvain community detection (modularity-based) on the weighted
     customer-customer projection, so a big loosely-connected component
     gets split into its actual dense sub-rings instead of being treated as
     one uniform blob.
  3. Computes a continuous per-customer risk score via Personalized
     PageRank seeded from customers with a known-fraud transaction, so risk
     is a spectrum rather than a binary in/out at a hard cluster-size cutoff.
  4. Surfaces cluster density (edges / possible edges) as a confidence
     signal -- a cluster where everyone shares device AND IP is a much
     stronger signal than one that only shares a city-level address pattern.
"""
from itertools import combinations

import networkx as nx
import pandas as pd
from networkx.algorithms.community import louvain_communities


class AbuseRingSentinel:
    # Shared device is the strongest signal (hardest to share legitimately);
    # shared IP is weaker (same household/office WiFi is common and benign);
    # shared address is weakest (roommates, family, PG accommodation).
    EDGE_WEIGHTS = {"device_id": 3.0, "ip_address": 1.5, "delivery_address": 1.0}
    IDENT_PREFIX = {"device_id": "DEV", "ip_address": "IP", "delivery_address": "ADDR"}

    def __init__(self, min_cluster_size: int = 3, seed: int = 42):
        self.min_cluster_size = min_cluster_size
        self.seed = seed
        self.graph = nx.Graph()            # bipartite customer<->identifier (viz + evidence breakdown)
        self.customer_graph = nx.Graph()   # weighted customer-customer projection (scoring)
        self.clusters = []
        self.flagged_customers = set()
        self.risk_scores_ = {}             # customer_id -> continuous risk score in [0, 1]
        self.metrics_ = None

    def _build_graphs(self, df_txns: pd.DataFrame, df_customers: pd.DataFrame):
        self.graph = nx.Graph()
        self.graph.add_nodes_from(df_customers.customer_id)
        self.customer_graph = nx.Graph()
        self.customer_graph.add_nodes_from(df_customers.customer_id)

        for key_col, prefix in self.IDENT_PREFIX.items():
            weight = self.EDGE_WEIGHTS[key_col]
            for key_val, grp in df_txns.groupby(key_col):
                custs = grp.customer_id.unique()
                if len(custs) <= 1:
                    continue
                node = f"{prefix}:{key_val}"
                self.graph.add_node(node, node_type=prefix.lower())
                for c in custs:
                    self.graph.add_edge(c, node, weight=weight)
                # Weighted customer-customer projection: every pair sharing
                # this identifier gets (or accumulates) an edge. Accumulating
                # weight across multiple shared identifier types is exactly
                # the "tight ring" signal -- two customers sharing device AND
                # IP end up with a much heavier edge than one sharing only
                # a loose address pattern.
                for a, b in combinations(sorted(custs), 2):
                    if self.customer_graph.has_edge(a, b):
                        self.customer_graph[a][b]["weight"] += weight
                        self.customer_graph[a][b]["shared_types"].add(prefix)
                    else:
                        self.customer_graph.add_edge(a, b, weight=weight, shared_types={prefix})

    def _compute_risk_scores(self, df_txns: pd.DataFrame):
        """Personalized PageRank seeded from customers with at least one
        known-fraud transaction -- risk propagates through the weighted
        graph from known-bad seeds, giving every customer a continuous
        score rather than a binary cluster membership flag."""
        fraud_customers = set(df_txns.loc[df_txns.is_fraud, "customer_id"].unique())
        n_nodes = self.customer_graph.number_of_nodes()
        if not fraud_customers or n_nodes == 0:
            self.risk_scores_ = {c: 0.0 for c in self.customer_graph.nodes}
            return

        personalization = {c: (1.0 if c in fraud_customers else 0.0) for c in self.customer_graph.nodes}
        ppr = nx.pagerank(self.customer_graph, alpha=0.85, personalization=personalization, weight="weight")

        values = list(ppr.values())
        lo, hi = min(values), max(values)
        span = (hi - lo) or 1.0
        # Min-max normalize to [0, 1] so the score reads as "relative risk
        # within this population" rather than a raw PageRank mass (which is
        # tiny and hard to interpret with thousands of nodes).
        self.risk_scores_ = {c: round((v - lo) / span, 4) for c, v in ppr.items()}

    def fit_and_evaluate(self, df_txns: pd.DataFrame, df_customers: pd.DataFrame):
        self._build_graphs(df_txns, df_customers)
        self._compute_risk_scores(df_txns)

        self.clusters = []
        flagged = set()
        cluster_idx = 0
        for comp in nx.connected_components(self.customer_graph):
            if len(comp) < 2:
                continue
            subgraph = self.customer_graph.subgraph(comp)
            # Louvain modularity-based community detection SEPARATES dense
            # sub-rings within one loosely-connected blob instead of
            # treating the whole component as a single ring.
            communities = louvain_communities(subgraph, weight="weight", seed=self.seed)
            for community in communities:
                if len(community) < self.min_cluster_size:
                    continue
                members = sorted(community)
                comm_subgraph = subgraph.subgraph(members)
                n = len(members)
                possible_edges = n * (n - 1) / 2
                density = round(comm_subgraph.number_of_edges() / possible_edges, 3) if possible_edges else 0.0

                # Shared identifiers touching >=2 members of this community.
                shared = set()
                for m in members:
                    for nbr in self.graph.neighbors(m):
                        if not nbr.startswith("CUST_"):
                            neighbor_members = {c for c in self.graph.neighbors(nbr) if c.startswith("CUST_")}
                            if len(neighbor_members & set(members)) >= 2:
                                shared.add(nbr)

                avg_risk = round(sum(self.risk_scores_.get(m, 0.0) for m in members) / n, 4)
                confidence = "High" if density >= 0.66 else ("Medium" if density >= 0.33 else "Low")

                self.clusters.append({
                    "cluster_id": f"RING_{cluster_idx:03d}",
                    "customer_count": n,
                    "customers": members,
                    "shared_identifiers": sorted(shared),
                    "density": density,
                    "confidence": confidence,
                    "avg_risk_score": avg_risk,
                    "detection_method": "louvain_community_weighted_graph",
                })
                flagged.update(members)
                cluster_idx += 1

        self.clusters.sort(key=lambda c: (c["avg_risk_score"], c["customer_count"]), reverse=True)
        self.flagged_customers = flagged

        truth = set(df_customers[df_customers.in_abuse_ring].customer_id)
        all_custs = set(df_customers.customer_id)
        tp = len(flagged & truth)
        fp = len(flagged - truth)
        fn = len(truth - flagged)
        tn = len(all_custs - flagged - truth)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

        true_ring_ids = set(df_customers[df_customers.ring_id >= 0].ring_id.unique())
        recovered = 0
        for rid in true_ring_ids:
            members = set(df_customers[df_customers.ring_id == rid].customer_id)
            if any(members.issubset(set(c["customers"])) for c in self.clusters):
                recovered += 1

        self.metrics_ = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            "n_clusters_flagged": len(self.clusters),
            "n_customers_flagged": len(flagged),
            "n_true_ring_members": len(truth),
            "n_customers_total": len(all_custs),
            "true_rings_total": len(true_ring_ids),
            "true_rings_recovered_intact": recovered,
            "scoring_method": "weighted_edges_louvain_community_personalized_pagerank",
            "edge_weights": self.EDGE_WEIGHTS,
            # Not a train/test split -- graph connectivity is evaluated over
            # the full customer graph against seeded ring-membership ground truth.
            "evaluation_protocol": "full_graph_vs_seeded_ground_truth",
        }
        return self.metrics_

    def inspect_customer(self, customer_id: str):
        if not self.graph.has_node(customer_id):
            return {"in_ring": False, "cluster_size": 0, "shared_entities": [],
                     "evidence_breakdown": {"shared_device": 0, "shared_ip": 0, "shared_address": 0},
                     "risk_score": 0.0, "cluster_density": None, "confidence": "None",
                     "recommended_action": "No shared-identity signal found"}

        comp = nx.node_connected_component(self.graph, customer_id)
        cust_nodes = [n for n in comp if n.startswith("CUST_")]
        shared = [n for n in comp if not n.startswith("CUST_")]

        matching_cluster = next((c for c in self.clusters if customer_id in c["customers"]), None)
        in_ring = matching_cluster is not None
        cluster_size = matching_cluster["customer_count"] if matching_cluster else len(cust_nodes)
        density = matching_cluster["density"] if matching_cluster else None
        confidence = matching_cluster["confidence"] if matching_cluster else "None"
        risk_score = self.risk_scores_.get(customer_id, 0.0)

        # Break down WHICH identifier type actually connects this customer to
        # others -- "shared an IP with 3 accounts" is a very different signal
        # from "shared a device with 3 accounts", and collapsing them into one
        # opaque cluster hides that.
        breakdown = {"shared_device": 0, "shared_ip": 0, "shared_address": 0}
        for node in shared:
            if node.startswith("DEV:"):
                breakdown["shared_device"] += 1
            elif node.startswith("IP:"):
                breakdown["shared_ip"] += 1
            elif node.startswith("ADDR:"):
                breakdown["shared_address"] += 1

        if in_ring:
            action = f"Recommend manual identity verification before approving promo/return ({confidence.lower()}-confidence, density {density})"
        elif risk_score >= 0.5:
            action = "Below ring size cutoff, but elevated PageRank risk score -- consider light-touch review"
        else:
            action = "No shared-identity signal found"

        return {
            "in_ring": in_ring,
            "cluster_size": cluster_size,
            "shared_entities": shared,
            "evidence_breakdown": breakdown,
            "risk_score": risk_score,
            "cluster_density": density,
            "confidence": confidence,
            "recommended_action": action,
        }

    def get_cytoscape_elements(self, max_clusters: int = 4):
        elements = []
        for cluster in self.clusters[:max_clusters]:
            cid = cluster["cluster_id"]
            for c in cluster["customers"]:
                elements.append({"data": {"id": c, "label": c, "type": "customer", "cluster": cid,
                                           "risk_score": self.risk_scores_.get(c, 0.0)}})
            for ident in cluster["shared_identifiers"]:
                ntype = "device" if ident.startswith("DEV:") else ("ip" if ident.startswith("IP:") else "address")
                elements.append({"data": {"id": ident, "label": ident.split(":", 1)[1][:18], "type": ntype, "cluster": cid}})
                for c in cluster["customers"]:
                    if self.graph.has_edge(c, ident):
                        elements.append({"data": {"id": f"{c}__{ident}", "source": c, "target": ident}})
        return elements
