"""
Phase 4 Dashboard - Feedback Analysis View

Visualization for pattern feedback, sentiment analysis, and improvements.
"""

import logging
from typing import List
from uuid import UUID, uuid4

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.archon_services.pattern_learning.phase4_traceability.models.model_pattern_feedback import (
    FeedbackSentiment,
    ImprovementStatus,
    ModelPatternFeedback,
    ModelPatternImprovement,
)

logger = logging.getLogger(__name__)


# NOTE: correlation_id support enabled for tracing
class FeedbackAnalysisView:
    """
    Feedback analysis visualization.

    Creates visualizations for:
    - Feedback sentiment distribution
    - Improvement pipeline tracking
    - Quality rating trends
    - Feedback timeline
    """

    # Color scheme for sentiment
    SENTIMENT_COLORS = {
        FeedbackSentiment.POSITIVE: "#2ECC40",  # Green
        FeedbackSentiment.NEUTRAL: "#FFDC00",  # Yellow
        FeedbackSentiment.NEGATIVE: "#FF4136",  # Red
    }

    # Color scheme for improvement status
    IMPROVEMENT_COLORS = {
        ImprovementStatus.PROPOSED: "#AAAAAA",  # Gray
        ImprovementStatus.VALIDATED: "#0074D9",  # Blue
        ImprovementStatus.APPLIED: "#2ECC40",  # Green
        ImprovementStatus.REJECTED: "#FF4136",  # Red
    }

    def __init__(self):
        """Initialize feedback analysis view."""
        logger.info("Initialized FeedbackAnalysisView")

    def create_sentiment_distribution(
        self,
        feedbacks: List[ModelPatternFeedback],
        title: str = "Feedback Sentiment Distribution",
    ) -> go.Figure:
        """
        Create pie chart showing sentiment distribution.

        Args:
            feedbacks: List of pattern feedbacks
            title: Chart title

        Returns:
            Plotly Figure with sentiment distribution
        """
        if not feedbacks:
            return self._create_empty_figure("No feedback data available")

        # Count sentiments
        sentiment_counts = {
            FeedbackSentiment.POSITIVE: 0,
            FeedbackSentiment.NEUTRAL: 0,
            FeedbackSentiment.NEGATIVE: 0,
        }

        for feedback in feedbacks:
            sentiment_counts[feedback.sentiment] += 1

        # Create pie chart
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=[s.value.capitalize() for s in sentiment_counts.keys()],
                    values=list(sentiment_counts.values()),
                    marker=dict(
                        colors=[
                            self.SENTIMENT_COLORS[s] for s in sentiment_counts.keys()
                        ]
                    ),
                    hole=0.3,
                )
            ]
        )

        fig.update_layout(
            title=title,
            height=400,
        )

        return fig

    def create_feedback_timeline(
        self,
        feedbacks: List[ModelPatternFeedback],
        title: str = "Feedback Timeline",
    ) -> go.Figure:
        """
        Create timeline showing feedback over time.

        Args:
            feedbacks: List of pattern feedbacks
            title: Chart title

        Returns:
            Plotly Figure with feedback timeline
        """
        if not feedbacks:
            return self._create_empty_figure("No feedback data available")

        # Convert to DataFrame
        df = pd.DataFrame(
            [
                {
                    "created_at": f.created_at,
                    "sentiment": f.sentiment.value,
                    "pattern_name": f.pattern_name,
                    "quality_rating": f.quality_rating or 0,
                }
                for f in feedbacks
            ]
        ).sort_values("created_at")

        # Create scatter plot
        fig = px.scatter(
            df,
            x="created_at",
            y="quality_rating",
            color="sentiment",
            color_discrete_map={
                "positive": self.SENTIMENT_COLORS[FeedbackSentiment.POSITIVE],
                "neutral": self.SENTIMENT_COLORS[FeedbackSentiment.NEUTRAL],
                "negative": self.SENTIMENT_COLORS[FeedbackSentiment.NEGATIVE],
            },
            hover_data=["pattern_name"],
            title=title,
            labels={
                "created_at": "Date",
                "quality_rating": "Quality Rating",
                "sentiment": "Sentiment",
            },
        )

        fig.update_layout(
            height=500,
            yaxis=dict(range=[0, 5.5]),
        )

        return fig

    def create_improvement_pipeline(
        self,
        improvements: List[ModelPatternImprovement],
        title: str = "Improvement Pipeline",
    ) -> go.Figure:
        """
        Create funnel chart showing improvement pipeline stages.

        Args:
            improvements: List of pattern improvements
            title: Chart title

        Returns:
            Plotly Figure with improvement pipeline
        """
        if not improvements:
            return self._create_empty_figure("No improvement data available")

        # Count by status
        status_counts = {
            ImprovementStatus.PROPOSED: 0,
            ImprovementStatus.VALIDATED: 0,
            ImprovementStatus.APPLIED: 0,
            ImprovementStatus.REJECTED: 0,
        }

        for improvement in improvements:
            status_counts[improvement.status] += 1

        # Create funnel chart
        fig = go.Figure(
            go.Funnel(
                y=[s.value.capitalize() for s in status_counts.keys()],
                x=list(status_counts.values()),
                marker=dict(
                    color=[self.IMPROVEMENT_COLORS[s] for s in status_counts.keys()],
                ),
            )
        )

        fig.update_layout(
            title=title,
            height=500,
        )

        return fig

    def create_improvement_priority_breakdown(
        self,
        improvements: List[ModelPatternImprovement],
        title: str = "Improvements by Priority",
    ) -> go.Figure:
        """
        Create bar chart showing improvements by priority level.

        Args:
            improvements: List of pattern improvements
            title: Chart title

        Returns:
            Plotly Figure with priority breakdown
        """
        if not improvements:
            return self._create_empty_figure("No improvement data available")

        # Count by priority
        priority_counts = {}
        for improvement in improvements:
            priority = improvement.priority
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        # Sort by priority level
        priority_order = ["critical", "high", "medium", "low"]
        sorted_priorities = sorted(
            priority_counts.items(),
            key=lambda x: priority_order.index(x[0]) if x[0] in priority_order else 999,
        )

        # Create bar chart
        fig = go.Figure(
            data=[
                go.Bar(
                    x=[p[0].capitalize() for p in sorted_priorities],
                    y=[p[1] for p in sorted_priorities],
                    marker_color=["#FF4136", "#FF851B", "#FFDC00", "#01FF70"],
                )
            ]
        )

        fig.update_layout(
            title=title,
            xaxis_title="Priority",
            yaxis_title="Count",
            height=400,
        )

        return fig

    def create_improvement_type_breakdown(
        self,
        improvements: List[ModelPatternImprovement],
        title: str = "Improvements by Type",
    ) -> go.Figure:
        """
        Create pie chart showing improvement type distribution.

        Args:
            improvements: List of pattern improvements
            title: Chart title

        Returns:
            Plotly Figure with type breakdown
        """
        if not improvements:
            return self._create_empty_figure("No improvement data available")

        # Count by type
        type_counts = {}
        for improvement in improvements:
            imp_type = improvement.improvement_type
            type_counts[imp_type] = type_counts.get(imp_type, 0) + 1

        # Create pie chart
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=list(type_counts.keys()),
                    values=list(type_counts.values()),
                )
            ]
        )

        fig.update_layout(
            title=title,
            height=400,
        )

        return fig

    def create_feedback_summary_table(
        self,
        feedbacks: List[ModelPatternFeedback],
        max_rows: int = 20,
    ) -> go.Figure:
        """
        Create table showing recent feedback.

        Args:
            feedbacks: List of pattern feedbacks
            max_rows: Maximum rows to display

        Returns:
            Plotly Figure with feedback table
        """
        if not feedbacks:
            return self._create_empty_figure("No feedback data available")

        # Sort by date (most recent first)
        sorted_feedbacks = sorted(feedbacks, key=lambda f: f.created_at, reverse=True)[
            :max_rows
        ]

        # Prepare table data
        table_data = {
            "Date": [],
            "Pattern": [],
            "Sentiment": [],
            "Rating": [],
            "Feedback": [],
        }

        for feedback in sorted_feedbacks:
            table_data["Date"].append(feedback.created_at.strftime("%Y-%m-%d %H:%M"))
            table_data["Pattern"].append(feedback.pattern_name)
            table_data["Sentiment"].append(feedback.sentiment.value.capitalize())
            table_data["Rating"].append(
                f"{feedback.quality_rating:.1f}★" if feedback.quality_rating else "N/A"
            )
            # Truncate feedback text
            feedback_text = feedback.feedback_text
            if len(feedback_text) > 80:
                feedback_text = feedback_text[:77] + "..."
            table_data["Feedback"].append(feedback_text)

        # Create table
        fig = go.Figure(
            data=[
                go.Table(
                    header=dict(
                        values=list(table_data.keys()),
                        fill_color="paleturquoise",
                        align="left",
                        font=dict(size=12, color="black"),
                    ),
                    cells=dict(
                        values=list(table_data.values()),
                        fill_color="lavender",
                        align="left",
                        font=dict(size=11),
                    ),
                )
            ]
        )

        fig.update_layout(
            title="Recent Feedback",
            height=600,
        )

        return fig

    def create_improvement_summary_table(
        self,
        improvements: List[ModelPatternImprovement],
        max_rows: int = 20,
    ) -> go.Figure:
        """
        Create table showing improvement suggestions.

        Args:
            improvements: List of pattern improvements
            max_rows: Maximum rows to display

        Returns:
            Plotly Figure with improvements table
        """
        if not improvements:
            return self._create_empty_figure("No improvement data available")

        # Sort by priority and date
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_improvements = sorted(
            improvements,
            key=lambda i: (priority_order.get(i.priority, 999), i.created_at),
            reverse=True,
        )[:max_rows]

        # Prepare table data
        table_data = {
            "Priority": [],
            "Status": [],
            "Type": [],
            "Pattern": [],
            "Description": [],
            "Impact": [],
        }

        for improvement in sorted_improvements:
            table_data["Priority"].append(improvement.priority.capitalize())
            table_data["Status"].append(improvement.status.value.capitalize())
            table_data["Type"].append(improvement.improvement_type)
            table_data["Pattern"].append(improvement.pattern_name)

            # Truncate description
            description = improvement.description
            if len(description) > 60:
                description = description[:57] + "..."
            table_data["Description"].append(description)

            table_data["Impact"].append(improvement.impact_estimate or "Unknown")

        # Create table
        fig = go.Figure(
            data=[
                go.Table(
                    header=dict(
                        values=list(table_data.keys()),
                        fill_color="lightblue",
                        align="left",
                        font=dict(size=12, color="black"),
                    ),
                    cells=dict(
                        values=list(table_data.values()),
                        fill_color="white",
                        align="left",
                        font=dict(size=11),
                    ),
                )
            ]
        )

        fig.update_layout(
            title="Improvement Suggestions",
            height=600,
        )

        return fig

    def create_feedback_dashboard(
        self,
        feedbacks: List[ModelPatternFeedback],
        improvements: List[ModelPatternImprovement],
        title: str = "Feedback Analysis Dashboard",
    ) -> go.Figure:
        """
        Create comprehensive feedback dashboard.

        Args:
            feedbacks: List of pattern feedbacks
            improvements: List of pattern improvements
            title: Dashboard title

        Returns:
            Plotly Figure with multi-panel dashboard
        """
        # Create subplots
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Sentiment Distribution",
                "Improvement Pipeline",
                "Quality Ratings Timeline",
                "Priority Breakdown",
            ),
            specs=[
                [{"type": "pie"}, {"type": "funnel"}],
                [{"type": "scatter"}, {"type": "bar"}],
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.10,
        )

        if feedbacks:
            # Sentiment pie
            sentiment_counts = {
                FeedbackSentiment.POSITIVE: 0,
                FeedbackSentiment.NEUTRAL: 0,
                FeedbackSentiment.NEGATIVE: 0,
            }
            for f in feedbacks:
                sentiment_counts[f.sentiment] += 1

            fig.add_trace(
                go.Pie(
                    labels=[s.value.capitalize() for s in sentiment_counts.keys()],
                    values=list(sentiment_counts.values()),
                    marker=dict(
                        colors=[
                            self.SENTIMENT_COLORS[s] for s in sentiment_counts.keys()
                        ]
                    ),
                ),
                row=1,
                col=1,
            )

            # Quality timeline
            df_quality = pd.DataFrame(
                [
                    {
                        "created_at": f.created_at,
                        "quality_rating": f.quality_rating or 0,
                    }
                    for f in feedbacks
                    if f.quality_rating
                ]
            ).sort_values("created_at")

            if not df_quality.empty:
                fig.add_trace(
                    go.Scatter(
                        x=df_quality["created_at"],
                        y=df_quality["quality_rating"],
                        mode="lines+markers",
                        name="Quality",
                    ),
                    row=2,
                    col=1,
                )

        if improvements:
            # Improvement funnel
            status_counts = {
                ImprovementStatus.PROPOSED: 0,
                ImprovementStatus.VALIDATED: 0,
                ImprovementStatus.APPLIED: 0,
            }
            for i in improvements:
                if i.status in status_counts:
                    status_counts[i.status] += 1

            fig.add_trace(
                go.Funnel(
                    y=[s.value.capitalize() for s in status_counts.keys()],
                    x=list(status_counts.values()),
                ),
                row=1,
                col=2,
            )

            # Priority breakdown
            priority_counts = {}
            for i in improvements:
                priority_counts[i.priority] = priority_counts.get(i.priority, 0) + 1

            priority_order = ["critical", "high", "medium", "low"]
            sorted_priorities = sorted(
                priority_counts.items(),
                key=lambda x: (
                    priority_order.index(x[0]) if x[0] in priority_order else 999
                ),
            )

            fig.add_trace(
                go.Bar(
                    x=[p[0].capitalize() for p in sorted_priorities],
                    y=[p[1] for p in sorted_priorities],
                ),
                row=2,
                col=2,
            )

        # Update layout
        fig.update_layout(
            title=title,
            height=800,
            showlegend=False,
        )

        return fig

    def _create_empty_figure(self, message: str) -> go.Figure:
        """Create empty figure with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16),
        )
        fig.update_layout(
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, showticklabels=False),
            height=400,
        )
        return fig
