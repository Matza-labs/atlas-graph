"""Diff simulation engine — previews refactored graphs without modifying files.

Takes a CICDGraph and a RefactorPlan, simulates the changes, and produces
a SimulationResult with projected scores and a diff preview.
"""

from __future__ import annotations

import logging
from copy import deepcopy

from atlas_sdk.models.graph import CICDGraph
from atlas_sdk.models.refactors import RefactorPlan
from atlas_sdk.models.simulation import ScoreDelta, SimulationResult

logger = logging.getLogger(__name__)


class DiffSimulator:
    """Simulates the effect of applying a RefactorPlan to a graph.

    Usage:
        simulator = DiffSimulator()
        result = simulator.simulate(graph, findings, plan)
    """

    def simulate(
        self,
        graph: CICDGraph,
        findings: list,
        plan: RefactorPlan,
    ) -> SimulationResult:
        """Simulate applying a refactor plan.

        Args:
            graph: The original CI/CD graph.
            findings: Current rule-engine findings.
            plan: The refactor plan to simulate.

        Returns:
            SimulationResult with projected scores and diff preview.
        """
        # Compute current scores
        from atlas_report.scorer import compute_scores

        current_scores = compute_scores(graph)

        # Determine which findings would be fixed
        fixed_rule_ids = {s.rule_id for s in plan.suggestions}
        remaining = [f for f in findings if f.rule_id not in fixed_rule_ids]
        removed_count = len(findings) - len(remaining)

        # Simulate the projected graph (deep copy to avoid mutation)
        projected_graph = deepcopy(graph)

        # Apply structural changes based on suggestions
        for suggestion in plan.suggestions:
            self._apply_suggestion(projected_graph, suggestion)

        projected_scores = compute_scores(projected_graph)

        # Build score deltas
        deltas = [
            ScoreDelta(
                metric="complexity",
                before=current_scores.complexity_score,
                after=projected_scores.complexity_score,
            ),
            ScoreDelta(
                metric="fragility",
                before=current_scores.fragility_score,
                after=projected_scores.fragility_score,
            ),
            ScoreDelta(
                metric="maturity",
                before=current_scores.maturity_score,
                after=projected_scores.maturity_score,
            ),
        ]

        # Generate diff preview
        diff_lines = self._generate_diff(plan)

        result = SimulationResult(
            plan_id=plan.id,
            graph_id=graph.id,
            findings_removed=removed_count,
            findings_remaining=len(remaining),
            score_deltas=deltas,
            diff_preview="\n".join(diff_lines),
            projected_node_count=len(projected_graph.nodes),
            projected_edge_count=len(projected_graph.edges),
        )

        logger.info(
            "Simulation complete: %d findings fixed, %d remaining",
            removed_count, len(remaining),
        )
        return result

    def _apply_suggestion(self, graph: CICDGraph, suggestion) -> None:
        """Apply a single suggestion to a projected graph.

        This modifies node metadata to reflect the fix without altering
        the actual node count/edges (structural simulation).
        """
        for node in graph.nodes:
            if node.id in suggestion.affected_node_ids:
                # Mark node as having the fix applied
                node.metadata["refactored"] = True
                node.metadata["refactor_rule"] = suggestion.rule_id

    def _generate_diff(self, plan: RefactorPlan) -> list[str]:
        """Generate a unified diff preview from all suggestions."""
        lines = [f"# Diff Preview — {plan.name}", f"# {plan.total_suggestions} changes", ""]

        for i, s in enumerate(plan.suggestions, 1):
            lines.append(f"## [{i}] {s.description}")
            lines.append(f"## Risk: {s.risk_level} | Effort: {s.effort_estimate}")
            lines.append("")

            for line in s.before_snippet.splitlines():
                lines.append(f"- {line}")
            for line in s.after_snippet.splitlines():
                lines.append(f"+ {line}")
            lines.append("")

        return lines
