"""Documentation intelligence — detection and scoring.

From docs/README.md §4.3:
- Detect doc files (README, runbooks, architecture, ADRs, CODEOWNERS, etc.)
- Evaluate coverage (build docs, deploy docs, rollback docs, ownership)
- Detect drift between documentation and pipeline reality
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from atlas_sdk.enums import DocType, NodeType
from atlas_sdk.models.graph import CICDGraph
from atlas_sdk.models.nodes import DocFileNode, Node

logger = logging.getLogger(__name__)

# Expected documentation categories for a well-documented project
_EXPECTED_DOCS = {
    "readme": "README file",
    "architecture": "Architecture documentation",
    "runbook": "Runbook / operations guide",
    "security_policy": "Security policy",
    "codeowners": "Code ownership file",
}


@dataclass
class DocScore:
    """Documentation coverage and drift scoring."""

    total_expected: int = len(_EXPECTED_DOCS)
    found: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    coverage_pct: float = 0.0
    drift_warnings: list[str] = field(default_factory=list)
    drift_score: float = 0.0  # 0 = no drift, 1 = severe drift


def detect_doc_files(file_paths: list[str]) -> list[tuple[str, DocType]]:
    """Classify file paths into documentation types.

    Args:
        file_paths: List of file paths from a repository.

    Returns:
        List of (path, DocType) tuples for detected doc files.
    """
    results = []
    for path in file_paths:
        lower = path.lower()
        basename = lower.rsplit("/", 1)[-1] if "/" in lower else lower

        if basename in ("readme.md", "readme.rst", "readme.txt", "readme"):
            results.append((path, DocType.README))
        elif basename in ("architecture.md", "arch.md"):
            results.append((path, DocType.ARCHITECTURE))
        elif basename in ("runbook.md", "playbook.md"):
            results.append((path, DocType.RUNBOOK))
        elif basename in ("security.md", "security_policy.md"):
            results.append((path, DocType.SECURITY_POLICY))
        elif basename in ("codeowners", ".github/codeowners"):
            results.append((path, DocType.CODEOWNERS))
        elif "adr" in lower and basename.endswith(".md"):
            results.append((path, DocType.ADR))
        elif "docs/" in lower or "doc/" in lower:
            results.append((path, DocType.DOCS_DIR))

    return results


def score_documentation(graph: CICDGraph) -> DocScore:
    """Score documentation coverage for a CI/CD graph.

    Checks which expected doc types are present as DocFileNodes.

    Args:
        graph: The CI/CD graph to score.

    Returns:
        DocScore with coverage percentage and missing docs.
    """
    doc_nodes = [n for n in graph.nodes if n.node_type == NodeType.DOC_FILE]
    found_types = set()
    for node in doc_nodes:
        if isinstance(node, DocFileNode):
            found_types.add(node.doc_type.value)

    score = DocScore()
    for doc_key, doc_label in _EXPECTED_DOCS.items():
        if doc_key in found_types:
            score.found.append(doc_label)
        else:
            score.missing.append(doc_label)

    if score.total_expected > 0:
        score.coverage_pct = round(len(score.found) / score.total_expected * 100, 1)

    # Drift detection: check if pipelines reference deploy/rollback
    # but no runbook exists
    has_deploy = any(
        n.node_type in (NodeType.ENVIRONMENT, NodeType.STAGE)
        and "deploy" in n.name.lower()
        for n in graph.nodes
    )
    has_runbook = "runbook" in found_types

    if has_deploy and not has_runbook:
        score.drift_warnings.append(
            "Pipeline deploys to environments but no runbook documentation found"
        )
        score.drift_score = max(score.drift_score, 0.5)

    # Check if secrets are used but no security policy
    has_secrets = any(n.node_type == NodeType.SECRET_REF for n in graph.nodes)
    has_security = "security_policy" in found_types

    if has_secrets and not has_security:
        score.drift_warnings.append(
            "Pipeline uses secrets but no security policy documentation found"
        )
        score.drift_score = max(score.drift_score, 0.3)

    logger.info(
        "Doc score: %.1f%% coverage, %.1f drift, %d warnings",
        score.coverage_pct, score.drift_score, len(score.drift_warnings),
    )
    return score
