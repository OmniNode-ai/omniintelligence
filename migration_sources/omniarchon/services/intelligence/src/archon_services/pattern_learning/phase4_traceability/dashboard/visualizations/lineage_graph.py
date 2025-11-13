"""
Phase 4 Dashboard - Lineage Graph Visualization

Interactive graph visualization for pattern evolution lineage.
Uses NetworkX for graph layout and Plotly for interactive rendering.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import networkx as nx
import plotly.graph_objects as go
from src.archon_services.pattern_learning.phase4_traceability.models.model_lineage_graph import (
    LineageRelationType,
    ModelLineageGraph,
    NodeStatus,
)

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class LineageGraphVisualizer:
    """
    Lineage graph visualization with interactive features.

    Creates force-directed graph layouts with:
    - Color-coded nodes by status
    - Edge types for relationships
    - Zoom and pan capabilities
    - Node/edge hover information
    - Export to PNG/SVG
    """

    # Color scheme for node status
    STATUS_COLORS = {
        NodeStatus.ACTIVE: "#2ECC40",  # Green
        NodeStatus.DEPRECATED: "#AAAAAA",  # Gray
        NodeStatus.MERGED: "#0074D9",  # Blue
        NodeStatus.ARCHIVED: "#DDDDDD",  # Light gray
    }

    # Color scheme for edge types
    EDGE_COLORS = {
        LineageRelationType.DERIVED_FROM: "#001f3f",  # Navy
        LineageRelationType.MERGED_WITH: "#0074D9",  # Blue
        LineageRelationType.REPLACED_BY: "#FF4136",  # Red
        LineageRelationType.SPLIT_INTO: "#FF851B",  # Orange
        LineageRelationType.INSPIRED_BY: "#B10DC9",  # Purple
    }

    def __init__(self, layout_algorithm: str = "spring"):
        """
        Initialize lineage graph visualizer.

        Args:
            layout_algorithm: NetworkX layout algorithm
                - "spring": Force-directed layout (default)
                - "kamada_kawai": Energy-minimization layout
                - "circular": Circular layout
                - "hierarchical": Hierarchical tree layout
        """
        self.layout_algorithm = layout_algorithm
        logger.info(
            f"Initialized LineageGraphVisualizer with {layout_algorithm} layout"
        )

    def create_interactive_graph(
        self,
        lineage_graph: ModelLineageGraph,
        focus_pattern_id: Optional[UUID] = None,
        max_depth: Optional[int] = None,
        title: str = "Pattern Lineage Graph",
    ) -> go.Figure:
        """
        Create interactive lineage graph visualization.

        Args:
            lineage_graph: Complete lineage graph
            focus_pattern_id: Optional pattern to focus on (highlights ancestors/descendants)
            max_depth: Maximum depth from focus pattern (if provided)
            title: Graph title

        Returns:
            Plotly Figure with interactive graph
        """
        logger.info(f"Creating lineage graph with {len(lineage_graph.nodes)} nodes")

        # Build NetworkX graph
        G = self._build_networkx_graph(lineage_graph)

        # Filter graph if focus pattern provided
        if focus_pattern_id:
            G = self._filter_graph_by_focus(
                G, lineage_graph, focus_pattern_id, max_depth
            )

        # Calculate layout positions
        pos = self._calculate_layout(G)

        # Create Plotly traces
        edge_traces = self._create_edge_traces(G, pos, lineage_graph)
        node_trace = self._create_node_trace(G, pos, lineage_graph, focus_pattern_id)

        # Combine traces
        fig = go.Figure(data=edge_traces + [node_trace])

        # Configure layout
        fig.update_layout(
            title=title,
            showlegend=True,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="white",
            height=800,
        )

        return fig

    def _build_networkx_graph(self, lineage_graph: ModelLineageGraph) -> nx.DiGraph:
        """Build NetworkX directed graph from lineage graph."""
        G = nx.DiGraph()

        # Add nodes
        for pattern_id, node in lineage_graph.nodes.items():
            G.add_node(
                pattern_id,
                pattern_name=node.pattern_name,
                status=node.status,
                version=node.version,
                usage_count=node.usage_count,
                success_rate=node.success_rate,
            )

        # Add edges
        for edge in lineage_graph.edges:
            G.add_edge(
                str(edge.source_pattern_id),
                str(edge.target_pattern_id),
                relation_type=edge.relation_type,
                created_at=edge.created_at,
            )

        return G

    def _filter_graph_by_focus(
        self,
        G: nx.DiGraph,
        lineage_graph: ModelLineageGraph,
        focus_pattern_id: UUID,
        max_depth: Optional[int],
    ) -> nx.DiGraph:
        """Filter graph to show only nodes related to focus pattern."""
        focus_id = str(focus_pattern_id)

        if focus_id not in G:
            logger.warning(f"Focus pattern {focus_id} not found in graph")
            return G

        # Get ancestors and descendants
        ancestors = lineage_graph.get_ancestors(focus_pattern_id)
        descendants = lineage_graph.get_descendants(focus_pattern_id)

        # Build set of relevant nodes
        relevant_nodes = {focus_id}
        relevant_nodes.update(str(n.pattern_id) for n in ancestors)
        relevant_nodes.update(str(n.pattern_id) for n in descendants)

        # Filter graph
        filtered_G = G.subgraph(relevant_nodes).copy()

        logger.info(
            f"Filtered graph to {len(filtered_G.nodes)} nodes around {focus_id}"
        )
        return filtered_G

    def _calculate_layout(self, G: nx.DiGraph) -> Dict[str, Tuple[float, float]]:
        """Calculate node positions using selected layout algorithm."""
        if self.layout_algorithm == "spring":
            pos = nx.spring_layout(G, k=2, iterations=50)
        elif self.layout_algorithm == "kamada_kawai":
            pos = nx.kamada_kawai_layout(G)
        elif self.layout_algorithm == "circular":
            pos = nx.circular_layout(G)
        elif self.layout_algorithm == "hierarchical":
            pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
        else:
            logger.warning(f"Unknown layout {self.layout_algorithm}, using spring")
            pos = nx.spring_layout(G, k=2, iterations=50)

        return pos

    def _create_edge_traces(
        self,
        G: nx.DiGraph,
        pos: Dict[str, Tuple[float, float]],
        lineage_graph: ModelLineageGraph,
    ) -> List[go.Scatter]:
        """Create Plotly traces for edges, grouped by relationship type."""
        edge_traces = []

        # Group edges by type
        edges_by_type = {}
        for u, v, data in G.edges(data=True):
            rel_type = data.get("relation_type", LineageRelationType.DERIVED_FROM)
            if rel_type not in edges_by_type:
                edges_by_type[rel_type] = []
            edges_by_type[rel_type].append((u, v, data))

        # Create trace for each edge type
        for rel_type, edges in edges_by_type.items():
            edge_x = []
            edge_y = []

            for u, v, _ in edges:
                x0, y0 = pos[u]
                x1, y1 = pos[v]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

            edge_trace = go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line=dict(
                    width=2,
                    color=self.EDGE_COLORS.get(rel_type, "#888888"),
                ),
                hoverinfo="none",
                showlegend=True,
                name=rel_type.value.replace("_", " ").title(),
            )
            edge_traces.append(edge_trace)

        return edge_traces

    def _create_node_trace(
        self,
        G: nx.DiGraph,
        pos: Dict[str, Tuple[float, float]],
        lineage_graph: ModelLineageGraph,
        focus_pattern_id: Optional[UUID],
    ) -> go.Scatter:
        """Create Plotly trace for nodes."""
        node_x = []
        node_y = []
        node_colors = []
        node_sizes = []
        node_text = []

        for node_id in G.nodes():
            x, y = pos[node_id]
            node_x.append(x)
            node_y.append(y)

            # Get node data
            node_data = G.nodes[node_id]
            status = node_data.get("status", NodeStatus.ACTIVE)
            usage_count = node_data.get("usage_count", 0)
            success_rate = node_data.get("success_rate", 0.0)

            # Color by status
            node_colors.append(self.STATUS_COLORS.get(status, "#888888"))

            # Size by usage count (with min/max bounds)
            size = max(10, min(50, 10 + usage_count / 2))
            node_sizes.append(size)

            # Hover text
            hover_text = f"""
            <b>{node_data.get('pattern_name', 'Unknown')}</b><br>
            Version: {node_data.get('version', 1)}<br>
            Status: {status.value}<br>
            Usage: {usage_count}<br>
            Success Rate: {success_rate:.1%}<br>
            """
            node_text.append(hover_text)

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=2, color="white"),
            ),
            text=[G.nodes[n].get("pattern_name", "") for n in G.nodes()],
            textposition="top center",
            textfont=dict(size=10),
            hovertext=node_text,
            hoverinfo="text",
            showlegend=False,
        )

        return node_trace

    def export_graph(
        self,
        fig: go.Figure,
        filepath: str,
        format: str = "html",
        width: int = 1200,
        height: int = 800,
    ) -> None:
        """
        Export graph to file.

        Args:
            fig: Plotly figure to export
            filepath: Output file path
            format: Export format - "html", "png", "svg", "pdf"
            width: Image width (for non-HTML formats)
            height: Image height (for non-HTML formats)
        """
        if format == "html":
            fig.write_html(filepath)
            logger.info(f"Exported graph to {filepath}")
        elif format == "png":
            fig.write_image(filepath, width=width, height=height, format="png")
            logger.info(f"Exported graph to {filepath}")
        elif format == "svg":
            fig.write_image(filepath, width=width, height=height, format="svg")
            logger.info(f"Exported graph to {filepath}")
        elif format == "pdf":
            fig.write_image(filepath, width=width, height=height, format="pdf")
            logger.info(f"Exported graph to {filepath}")
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def create_lineage_summary(
        self, lineage_graph: ModelLineageGraph
    ) -> Dict[str, Any]:
        """
        Create summary statistics for lineage graph.

        Returns:
            Dictionary with summary metrics
        """
        G = self._build_networkx_graph(lineage_graph)

        # Count nodes by status
        status_counts = {}
        for node_id in G.nodes():
            status = G.nodes[node_id].get("status", NodeStatus.ACTIVE)
            status_counts[status.value] = status_counts.get(status.value, 0) + 1

        # Count edges by type
        edge_type_counts = {}
        for _, _, data in G.edges(data=True):
            rel_type = data.get("relation_type", LineageRelationType.DERIVED_FROM)
            edge_type_counts[rel_type.value] = (
                edge_type_counts.get(rel_type.value, 0) + 1
            )

        # Calculate graph metrics
        summary = {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "status_breakdown": status_counts,
            "relationship_breakdown": edge_type_counts,
            "connected_components": nx.number_weakly_connected_components(G),
            "avg_degree": sum(dict(G.degree()).values()) / max(G.number_of_nodes(), 1),
            "active_patterns": status_counts.get(NodeStatus.ACTIVE.value, 0),
            "deprecated_patterns": status_counts.get(NodeStatus.DEPRECATED.value, 0),
        }

        return summary
