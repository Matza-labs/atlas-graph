"""Graph export — JSON, GraphML, and DOT formats.

Provides multiple export formats for CICDGraph:
- JSON: full serialization for API and storage
- GraphML: for graph analysis tools (Gephi, yEd)
- DOT: for Graphviz visualization
"""

from __future__ import annotations

import json
import logging
from typing import Any

from atlas_sdk.models.graph import CICDGraph

logger = logging.getLogger(__name__)


def export_json(graph: CICDGraph, indent: int = 2) -> str:
    """Export graph as JSON string."""
    return graph.model_dump_json(indent=indent)


def export_dict(graph: CICDGraph) -> dict[str, Any]:
    """Export graph as a Python dict (JSON-serializable)."""
    return graph.model_dump(mode="json")


def export_graphml(graph: CICDGraph) -> str:
    """Export graph as GraphML XML for tools like Gephi, yEd.

    GraphML is a standard XML format for representing graphs.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphstd.org/xmlns">',
        '  <key id="node_type" for="node" attr.name="node_type" attr.type="string"/>',
        '  <key id="platform" for="node" attr.name="platform" attr.type="string"/>',
        '  <key id="edge_type" for="edge" attr.name="edge_type" attr.type="string"/>',
        f'  <graph id="{_xml_escape(graph.id)}" edgedefault="directed">',
    ]

    for node in graph.nodes:
        lines.append(f'    <node id="{_xml_escape(node.id)}">')
        lines.append(f'      <data key="node_type">{_xml_escape(str(node.node_type))}</data>')
        if node.platform:
            lines.append(f'      <data key="platform">{_xml_escape(str(node.platform))}</data>')
        lines.append(f'    </node>')

    for edge in graph.edges:
        lines.append(
            f'    <edge id="{_xml_escape(edge.id)}" '
            f'source="{_xml_escape(edge.source_node_id)}" '
            f'target="{_xml_escape(edge.target_node_id)}">'
        )
        lines.append(f'      <data key="edge_type">{_xml_escape(str(edge.edge_type))}</data>')
        lines.append(f'    </edge>')

    lines.append('  </graph>')
    lines.append('</graphml>')
    return "\n".join(lines)


def export_dot(graph: CICDGraph) -> str:
    """Export graph as DOT format for Graphviz.

    Nodes are labeled with name and type.
    Edges are labeled with edge type.
    """
    lines = [f'digraph "{_dot_escape(graph.name)}" {{']
    lines.append('  rankdir=LR;')
    lines.append('  node [shape=box, style=filled, fillcolor=lightblue];')
    lines.append('')

    for node in graph.nodes:
        label = f"{node.name}\\n({node.node_type})"
        color = _node_color(str(node.node_type))
        lines.append(
            f'  "{_dot_escape(node.id)}" '
            f'[label="{_dot_escape(label)}", fillcolor="{color}"];'
        )

    lines.append('')
    for edge in graph.edges:
        lines.append(
            f'  "{_dot_escape(edge.source_node_id)}" -> '
            f'"{_dot_escape(edge.target_node_id)}" '
            f'[label="{_dot_escape(str(edge.edge_type))}"];'
        )

    lines.append('}')
    return "\n".join(lines)


def _xml_escape(text: str) -> str:
    """Escape special characters for XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _dot_escape(text: str) -> str:
    """Escape special characters for DOT."""
    return text.replace('"', '\\"').replace("\n", "\\n")


def _node_color(node_type: str) -> str:
    """Assign color by node type for DOT export."""
    colors = {
        "pipeline": "#4CAF50",
        "job": "#2196F3",
        "stage": "#03A9F4",
        "step": "#00BCD4",
        "repository": "#FF9800",
        "artifact": "#FFC107",
        "container_image": "#9C27B0",
        "runner": "#607D8B",
        "secret_ref": "#F44336",
        "environment": "#8BC34A",
        "external_service": "#795548",
        "doc_file": "#E91E63",
    }
    return colors.get(node_type, "lightblue")
