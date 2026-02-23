"""Tests for GraphDiffer."""

from atlas_sdk.enums import EdgeType, NodeType
from atlas_sdk.models.edges import Edge
from atlas_sdk.models.graph import CICDGraph
from atlas_sdk.models.nodes import PipelineNode, JobNode, StageNode

from atlas_graph.differ import GraphDiffer, GraphDiff


def test_identical_graphs_no_changes():
    g1 = CICDGraph(name="CI")
    g1.add_node(PipelineNode(name="Pipeline"))
    g1.add_node(JobNode(name="Build"))

    g2 = CICDGraph(name="CI")
    g2.add_node(PipelineNode(name="Pipeline"))
    g2.add_node(JobNode(name="Build"))

    differ = GraphDiffer()
    diff = differ.diff(g1, g2)

    assert diff.has_changes is False
    assert diff.total_changes == 0


def test_added_node_detected():
    g1 = CICDGraph(name="CI v1")
    g1.add_node(PipelineNode(name="Pipeline"))

    g2 = CICDGraph(name="CI v2")
    g2.add_node(PipelineNode(name="Pipeline"))
    g2.add_node(JobNode(name="Deploy"))

    differ = GraphDiffer()
    diff = differ.diff(g1, g2)

    assert diff.added_nodes == 1
    assert diff.node_changes[0].node_name == "Deploy"
    assert diff.node_changes[0].change_type == "added"


def test_removed_node_detected():
    g1 = CICDGraph(name="CI v1")
    g1.add_node(PipelineNode(name="Pipeline"))
    g1.add_node(JobNode(name="OldJob"))

    g2 = CICDGraph(name="CI v2")
    g2.add_node(PipelineNode(name="Pipeline"))

    differ = GraphDiffer()
    diff = differ.diff(g1, g2)

    assert diff.removed_nodes == 1
    assert diff.node_changes[0].node_name == "OldJob"


def test_modified_node_detected():
    g1 = CICDGraph(name="CI")
    n1 = JobNode(name="Build", metadata={"timeout": 30})
    g1.add_node(n1)

    g2 = CICDGraph(name="CI")
    n2 = JobNode(name="Build", metadata={"timeout": 60})
    g2.add_node(n2)

    differ = GraphDiffer()
    diff = differ.diff(g1, g2)

    assert len(diff.node_changes) == 1
    assert diff.node_changes[0].change_type == "modified"


def test_edge_changes_detected():
    p1 = PipelineNode(name="Pipeline")
    j1 = JobNode(name="Build")

    g1 = CICDGraph(name="CI")
    g1.add_node(p1)
    g1.add_node(j1)

    g2 = CICDGraph(name="CI")
    g2.add_node(PipelineNode(name="Pipeline"))
    g2.add_node(JobNode(name="Build"))
    g2.add_edge(Edge(edge_type=EdgeType.CALLS, source_node_id=p1.id, target_node_id=j1.id))

    differ = GraphDiffer()
    diff = differ.diff(g1, g2)

    assert len(diff.edge_changes) == 1
    assert diff.edge_changes[0].change_type == "added"
