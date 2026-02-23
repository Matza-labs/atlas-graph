"""Cross-project graph linker.

Detects dependencies between multiple CICDGraph instances by analyzing
shared artifacts, secrets, environments, container images, and triggers.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from atlas_sdk.enums import EdgeType, NodeType
from atlas_sdk.models.graph import (
    CICDGraph,
    CrossProjectEdge,
    MultiProjectGraph,
)

logger = logging.getLogger(__name__)


class CrossProjectLinker:
    """Detects and creates cross-project dependency links.

    Usage:
        linker = CrossProjectLinker()
        multi = linker.link([graph_a, graph_b, graph_c])
    """

    # Node types that can be shared across projects
    LINKABLE_TYPES = {
        NodeType.ARTIFACT,
        NodeType.CONTAINER_IMAGE,
        NodeType.SECRET_REF,
        NodeType.ENVIRONMENT,
        NodeType.EXTERNAL_SERVICE,
    }

    # Edge types that imply cross-project relationships
    TRIGGER_EDGE_TYPES = {EdgeType.TRIGGERS}

    def link(self, graphs: list[CICDGraph], name: str = "Multi-Project View") -> MultiProjectGraph:
        """Analyze multiple graphs and produce a linked MultiProjectGraph.

        Args:
            graphs: List of CICDGraph instances (one per project).
            name: Name for the resulting multi-project graph.

        Returns:
            MultiProjectGraph with detected cross-project edges.
        """
        multi = MultiProjectGraph(name=name)
        for g in graphs:
            multi.add_graph(g)

        # Build index: (node_type, normalized_name) → [(graph_id, node_id)]
        node_index: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)

        for graph in graphs:
            for node in graph.nodes:
                if node.node_type in self.LINKABLE_TYPES:
                    key = (str(node.node_type), self._normalize(node.name))
                    node_index[key].append((graph.id, node.id))

        # Create cross-edges for nodes that appear in multiple graphs
        for (node_type, _name), locations in node_index.items():
            if len(locations) < 2:
                continue

            link_type = self._link_type_for(node_type)

            # Link each pair (first occurrence is the "source", rest are "targets")
            source_graph_id, source_node_id = locations[0]
            for target_graph_id, target_node_id in locations[1:]:
                if source_graph_id == target_graph_id:
                    continue
                edge = CrossProjectEdge(
                    source_graph_id=source_graph_id,
                    source_node_id=source_node_id,
                    target_graph_id=target_graph_id,
                    target_node_id=target_node_id,
                    link_type=link_type,
                )
                multi.add_cross_edge(edge)

        # Detect cross-repo trigger edges (nodes referencing external project names)
        trigger_edges = self._detect_triggers(graphs)
        for edge in trigger_edges:
            multi.add_cross_edge(edge)

        logger.info(
            "Linked %d graphs: %d cross-project edges detected.",
            len(graphs), len(multi.cross_edges),
        )
        return multi

    def _normalize(self, name: str) -> str:
        """Normalize node names for comparison (lowercase, strip prefixes)."""
        # Strip common prefixes like "secret:", environment qualifiers, etc.
        name = name.lower().strip()
        for prefix in ("secret:", "env:", "image:"):
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name.strip()

    def _link_type_for(self, node_type: str) -> str:
        """Map node type to cross-project link type."""
        mapping = {
            str(NodeType.ARTIFACT): "shared_artifact",
            str(NodeType.CONTAINER_IMAGE): "shared_image",
            str(NodeType.SECRET_REF): "shared_secret",
            str(NodeType.ENVIRONMENT): "shared_env",
            str(NodeType.EXTERNAL_SERVICE): "shared_service",
        }
        return mapping.get(node_type, "shared_resource")

    def _detect_triggers(self, graphs: list[CICDGraph]) -> list[CrossProjectEdge]:
        """Detect trigger-based cross-project links.

        If a node in graph A has a TRIGGERS edge, and the target name
        matches a pipeline in graph B, create a cross-project trigger edge.
        """
        edges: list[CrossProjectEdge] = []

        # Index: pipeline name → (graph_id, node_id)
        pipeline_index: dict[str, tuple[str, str]] = {}
        for g in graphs:
            for n in g.nodes:
                if n.node_type == NodeType.PIPELINE:
                    pipeline_index[self._normalize(n.name)] = (g.id, n.id)

        for g in graphs:
            for e in g.edges:
                if e.edge_type not in self.TRIGGER_EDGE_TYPES:
                    continue
                target_node = g.get_node(e.target_node_id)
                if not target_node:
                    continue
                target_name = self._normalize(target_node.name)
                if target_name in pipeline_index:
                    tg_id, tn_id = pipeline_index[target_name]
                    if tg_id != g.id:
                        edges.append(CrossProjectEdge(
                            source_graph_id=g.id,
                            source_node_id=e.source_node_id,
                            target_graph_id=tg_id,
                            target_node_id=tn_id,
                            link_type="cross_trigger",
                            confidence=0.7,
                        ))

        return edges
