"""PipelineAtlas Graph Engine — graph construction, export, and persistence."""

__version__ = "0.1.0"

from atlas_graph.builder import GraphBuilder  # noqa: F401
from atlas_graph.doc_intel import (  # noqa: F401
    DocScore,
    detect_doc_files,
    score_documentation,
)
from atlas_graph.export import export_dict, export_dot, export_graphml, export_json  # noqa: F401
from atlas_graph.persistence import GraphStore  # noqa: F401
