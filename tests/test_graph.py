"""Unit tests for atlas-graph — builder, export, doc intelligence."""

import json

import pytest

from atlas_sdk.enums import DocType, EdgeType, NodeType, Platform
from atlas_sdk.models.edges import Edge
from atlas_sdk.models.graph import CICDGraph
from atlas_sdk.models.nodes import (
    DocFileNode,
    EnvironmentNode,
    JobNode,
    PipelineNode,
    SecretRefNode,
    StageNode,
    StepNode,
)

from atlas_graph.builder import GraphBuilder
from atlas_graph.doc_intel import DocScore, detect_doc_files, score_documentation
from atlas_graph.export import export_dict, export_dot, export_graphml, export_json


# ── Builder tests ─────────────────────────────────────────────────────


class TestGraphBuilder:
    def test_basic_build(self):
        builder = GraphBuilder(name="test", platform=Platform.JENKINS)
        p = PipelineNode(name="build")
        j = JobNode(name="compile")
        builder.add_nodes([p, j])
        builder.add_edges([
            Edge(edge_type=EdgeType.CALLS, source_node_id=p.id, target_node_id=j.id),
        ])
        graph = builder.build()

        assert graph.name == "test"
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_deduplication(self):
        builder = GraphBuilder(name="test")
        p1 = PipelineNode(name="build")
        p2 = PipelineNode(name="build")  # same name+type
        builder.add_nodes([p1, p2])
        graph = builder.build()
        assert len(graph.nodes) == 1

    def test_edge_validation(self):
        builder = GraphBuilder(name="test")
        p = PipelineNode(name="build")
        builder.add_nodes([p])
        # Edge pointing to non-existent node
        builder.add_edges([
            Edge(edge_type=EdgeType.CALLS, source_node_id=p.id, target_node_id="nonexistent"),
        ])
        graph = builder.build()
        assert len(graph.edges) == 0  # invalid edge skipped

    def test_from_parse_result(self):
        p = PipelineNode(name="build")
        s = StageNode(name="test")
        edge = Edge(edge_type=EdgeType.CALLS, source_node_id=p.id, target_node_id=s.id)

        graph = GraphBuilder.from_parse_result(
            name="quick", nodes=[p, s], edges=[edge], platform=Platform.GITLAB,
        )
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert graph.platform == Platform.GITLAB


# ── Export tests ──────────────────────────────────────────────────────


class TestExport:
    def _make_graph(self) -> CICDGraph:
        graph = CICDGraph(name="test-export", platform=Platform.JENKINS)
        p = PipelineNode(name="build", platform=Platform.JENKINS)
        s = StageNode(name="compile", platform=Platform.JENKINS)
        graph.add_node(p)
        graph.add_node(s)
        graph.add_edge(Edge(
            edge_type=EdgeType.CALLS,
            source_node_id=p.id,
            target_node_id=s.id,
        ))
        return graph

    def test_export_json(self):
        graph = self._make_graph()
        result = export_json(graph)
        data = json.loads(result)
        assert data["name"] == "test-export"
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

    def test_export_dict(self):
        graph = self._make_graph()
        data = export_dict(graph)
        assert isinstance(data, dict)
        assert data["name"] == "test-export"

    def test_export_graphml(self):
        graph = self._make_graph()
        xml = export_graphml(graph)
        assert '<?xml version="1.0"' in xml
        assert "<graphml" in xml
        assert "<node " in xml
        assert "<edge " in xml
        assert "edge_type" in xml

    def test_export_dot(self):
        graph = self._make_graph()
        dot = export_dot(graph)
        assert "digraph" in dot
        assert "test-export" in dot
        assert "->" in dot
        assert "calls" in dot

    def test_graphml_escaping(self):
        graph = CICDGraph(name="test")
        graph.add_node(PipelineNode(name='build<>&"special'))
        xml = export_graphml(graph)
        # Node type data should be present and properly formed
        assert "pipeline" in xml
        assert "<node " in xml

    def test_dot_escaping(self):
        graph = CICDGraph(name='test "quoted"')
        dot = export_dot(graph)
        assert '\\"' in dot


# ── Doc intelligence tests ───────────────────────────────────────────


class TestDocIntel:
    def test_detect_readme(self):
        files = detect_doc_files(["README.md", "src/main.py"])
        assert len(files) == 1
        assert files[0][1] == DocType.README

    def test_detect_multiple(self):
        files = detect_doc_files([
            "README.md",
            "ARCHITECTURE.md",
            "RUNBOOK.md",
            "SECURITY.md",
            "CODEOWNERS",
            "docs/guide.md",
            "adr/001-decision.md",
        ])
        types = [f[1] for f in files]
        assert DocType.README in types
        assert DocType.ARCHITECTURE in types
        assert DocType.RUNBOOK in types
        assert DocType.SECURITY_POLICY in types
        assert DocType.CODEOWNERS in types
        assert DocType.DOCS_DIR in types
        assert DocType.ADR in types

    def test_detect_none(self):
        files = detect_doc_files(["src/app.py", "Makefile"])
        assert len(files) == 0

    def test_score_full_coverage(self):
        graph = CICDGraph(name="test")
        for doc_type, label in [
            (DocType.README, "README.md"),
            (DocType.ARCHITECTURE, "ARCHITECTURE.md"),
            (DocType.RUNBOOK, "RUNBOOK.md"),
            (DocType.SECURITY_POLICY, "SECURITY.md"),
            (DocType.CODEOWNERS, "CODEOWNERS"),
        ]:
            graph.add_node(DocFileNode(name=label, path=label, doc_type=doc_type))

        score = score_documentation(graph)
        assert score.coverage_pct == 100.0
        assert len(score.missing) == 0

    def test_score_partial_coverage(self):
        graph = CICDGraph(name="test")
        graph.add_node(DocFileNode(name="README.md", path="README.md", doc_type=DocType.README))
        score = score_documentation(graph)
        assert score.coverage_pct == 20.0
        assert len(score.missing) == 4

    def test_drift_deploy_no_runbook(self):
        graph = CICDGraph(name="test")
        graph.add_node(EnvironmentNode(name="deploy-prod"))
        score = score_documentation(graph)
        assert len(score.drift_warnings) >= 1
        assert score.drift_score > 0

    def test_drift_secrets_no_security(self):
        graph = CICDGraph(name="test")
        graph.add_node(SecretRefNode(name="API_KEY", key="API_KEY"))
        score = score_documentation(graph)
        assert any("security" in w.lower() for w in score.drift_warnings)

    def test_no_drift_when_documented(self):
        graph = CICDGraph(name="test")
        graph.add_node(EnvironmentNode(name="deploy-staging"))
        graph.add_node(DocFileNode(name="RUNBOOK.md", path="RUNBOOK.md", doc_type=DocType.RUNBOOK))
        score = score_documentation(graph)
        assert not any("runbook" in w.lower() for w in score.drift_warnings)
