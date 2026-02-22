"""Graph builder — constructs CICDGraph from ParseResult.

Receives parsed nodes and edges from atlas-parser and assembles
them into a complete CICDGraph with deduplication and validation.
"""

from __future__ import annotations

import logging
from typing import Any

from atlas_sdk.enums import Platform
from atlas_sdk.models.edges import Edge
from atlas_sdk.models.graph import CICDGraph
from atlas_sdk.models.nodes import Node

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds a CICDGraph from parsed nodes and edges.

    Handles:
    - Node deduplication by name+type
    - Edge validation (source/target exist)
    - Graph metadata
    """

    def __init__(self, name: str, platform: Platform | None = None) -> None:
        self._graph = CICDGraph(name=name, platform=platform)
        self._node_index: dict[str, str] = {}  # "type:name" → node_id

    def add_nodes(self, nodes: list[Node]) -> None:
        """Add nodes with deduplication."""
        for node in nodes:
            key = f"{node.node_type}:{node.name}"
            if key not in self._node_index:
                self._graph.add_node(node)
                self._node_index[key] = node.id
            else:
                logger.debug("Skipping duplicate node: %s", key)

    def add_edges(self, edges: list[Edge]) -> None:
        """Add edges with validation."""
        valid_ids = {n.id for n in self._graph.nodes}
        for edge in edges:
            if edge.source_node_id in valid_ids and edge.target_node_id in valid_ids:
                self._graph.add_edge(edge)
            else:
                logger.debug(
                    "Skipping edge %s→%s: missing node(s)",
                    edge.source_node_id[:8], edge.target_node_id[:8],
                )

    def build(self) -> CICDGraph:
        """Return the constructed graph."""
        logger.info(
            "Graph '%s' built: %d nodes, %d edges",
            self._graph.name, len(self._graph.nodes), len(self._graph.edges),
        )
        return self._graph

    @classmethod
    def from_parse_result(
        cls,
        name: str,
        nodes: list[Node],
        edges: list[Edge],
        platform: Platform | None = None,
    ) -> CICDGraph:
        """Convenience: build a graph from parsed output in one call."""
        builder = cls(name=name, platform=platform)
        builder.add_nodes(nodes)
        builder.add_edges(edges)
        return builder.build()
