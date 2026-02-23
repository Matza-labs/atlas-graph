"""Graph differ — compare two CICDGraphs and produce a structured diff.

Detects added/removed/modified nodes and edges between two snapshots
of the same pipeline, enabling "what changed?" analysis.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from pydantic import BaseModel, Field

from atlas_sdk.models.graph import CICDGraph
from atlas_sdk.models.nodes import Node
from atlas_sdk.models.edges import Edge

logger = logging.getLogger(__name__)


def _new_id() -> str:
    return str(uuid4())


class NodeChange(BaseModel):
    """A change to a single node."""

    change_type: str  # added, removed, modified
    node_name: str
    node_type: str
    details: str = ""


class EdgeChange(BaseModel):
    """A change to a single edge."""

    change_type: str
    edge_type: str
    source: str
    target: str


class GraphDiff(BaseModel):
    """Structured diff between two graphs."""

    id: str = Field(default_factory=_new_id)
    before_graph_id: str
    after_graph_id: str
    before_name: str = ""
    after_name: str = ""
    node_changes: list[NodeChange] = Field(default_factory=list)
    edge_changes: list[EdgeChange] = Field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return len(self.node_changes) + len(self.edge_changes)

    @property
    def added_nodes(self) -> int:
        return sum(1 for c in self.node_changes if c.change_type == "added")

    @property
    def removed_nodes(self) -> int:
        return sum(1 for c in self.node_changes if c.change_type == "removed")

    @property
    def has_changes(self) -> bool:
        return self.total_changes > 0


class GraphDiffer:
    """Compares two CICDGraphs and produces a GraphDiff.

    Usage:
        differ = GraphDiffer()
        diff = differ.diff(old_graph, new_graph)
    """

    def diff(self, before: CICDGraph, after: CICDGraph) -> GraphDiff:
        """Compute the diff between two graphs."""
        result = GraphDiff(
            before_graph_id=before.id,
            after_graph_id=after.id,
            before_name=before.name,
            after_name=after.name,
        )

        # Index nodes by (type, name) for comparison
        before_nodes = {(n.node_type, n.name): n for n in before.nodes}
        after_nodes = {(n.node_type, n.name): n for n in after.nodes}

        # Added nodes
        for key, node in after_nodes.items():
            if key not in before_nodes:
                result.node_changes.append(NodeChange(
                    change_type="added",
                    node_name=node.name,
                    node_type=str(node.node_type),
                ))

        # Removed nodes
        for key, node in before_nodes.items():
            if key not in after_nodes:
                result.node_changes.append(NodeChange(
                    change_type="removed",
                    node_name=node.name,
                    node_type=str(node.node_type),
                ))

        # Modified nodes (same key but different metadata)
        for key in before_nodes:
            if key in after_nodes:
                b = before_nodes[key]
                a = after_nodes[key]
                if b.metadata != a.metadata:
                    result.node_changes.append(NodeChange(
                        change_type="modified",
                        node_name=a.name,
                        node_type=str(a.node_type),
                        details="metadata changed",
                    ))

        # Edge comparison
        before_edges = {(e.edge_type, e.source_node_id, e.target_node_id) for e in before.edges}
        after_edges = {(e.edge_type, e.source_node_id, e.target_node_id) for e in after.edges}

        for edge_key in after_edges - before_edges:
            result.edge_changes.append(EdgeChange(
                change_type="added",
                edge_type=str(edge_key[0]),
                source=edge_key[1][:8],
                target=edge_key[2][:8],
            ))

        for edge_key in before_edges - after_edges:
            result.edge_changes.append(EdgeChange(
                change_type="removed",
                edge_type=str(edge_key[0]),
                source=edge_key[1][:8],
                target=edge_key[2][:8],
            ))

        logger.info(
            "GraphDiff: %d node change(s), %d edge change(s)",
            len(result.node_changes), len(result.edge_changes),
        )
        return result
