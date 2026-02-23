"""Tests for the DiffSimulator."""

from atlas_sdk.enums import NodeType, Severity
from atlas_sdk.models.findings import Finding
from atlas_sdk.models.graph import CICDGraph
from atlas_sdk.models.nodes import PipelineNode, JobNode
from atlas_sdk.models.refactors import RefactorPlan, RefactorSuggestion
from atlas_sdk.models.simulation import ScoreDelta, SimulationResult

from atlas_graph.simulator import DiffSimulator


def _setup():
    """Create a simple graph with findings and a refactor plan."""
    graph = CICDGraph(name="Test CI")
    p = PipelineNode(name="Pipeline")
    j = JobNode(name="Build")
    graph.add_node(p)
    graph.add_node(j)

    findings = [
        Finding(
            rule_id="no-timeout",
            title="No timeout",
            description="Job has no timeout",
            severity=Severity.MEDIUM,
            affected_node_ids=[j.id],
        ),
        Finding(
            rule_id="unpinned-images",
            title="Unpinned",
            description="Image not pinned",
            severity=Severity.HIGH,
            affected_node_ids=[j.id],
        ),
    ]

    plan = RefactorPlan(
        name="Test CI",
        graph_id=graph.id,
        suggestions=[
            RefactorSuggestion(
                rule_id="no-timeout",
                description="Add timeout",
                before_snippet="runs-on: ubuntu",
                after_snippet="runs-on: ubuntu\ntimeout-minutes: 30",
                affected_node_ids=[j.id],
            ),
        ],
    )
    return graph, findings, plan


def test_simulation_produces_result():
    graph, findings, plan = _setup()
    sim = DiffSimulator()
    result = sim.simulate(graph, findings, plan)

    assert isinstance(result, SimulationResult)
    assert result.findings_removed == 1  # no-timeout fixed
    assert result.findings_remaining == 1  # unpinned still there


def test_score_deltas_computed():
    graph, findings, plan = _setup()
    sim = DiffSimulator()
    result = sim.simulate(graph, findings, plan)

    assert len(result.score_deltas) == 3
    metrics = {d.metric for d in result.score_deltas}
    assert metrics == {"complexity", "fragility", "maturity"}


def test_diff_preview_generated():
    graph, findings, plan = _setup()
    sim = DiffSimulator()
    result = sim.simulate(graph, findings, plan)

    assert "Diff Preview" in result.diff_preview
    assert "Add timeout" in result.diff_preview
    assert "- runs-on: ubuntu" in result.diff_preview
    assert "+ timeout-minutes: 30" in result.diff_preview


def test_score_delta_properties():
    delta = ScoreDelta(metric="fragility", before=60.0, after=40.0)
    assert delta.delta == -20.0
    assert delta.improved is True

    maturity = ScoreDelta(metric="maturity", before=30.0, after=50.0)
    assert maturity.delta == 20.0
    assert maturity.improved is True
