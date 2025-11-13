"""
CLAUDE.md Generation Agent

PydanticAI agent that orchestrates multi-model chain of responders for generating
professional CLAUDE.md documentation from project and task contexts.
"""

import logging
import time
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ClaudeMdGenerationContext(BaseModel):
    """Context for CLAUDE.md generation"""

    project: Optional[dict[str, Any]] = None
    task: Optional[dict[str, Any]] = None
    generation_config: dict[str, Any] = Field(default_factory=dict)


class ClaudeMdResult(BaseModel):
    """Result from multi-model CLAUDE.md generation"""

    content: str = Field(..., description="Generated CLAUDE.md content")
    quality_score: float = Field(..., description="Quality score 0.0-1.0")
    models_used: list[str] = Field(..., description="Models used in generation chain")
    processing_time: float = Field(..., description="Total processing time in seconds")
    stages_completed: int = Field(
        ..., description="Number of generation stages completed"
    )
    generation_metadata: dict[str, Any] = Field(default_factory=dict)


class ClaudeMdAgent:
    """
    Multi-model CLAUDE.md generation agent.

    Implements chain of responders pattern inspired by Archon's orchestration architectures:
    1. Analysis Stage: Deep project/task understanding
    2. Structure Stage: Content organization and planning
    3. Writing Stage: Professional technical documentation
    4. Validation Stage: Quality assurance and refinement
    """

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        self.model = model
        self.name = "claude_md_generator"
        self.ollama_url = "http://192.168.86.200:11434"

        # PydanticAI agent will be initialized when needed
        self.agent = None

    def _get_system_prompt(self) -> str:
        """Get system prompt for the CLAUDE.md generation agent"""
        return """
You are a technical documentation specialist that orchestrates multi-model chains
for generating professional CLAUDE.md files. You coordinate with specialized models
to create comprehensive, accurate, and developer-friendly documentation.

Your role is to:
1. Coordinate multi-model chain of responders
2. Analyze project/task contexts for documentation needs
3. Generate structured, professional CLAUDE.md content
4. Ensure quality through validation and refinement

Always return properly formatted CLAUDE.md content with:
- Clear project overview and purpose
- Comprehensive API documentation with examples
- Setup and deployment instructions
- Architecture and technology stack details
- Developer experience optimizations
"""

    async def run(self, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Run the CLAUDE.md generation using multi-model chain

        Args:
            prompt: Generation prompt (usually describes what type of documentation needed)
            context: Context containing project/task information and generation config

        Returns:
            Dictionary with generation results
        """
        try:
            # Extract context
            generation_context = ClaudeMdGenerationContext(**context)

            # Execute multi-model chain
            result = await self._execute_multi_model_chain(generation_context, prompt)

            return {
                "success": True,
                "output": result.dict(),
                "agent_type": self.name,
                "model": self.model,
            }

        except Exception as e:
            logger.error(f"CLAUDE.md generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_type": self.name,
                "model": self.model,
            }

    async def _execute_multi_model_chain(
        self, context: ClaudeMdGenerationContext, prompt: str
    ) -> ClaudeMdResult:
        """
        Execute the multi-model chain of responders

        This implements the sophisticated orchestration pattern:
        1. Analysis: Deep understanding of project/task
        2. Structure: Content organization
        3. Writing: Technical documentation generation
        4. Validation: Quality assurance
        """
        start_time = time.time()
        models_used = []
        stages_completed = 0

        try:
            # Get model chain configuration
            chain_config = context.generation_config.get("model_chain", {})

            # Stage 1: Analysis
            analysis_result = ""
            if chain_config.get("analysis"):
                analysis_result = await self._call_ollama_model(
                    chain_config["analysis"],
                    self._create_analysis_prompt(context, prompt),
                )
                models_used.append(chain_config["analysis"])
                stages_completed += 1

            # Stage 2: Structure (optional, fast planning stage)
            structure_result = ""
            if chain_config.get("structure"):
                structure_prompt = self._create_structure_prompt(
                    analysis_result, context, prompt
                )
                structure_result = await self._call_ollama_model(
                    chain_config["structure"], structure_prompt
                )
                models_used.append(chain_config["structure"])
                stages_completed += 1

            # Stage 3: Writing (main documentation generation)
            writing_model = chain_config.get(
                "writing", "mixtral:8x7b-instruct-v0.1-q4_K_M"
            )
            writing_prompt = self._create_writing_prompt(
                analysis_result, structure_result, context, prompt
            )
            content = await self._call_ollama_model(writing_model, writing_prompt)
            models_used.append(writing_model)
            stages_completed += 1

            # Stage 4: Validation (optional quality check)
            quality_score = 0.8  # Default score
            if chain_config.get("validation"):
                validation_result = await self._call_ollama_model(
                    chain_config["validation"],
                    self._create_validation_prompt(content, context),
                )
                models_used.append(chain_config["validation"])
                stages_completed += 1

                # Extract quality score and potentially improved content
                content, quality_score = self._parse_validation_result(
                    validation_result, content
                )

            processing_time = time.time() - start_time

            return ClaudeMdResult(
                content=content,
                quality_score=quality_score,
                models_used=models_used,
                processing_time=processing_time,
                stages_completed=stages_completed,
                generation_metadata={
                    "pattern": "chain_of_responders",
                    "target_audience": context.generation_config.get(
                        "target_audience", "developers"
                    ),
                    "output_type": context.generation_config.get(
                        "output_type", "project_level"
                    ),
                    "task_focused": context.generation_config.get(
                        "task_focused", False
                    ),
                },
            )

        except Exception as e:
            # Return partial results if available
            processing_time = time.time() - start_time
            logger.error(
                f"Multi-model chain failed at stage {stages_completed + 1}: {e}"
            )

            # If we have some content, return it with lower quality score
            fallback_content = (
                content
                if "content" in locals()
                else f"# Documentation Generation Failed\n\nError: {e!s}"
            )

            return ClaudeMdResult(
                content=fallback_content,
                quality_score=0.3,
                models_used=models_used,
                processing_time=processing_time,
                stages_completed=stages_completed,
                generation_metadata={
                    "pattern": "chain_of_responders",
                    "error": str(e),
                    "partial_result": True,
                },
            )

    async def _call_ollama_model(self, model_id: str, prompt: str) -> str:
        """Call Ollama model with the given prompt"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                payload = {
                    "model": model_id,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.6, "top_p": 0.9},
                }

                response = await client.post(
                    f"{self.ollama_url}/api/generate", json=payload
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "")
                else:
                    raise Exception(
                        f"Ollama API error: {response.status_code} - {response.text}"
                    )

        except Exception as e:
            logger.error(f"Failed to call Ollama model {model_id}: {e}")
            raise

    def _create_analysis_prompt(
        self, context: ClaudeMdGenerationContext, prompt: str
    ) -> str:
        """Create analysis stage prompt"""

        if context.project:
            project_info = f"""
PROJECT CONTEXT:
- Name: {context.project.get('name', 'Unknown')}
- Description: {context.project.get('description', '')}
- Dependencies: {', '.join(context.project.get('dependencies', []))}
- Service Endpoints: {len(context.project.get('service_endpoints', []))} endpoints
- Features: {', '.join(context.project.get('features', []))}
"""
        else:
            project_info = "No specific project context provided."

        if context.task:
            task_info = f"""
TASK CONTEXT:
- Title: {context.task.get('title', 'Unknown')}
- Description: {context.task.get('description', '')}
- Feature Area: {context.task.get('feature_area', 'general')}
"""
        else:
            task_info = "No specific task context provided."

        return f"""ARCHITECTURAL ANALYSIS FOR CLAUDE.md GENERATION

{project_info}

{task_info}

GENERATION REQUEST: {prompt}

Analyze this project/task for comprehensive CLAUDE.md documentation generation:

1. **Service Architecture**: What are the key architectural patterns and design decisions?
2. **Technology Stack**: What technologies are used and how do they integrate?
3. **API Design**: How are the endpoints organized and what patterns do they follow?
4. **Key Features**: What are the most important capabilities to highlight?
5. **Developer Experience**: What would developers most need to understand?
6. **Documentation Priorities**: What sections are most critical for this project?

Provide specific insights that will help generate exceptional technical documentation.
Focus on actionable information that shows deep understanding of the system.
"""

    def _create_structure_prompt(
        self, analysis: str, context: ClaudeMdGenerationContext, prompt: str
    ) -> str:
        """Create structure planning prompt"""

        return f"""CONTENT STRUCTURE PLANNING

ANALYSIS RESULTS:
{analysis}

GENERATION REQUEST: {prompt}

Based on the analysis, create a structured outline for the CLAUDE.md documentation:

1. **Section Organization**: What are the main sections and their logical order?
2. **Content Hierarchy**: How should information be prioritized and structured?
3. **API Documentation**: How should endpoints be grouped and presented?
4. **Code Examples**: What examples would be most valuable?
5. **User Journey**: What order should developers follow when reading this?

Create a clear, logical structure that makes the documentation easy to navigate and understand.
Focus on developer workflow and practical usability.
"""

    def _create_writing_prompt(
        self,
        analysis: str,
        structure: str,
        context: ClaudeMdGenerationContext,
        prompt: str,
    ) -> str:
        """Create writing stage prompt"""

        project_name = "Unknown Service"
        port = "8053"

        if context.project:
            project_name = context.project.get("name", "Unknown Service")
            # Try to extract port from service endpoints or default to 8053
            endpoints = context.project.get("service_endpoints", [])
            if endpoints and isinstance(endpoints, list) and len(endpoints) > 0:
                # Look for port in endpoint strings
                for endpoint in endpoints:
                    if isinstance(endpoint, str) and "http" in endpoint:
                        try:
                            # Extract port from URL if present
                            import re

                            port_match = re.search(r":(\d+)/", endpoint)
                            if port_match:
                                port = port_match.group(1)
                                break
                        except (ValueError, AttributeError, IndexError) as e:
                            logger.debug(
                                f"Failed to extract port from endpoint {endpoint}: {e}"
                            )
                            pass

        target_audience = context.generation_config.get("target_audience", "developers")

        analysis_section = f"ANALYSIS:\n{analysis}\n\n" if analysis else ""
        structure_section = f"STRUCTURE:\n{structure}\n\n" if structure else ""

        return f"""TECHNICAL DOCUMENTATION GENERATION

{analysis_section}{structure_section}Generate a comprehensive CLAUDE.md file for {project_name}.

TARGET AUDIENCE: {target_audience}
SERVICE PORT: {port}

REQUIREMENTS:
- Professional technical writing style
- Clear, developer-friendly language
- Comprehensive but concise content
- Well-structured with proper Markdown formatting
- Practical, actionable information
- Real code examples using port {port}
- Complete API coverage with curl examples

CONTENT STRUCTURE:
1. **Compelling Overview**: Clear explanation of what this service does and why
2. **Architecture Section**: Technical insights and design patterns
3. **Technology Stack**: Core technologies and integration patterns
4. **API Documentation**: All endpoints with practical examples
5. **Setup Instructions**: Clear deployment and configuration guidance
6. **Developer Experience**: Easy to understand and integrate

Generate ONLY the markdown content for CLAUDE.md. No meta-commentary or explanations.
Make it production-ready documentation that developers will love to use.
"""

    def _create_validation_prompt(
        self, content: str, context: ClaudeMdGenerationContext
    ) -> str:
        """Create validation stage prompt"""

        project_name = (
            context.project.get("name", "Unknown Service")
            if context.project
            else "Unknown Service"
        )
        expected_features = (
            context.project.get("features", []) if context.project else []
        )

        return f"""QUALITY VALIDATION AND SCORING

Validate this CLAUDE.md documentation for technical accuracy and completeness:

GENERATED CONTENT:
{content}

VALIDATION CRITERIA:
1. **Technical Accuracy**: Correct information and realistic examples
2. **Completeness**: All key features and capabilities covered
3. **Structure**: Logical organization with clear headings
4. **Clarity**: Professional technical writing that's easy to follow
5. **Usability**: Practical examples and clear setup instructions
6. **Code Examples**: Accurate syntax and proper formatting

EXPECTED FEATURES: {', '.join(expected_features) if expected_features else 'Not specified'}
SERVICE: {project_name}

RESPONSE FORMAT:
QUALITY_SCORE: X.X (0.0-1.0 scale)
TECHNICAL_ACCURACY: Pass/Fail
COMPLETENESS: Pass/Fail
CLARITY: Pass/Fail
USABILITY: Pass/Fail
ISSUES_FOUND: List any problems or "None"
RECOMMENDATIONS: Brief suggestions or "None"

If score is below 0.8, provide IMPROVED_CONTENT with fixes.
If score is 0.8+, respond with CONTENT_APPROVED: Yes
"""

    def _parse_validation_result(
        self, validation: str, original_content: str
    ) -> tuple[str, float]:
        """Extract quality score and final content from validation"""

        lines = validation.split("\n")
        quality_score = 0.75  # Default
        final_content = original_content

        # Extract quality score
        for line in lines:
            if "QUALITY_SCORE:" in line:
                try:
                    score_str = line.split("QUALITY_SCORE:")[1].strip()
                    quality_score = float(score_str)
                except (ValueError, IndexError):
                    pass

        # Check for improved content
        if "IMPROVED_CONTENT:" in validation:
            parts = validation.split("IMPROVED_CONTENT:")
            if len(parts) > 1:
                improved = parts[1].strip()
                if len(improved) > 200:  # Substantial improvement
                    final_content = improved

        return final_content, quality_score
