"""Unit tests for CrossProjectLinker."""

from atlas_sdk.enums import EdgeType, NodeType, Platform
from atlas_sdk.models.edges import Edge
from atlas_sdk.models.graph import CICDGraph, MultiProjectGraph
from atlas_sdk.models.nodes import (
    ArtifactNode,
    EnvironmentNode,
    JobNode,
    PipelineNode,
    SecretRefNode,
)

from atlas_graph.cross_project import CrossProjectLinker


def _make_graph_a() -> CICDGraph:
    """Simulates a build pipeline that produces an artifact and uses a secret."""
    g = CICDGraph(name="Build Service", platform=Platform.GITHUB_ACTIONS)
    p = PipelineNode(name="CI Build")
    j = JobNode(name="Build Job")
    art = ArtifactNode(name="my-app.jar")
    sec = SecretRefNode(name="secret:DEPLOY_KEY", key="DEPLOY_KEY")
    env = EnvironmentNode(name="staging")
    g.add_node(p)
    g.add_node(j)
    g.add_node(art)
    g.add_node(sec)
    g.add_node(env)
    g.add_edge(Edge(edge_type=EdgeType.CALLS, source_node_id=p.id, target_node_id=j.id))
    g.add_edge(Edge(edge_type=EdgeType.PRODUCES, source_node_id=j.id, target_node_id=art.id))
    return g


def _make_graph_b() -> CICDGraph:
    """Simulates a deploy pipeline that consumes the same artifact and secret."""
    g = CICDGraph(name="Deploy Service", platform=Platform.GITLAB)
    p = PipelineNode(name="CD Deploy")
    j = JobNode(name="Deploy Job")
    art = ArtifactNode(name="my-app.jar")  # Same artifact!
    sec = SecretRefNode(name="secret:DEPLOY_KEY", key="DEPLOY_KEY")  # Same secret!
    env = EnvironmentNode(name="staging")  # Same environment!
    g.add_node(p)
    g.add_node(j)
    g.add_node(art)
    g.add_node(sec)
    g.add_node(env)
    g.add_edge(Edge(edge_type=EdgeType.CALLS, source_node_id=p.id, target_node_id=j.id))
    g.add_edge(Edge(edge_type=EdgeType.CONSUMES, source_node_id=j.id, target_node_id=art.id))
    return g


def test_linker_detects_shared_artifacts():
    linker = CrossProjectLinker()
    graph_a = _make_graph_a()
    graph_b = _make_graph_b()
    multi = linker.link([graph_a, graph_b])

    assert isinstance(multi, MultiProjectGraph)
    assert len(multi.graphs) == 2
    assert multi.total_nodes == 10

    # Should detect shared artifact, shared secret, shared environment
    shared_types = {e.link_type for e in multi.cross_edges}
    assert "shared_artifact" in shared_types
    assert "shared_secret" in shared_types
    assert "shared_env" in shared_types
    assert len(multi.cross_edges) >= 3


def test_linker_no_links_for_single_graph():
    linker = CrossProjectLinker()
    graph_a = _make_graph_a()
    multi = linker.link([graph_a])

    assert len(multi.graphs) == 1
    assert len(multi.cross_edges) == 0


def test_linker_no_false_positives():
    """Two graphs with completely different nodes should produce no links."""
    g1 = CICDGraph(name="Alpha")
    g1.add_node(PipelineNode(name="Alpha Pipeline"))
    g1.add_node(ArtifactNode(name="alpha.jar"))

    g2 = CICDGraph(name="Beta")
    g2.add_node(PipelineNode(name="Beta Pipeline"))
    g2.add_node(ArtifactNode(name="beta.jar"))

    linker = CrossProjectLinker()
    multi = linker.link([g1, g2])
    assert len(multi.cross_edges) == 0
