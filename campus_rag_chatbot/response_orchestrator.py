"""
Response Orchestrator - Phase 44: LLM-as-Final-Synthesizer Architecture
=========================================================================

This module implements a unified response orchestration layer where ALL response
paths terminate in the LLM for final natural language generation.

Architecture:
    Query
      ↓
    [Governance Layer] - Intent classification, authority rules, policy
      ↓
    [Retrieval Layer] - Hybrid search, grounding validation, semantic scoring
      ↓
    [Extraction Layer] - Deterministic extractors (deans, awards, dates, contacts)
      ↓
    [LLM Synthesis Layer] - Final response generation (ALL paths end here)
      ↓
    Response

Response Modes:
    - EXTRACTOR_AUTHORITATIVE: Deterministic extractor matched, LLM presents data
    - RAG_AUTHORITATIVE: High-confidence RAG, LLM answers from documents
    - RAG_SUPPLEMENTED: Low semantic relevance, LLM uses context if applicable
    - GENERAL_KNOWLEDGE: No campus relevance, LLM provides general answer
"""

import logging
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from document_manager import DocumentManager
from text_normalizer import normalize_text
from retrieval_validator import (
    extract_query_terms,
    compute_keyword_scores,
    combine_hybrid_scores,
    validate_grounding,
    GroundingResult
)
from confidence_scorer import compute_confidence_score, ConfidenceLevel
from entity_extractors import (
    is_dean_enumeration_query, extract_deans_from_text, format_dean_list,
    is_awards_enumeration_query, extract_awards_from_text, format_awards_list,
    is_event_date_query, extract_events_from_text, format_event_list,
    is_contact_query, extract_contacts_from_text, format_contact_list
)

# Phase 46: Math engine and input preprocessing
try:
    from math_engine import is_calculable_expression, try_calculate
    from input_preprocessor import preprocess_input
    MATH_ENGINE_AVAILABLE = True
except ImportError:
    MATH_ENGINE_AVAILABLE = False
    def is_calculable_expression(text):
        return False
    def try_calculate(text):
        return False, None, None
    def preprocess_input(text, source="text"):
        return text

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class ResponseMode(Enum):
    """Determines how the LLM should synthesize the response."""
    EXTRACTOR_AUTHORITATIVE = "extractor"      # Deterministic extractor matched
    RAG_AUTHORITATIVE = "rag_authoritative"    # High-confidence RAG answer
    RAG_SUPPLEMENTED = "rag_supplemented"      # Context available but low relevance
    GENERAL_KNOWLEDGE = "general"              # No campus relevance, general AI


class SemanticRelevance(Enum):
    """Semantic relevance of retrieved content to the query."""
    HIGH = "high"      # Query terms are central to the content
    MEDIUM = "medium"  # Query terms appear but may be tangential
    LOW = "low"        # Lexical match only, semantic mismatch


@dataclass
class GovernanceResult:
    """Result from the governance layer."""
    intent: str  # "campus", "general", "directory", etc.
    is_safe: bool
    safety_reason: Optional[str] = None
    is_directory_query: bool = False
    requires_authority: bool = True  # Campus queries require document authority


@dataclass
class RetrievalResult:
    """Result from the retrieval layer."""
    documents: List[Any] = field(default_factory=list)
    hybrid_scores: List[Tuple[Any, float]] = field(default_factory=list)
    grounding: Optional[GroundingResult] = None
    semantic_relevance: SemanticRelevance = SemanticRelevance.LOW
    context: str = ""
    query_terms: List[str] = field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    confidence_score: float = 0.0


@dataclass
class ExtractionResult:
    """Result from the extraction layer."""
    matched: bool = False
    extractor_name: Optional[str] = None
    extracted_data: Any = None
    formatted_output: Optional[str] = None


@dataclass
class OrchestratedResponse:
    """Final orchestrated response."""
    answer: str
    mode: ResponseMode
    sources: List[Dict] = field(default_factory=list)
    confidence_level: str = "LOW"
    confidence_score: float = 0.0
    grounding_mode: str = "none"
    rejected: bool = False
    extractor_used: Optional[str] = None
    debug_info: Optional[Dict] = None


# =============================================================================
# PROMPTS FOR EACH RESPONSE MODE
# =============================================================================

SYNTHESIS_PROMPTS = {
    ResponseMode.EXTRACTOR_AUTHORITATIVE: """You are presenting verified campus information from Columban College.
Present the following information clearly, helpfully, and in a natural conversational tone.

VERIFIED INFORMATION:
{extractor_output}

INSTRUCTIONS:
- Present this information naturally, as if speaking to a student or visitor
- Do NOT add any information that is not in the verified data above
- Do NOT make up names, dates, locations, or other details
- You may add brief transitional phrases for natural flow
- Keep the response concise and helpful

Question: {query}""",

    ResponseMode.RAG_AUTHORITATIVE: """You are a campus information assistant for Columban College.
Answer the question using ONLY the information from the provided campus documents.

CAMPUS DOCUMENTS:
{context}

STRICT RULES:
- Answer based ONLY on the information in the documents above
- If the documents don't contain the answer, say "I don't have verified information about that"
- Do NOT invent names, locations, schedules, or any campus-specific details
- Do NOT guess or extrapolate beyond what the documents state
- Be helpful and conversational while staying accurate

Question: {query}""",

    ResponseMode.RAG_SUPPLEMENTED: """You are answering a question. Some campus information was found that may or may not be relevant.

POSSIBLY RELATED CAMPUS INFO:
{context}

INSTRUCTIONS:
- If the campus info above DIRECTLY answers the question, use it
- If the campus info is NOT relevant to the question (e.g., the question is about something general
  and the campus info just happens to mention a related word), IGNORE the campus info entirely
  and answer based on general knowledge
- DO NOT mention or explain that campus information was irrelevant
- DO NOT add disclaimers about campus vs general knowledge
- Just answer the question naturally and helpfully
- Use plain language suitable for reading aloud

Question: {query}""",

    ResponseMode.GENERAL_KNOWLEDGE: """You are a helpful assistant on a campus information kiosk.
Answer this general question naturally and concisely.

RESPONSE STYLE:
- Be conversational and friendly
- Give direct answers without unnecessary preamble
- Use plain language that sounds natural when spoken aloud
- Do NOT use LaTeX, mathematical notation, or special symbols
- For math calculations, state the answer naturally (e.g., "25 plus 17 equals 42")
- Keep responses concise (1-3 sentences for simple questions)
- Do NOT add disclaimers about not being campus-related
{style_hints}

Question: {query}"""
}


# =============================================================================
# STYLE HINTS FOR QUERY-SPECIFIC FORMATTING (Phase 45)
# =============================================================================

STYLE_HINTS = {
    "math_simple": """
MATH RESPONSE STYLE:
- State the numerical answer directly in one sentence
- Use words like "plus", "times", "equals" instead of symbols
- Example: "5 times 5 equals 25" or "That equals 48"
- Do NOT show step-by-step calculations unless asked
""",

    "math_complex": """
MATH RESPONSE STYLE:
- You may explain steps if the calculation is complex
- Keep explanations concise
- You may use mathematical notation if it aids clarity
""",

    "greeting": """
GREETING STYLE:
- Respond warmly in 1-2 sentences
- Be welcoming and friendly
- You may offer to help with campus information
""",

    "definition": """
DEFINITION STYLE:
- Start with the definition directly
- Keep it concise (2-4 sentences)
- Use accessible language
""",

    "default": """
GENERAL STYLE:
- Be helpful and concise
- Use plain language suitable for speaking aloud
- Avoid special notation or symbols
"""
}


# =============================================================================
# RESPONSE ORCHESTRATOR
# =============================================================================

class ResponseOrchestrator:
    """
    Unified response orchestration layer.

    All response paths terminate in the LLM for final synthesis while
    preserving deterministic governance, authority rules, and grounding.
    """

    def __init__(
        self,
        llm: ChatOpenAI,
        doc_manager: DocumentManager,
        config: Optional[Dict] = None
    ):
        self.llm = llm
        self.doc_manager = doc_manager
        self.config = config or {}

        # Configuration defaults
        self.retrieval_top_k = self.config.get("retrieval_top_k", 8)
        self.relevance_threshold = self.config.get("relevance_threshold", 0.5)
        self.min_grounding_terms = self.config.get("min_grounding_terms", 1)
        self.semantic_threshold_high = self.config.get("semantic_threshold_high", 0.78)
        self.semantic_threshold_medium = self.config.get("semantic_threshold_medium", 0.65)

    def process_query(
        self,
        query: str,
        session_id: str,
        memory: Any = None,
        rag_only_mode: bool = False
    ) -> OrchestratedResponse:
        """
        Process a query through all layers and return a synthesized response.

        Args:
            query: The user's question
            session_id: Session identifier
            memory: Conversation memory (optional)
            rag_only_mode: If True, only allow RAG responses (no general knowledge)

        Returns:
            OrchestratedResponse with the final answer and metadata
        """
        logger.info(f"[ORCHESTRATOR] Processing query: {query[:50]}...")

        # Phase 46: Preprocess input (STT artifact cleanup, number normalization)
        query = preprocess_input(query)

        # Phase 46: Fast path for simple arithmetic (deterministic, no LLM needed)
        if MATH_ENGINE_AVAILABLE and is_calculable_expression(query):
            success, answer, result = try_calculate(query)
            if success and answer:
                logger.info(f"[ORCHESTRATOR] Math engine: '{query}' = {result}")
                return OrchestratedResponse(
                    answer=answer,
                    mode=ResponseMode.GENERAL_KNOWLEDGE,
                    sources=[],
                    confidence_level="High",
                    confidence_score=100.0,
                    grounding_mode="deterministic",
                    rejected=False,
                    extractor_used="math_engine"
                )

        # Layer 1: Governance (intent, safety)
        governance = self._apply_governance(query)
        logger.info(f"[ORCHESTRATOR] Governance: intent={governance.intent}, safe={governance.is_safe}")

        # Layer 2: Retrieval
        retrieval = self._perform_retrieval(query)
        logger.info(f"[ORCHESTRATOR] Retrieval: {len(retrieval.documents)} docs, "
                   f"grounded={retrieval.grounding.is_grounded if retrieval.grounding else False}, "
                   f"semantic={retrieval.semantic_relevance.value}")

        # Layer 3: Extraction (try deterministic extractors)
        extraction = self._try_extractors(query, retrieval.context)
        logger.info(f"[ORCHESTRATOR] Extraction: matched={extraction.matched}, "
                   f"extractor={extraction.extractor_name}")

        # Determine response mode
        mode = self._determine_response_mode(
            governance, retrieval, extraction, rag_only_mode
        )
        logger.info(f"[ORCHESTRATOR] Response mode: {mode.value}")

        # Layer 4: LLM Synthesis (ALL paths go through here)
        response = self._synthesize_response(query, mode, retrieval, extraction)

        # Update memory if provided
        if memory:
            try:
                memory.save_context({"question": query}, {"answer": response.answer})
            except Exception as e:
                logger.warning(f"[ORCHESTRATOR] Failed to save memory: {e}")

        return response

    async def process_query_streaming(
        self,
        query: str,
        session_id: str,
        memory: Any = None,
        rag_only_mode: bool = False
    ) -> AsyncGenerator[Dict, None]:
        """
        Process a query with streaming LLM synthesis.

        Yields events in this order:
        1. "metadata" - sources, confidence, mode (BEFORE tokens)
        2. "token" - individual LLM tokens
        3. "complete" - final timing and status

        Args:
            query: The user's question
            session_id: Session identifier
            memory: Conversation memory (optional)
            rag_only_mode: If True, only allow RAG responses

        Yields:
            Dict events with 'event' and 'data' keys
        """
        logger.info(f"[ORCHESTRATOR] Streaming query: {query[:50]}...")
        start_time = time.perf_counter()

        # Phase 46: Preprocess input
        query = preprocess_input(query)

        # Phase 46: Fast path for simple arithmetic (deterministic, no streaming needed)
        if MATH_ENGINE_AVAILABLE and is_calculable_expression(query):
            success, answer, result = try_calculate(query)
            if success and answer:
                logger.info(f"[ORCHESTRATOR] Math engine: '{query}' = {result}")
                yield {
                    "event": "metadata",
                    "data": {
                        "session_id": session_id,
                        "mode": "general",
                        "confidence_level": "High",
                        "confidence_score": 100.0,
                        "sources": [],
                        "response_mode": "general",
                        "extractor_used": "math_engine",
                        "grounding_mode": "deterministic",
                        "debug_info": {
                            "response_mode": "general",
                            "semantic_relevance": "high",
                            "query_terms": [],
                            "grounded": True,
                            "extractor_matched": True,
                            "extractor_name": "math_engine"
                        }
                    }
                }
                yield {"event": "token", "data": {"content": answer, "index": 0}}
                yield {
                    "event": "complete",
                    "data": {
                        "timing": {"retrieval_ms": 0, "llm_ms": 0, "total_ms": 0},
                        "rejected": False,
                        "token_count": 1
                    }
                }
                return

        # Layer 1: Governance (sync)
        governance = self._apply_governance(query)
        logger.info(f"[ORCHESTRATOR] Governance: intent={governance.intent}, safe={governance.is_safe}")

        # Layer 2: Retrieval (sync)
        retrieval_start = time.perf_counter()
        retrieval = self._perform_retrieval(query)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
        logger.info(f"[ORCHESTRATOR] Retrieval: {len(retrieval.documents)} docs, "
                   f"grounded={retrieval.grounding.is_grounded if retrieval.grounding else False}")

        # Layer 3: Extraction (sync)
        extraction = self._try_extractors(query, retrieval.context)
        logger.info(f"[ORCHESTRATOR] Extraction: matched={extraction.matched}")

        # Determine response mode
        mode = self._determine_response_mode(
            governance, retrieval, extraction, rag_only_mode
        )
        logger.info(f"[ORCHESTRATOR] Response mode: {mode.value}")

        # Determine grounding mode string
        grounding_mode = "none"
        if retrieval.grounding:
            grounding_mode = retrieval.grounding.grounding_mode or "keyword"

        # Build sources list
        sources = []
        for doc in retrieval.documents[:4]:
            sources.append({
                "document_name": doc.metadata.get("document_name", "Unknown"),
                "section": doc.metadata.get("section", "Unknown"),
                "chunk_id": doc.metadata.get("chunk_id", 0)
            })

        # Yield metadata event FIRST (before any tokens)
        yield {
            "event": "metadata",
            "data": {
                "session_id": session_id,
                "mode": "campus" if mode != ResponseMode.GENERAL_KNOWLEDGE else "general",
                "confidence_level": retrieval.confidence_level.value if retrieval.confidence_level else "LOW",
                "confidence_score": float(retrieval.confidence_score) if retrieval.confidence_score else 0.0,
                "sources": sources,
                "response_mode": mode.value,
                "extractor_used": extraction.extractor_name,
                "grounding_mode": grounding_mode,
                "debug_info": {
                    "response_mode": mode.value,
                    "semantic_relevance": retrieval.semantic_relevance.value,
                    "query_terms": retrieval.query_terms,
                    "grounded": retrieval.grounding.is_grounded if retrieval.grounding else False,
                    "extractor_matched": extraction.matched,
                    "extractor_name": extraction.extractor_name
                }
            }
        }

        # Layer 4: Streaming LLM Synthesis
        prompt = self._build_prompt_for_mode(query, mode, retrieval, extraction)
        messages = [HumanMessage(content=prompt)]

        llm_start = time.perf_counter()
        token_count = 0
        full_response = ""

        try:
            # Single LLM call with streaming - accumulate tokens locally
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    token_count += 1
                    full_response += chunk.content
                    yield {
                        "event": "token",
                        "data": {"content": chunk.content, "index": token_count}
                    }
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Streaming error: {e}")
            yield {
                "event": "error",
                "data": {"message": str(e), "code": "llm_error"}
            }
            return

        llm_ms = (time.perf_counter() - llm_start) * 1000
        total_ms = (time.perf_counter() - start_time) * 1000

        # Save to memory AFTER streaming completes (using accumulated full_response)
        if memory:
            try:
                memory.save_context({"question": query}, {"answer": full_response})
            except Exception as e:
                logger.warning(f"[ORCHESTRATOR] Failed to save memory: {e}")

        # Yield complete event
        yield {
            "event": "complete",
            "data": {
                "timing": {
                    "retrieval_ms": round(retrieval_ms, 1),
                    "llm_ms": round(llm_ms, 1),
                    "total_ms": round(total_ms, 1)
                },
                "rejected": False,
                "token_count": token_count
            }
        }

    def _build_prompt_for_mode(
        self,
        query: str,
        mode: ResponseMode,
        retrieval: 'RetrievalResult',
        extraction: 'ExtractionResult'
    ) -> str:
        """
        Build prompt string for given response mode.

        Extracted from _synthesize_response for reuse in streaming.
        """
        from query_analyzer import analyze_query, QueryType

        query_analysis = analyze_query(query)
        query_type = query_analysis["query_type"]

        prompt_template = SYNTHESIS_PROMPTS[mode]

        # Prepare prompt variables
        prompt_vars = {"query": query}

        if mode == ResponseMode.EXTRACTOR_AUTHORITATIVE:
            prompt_vars["extractor_output"] = extraction.formatted_output or ""
        elif mode in [ResponseMode.RAG_AUTHORITATIVE, ResponseMode.RAG_SUPPLEMENTED]:
            prompt_vars["context"] = retrieval.context or "No relevant documents found."

        # Add style hints for GENERAL_KNOWLEDGE and RAG_SUPPLEMENTED modes
        if mode in [ResponseMode.GENERAL_KNOWLEDGE, ResponseMode.RAG_SUPPLEMENTED]:
            if query_type == QueryType.MATH:
                if query_analysis["complexity"].value == "simple":
                    prompt_vars["style_hints"] = STYLE_HINTS.get("math_simple", "")
                else:
                    prompt_vars["style_hints"] = STYLE_HINTS.get("math_complex", "")
            elif query_type == QueryType.GREETING:
                prompt_vars["style_hints"] = STYLE_HINTS.get("greeting", "")
            elif query_type == QueryType.DEFINITION:
                prompt_vars["style_hints"] = STYLE_HINTS.get("definition", "")
            else:
                prompt_vars["style_hints"] = STYLE_HINTS.get("default", "")
        else:
            prompt_vars["style_hints"] = ""

        return prompt_template.format(**prompt_vars)

    def _apply_governance(self, query: str) -> GovernanceResult:
        """
        Apply governance rules: intent classification, safety checks, authority requirements.
        """
        from intent_classifier import classify_intent, is_directory_query, safety_check_general_mode

        # Check if directory query (stricter handling)
        is_dir_query = is_directory_query(query)

        # Safety check
        safety = safety_check_general_mode(query)
        is_safe = safety.get("is_safe", True)
        safety_reason = safety.get("reason") if not is_safe else None

        # Intent classification (lightweight - regex based for common patterns)
        intent = "campus"  # Default to campus
        if is_dir_query:
            intent = "directory"

        return GovernanceResult(
            intent=intent,
            is_safe=is_safe,
            safety_reason=safety_reason,
            is_directory_query=is_dir_query,
            requires_authority=True
        )

    def _perform_retrieval(self, query: str) -> RetrievalResult:
        """
        Perform hybrid retrieval with grounding validation and semantic relevance scoring.
        """
        result = RetrievalResult()

        # Normalize query
        normalized_query = normalize_text(query)

        # Extract query terms
        result.query_terms = extract_query_terms(query)

        # Vector retrieval
        if not self.doc_manager.vector_store:
            logger.warning("[ORCHESTRATOR] No vector store available")
            return result

        try:
            retrieval_results = self.doc_manager.vector_store.similarity_search_with_relevance_scores(
                normalized_query,
                k=self.retrieval_top_k,
                score_threshold=self.relevance_threshold
            )
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Retrieval error: {e}")
            return result

        if not retrieval_results:
            return result

        result.documents = [doc for doc, score in retrieval_results]

        # Compute keyword scores
        keyword_scores = compute_keyword_scores(result.query_terms, result.documents)

        # Combine into hybrid scores
        # combine_hybrid_scores returns (reranked_results, detailed_scores)
        result.hybrid_scores, _ = combine_hybrid_scores(
            retrieval_results, keyword_scores
        )

        # Grounding validation
        result.grounding = validate_grounding(
            result.query_terms,
            result.hybrid_scores,
            min_term_matches=self.min_grounding_terms,
            allow_semantic_override=True
        )

        # Compute semantic relevance
        result.semantic_relevance = self._assess_semantic_relevance(
            query, result.query_terms, result.hybrid_scores
        )

        # Build context string
        result.context = self._build_context(result.documents)

        # Compute confidence
        if result.hybrid_scores:
            # Extract scores from hybrid results for confidence computation
            scores = [score for _, score in result.hybrid_scores]
            conf_level, conf_metrics = compute_confidence_score(scores)
            result.confidence_level = conf_level
            result.confidence_score = conf_metrics.get("confidence_score", 0.0)

        return result

    def _assess_semantic_relevance(
        self,
        query: str,
        query_terms: List[str],
        hybrid_results: List[Tuple]
    ) -> SemanticRelevance:
        """
        Assess semantic relevance beyond simple keyword matching.

        This distinguishes between:
        - HIGH: Query terms are central to document content
        - MEDIUM: Query terms appear but may be tangential
        - LOW: Lexical match only, semantic mismatch
        """
        if not hybrid_results:
            return SemanticRelevance.LOW

        top_doc, top_score = hybrid_results[0]
        content = top_doc.page_content.lower()

        # Factor 1: Vector similarity score
        score_factor = SemanticRelevance.LOW
        if top_score >= self.semantic_threshold_high:
            score_factor = SemanticRelevance.HIGH
        elif top_score >= self.semantic_threshold_medium:
            score_factor = SemanticRelevance.MEDIUM

        # Factor 2: Term position analysis
        # Check if terms appear in substantive positions vs titles/metadata
        position_factor = self._analyze_term_positions(query_terms, content)

        # Factor 3: Query type analysis
        # "What is X?" queries about general concepts should get lower relevance
        # if only found in job titles, course names, etc.
        query_type_factor = self._analyze_query_type(query, content)

        # Combine factors (conservative - take minimum)
        factors = [score_factor, position_factor, query_type_factor]

        if SemanticRelevance.LOW in factors:
            return SemanticRelevance.LOW
        elif SemanticRelevance.MEDIUM in factors:
            return SemanticRelevance.MEDIUM
        else:
            return SemanticRelevance.HIGH

    def _analyze_term_positions(
        self,
        query_terms: List[str],
        content: str
    ) -> SemanticRelevance:
        """
        Analyze where query terms appear in the content.
        Terms in titles, job names, or metadata are less relevant than
        terms in explanatory content.
        """
        # Indicators of tangential mentions (terms in names/titles)
        tangential_patterns = [
            "laboratory custodian",
            "office of",
            "department of",
            "college of",
            "coordinator",
            "assistant",
            "secretary",
            "head,",
            "dean,",
        ]

        for term in query_terms:
            # Find term position
            term_pos = content.find(term.lower())
            if term_pos == -1:
                continue

            # Get surrounding context (50 chars each side)
            start = max(0, term_pos - 50)
            end = min(len(content), term_pos + len(term) + 50)
            context_window = content[start:end]

            # Check if term appears in tangential context
            for pattern in tangential_patterns:
                if pattern in context_window:
                    return SemanticRelevance.LOW

        return SemanticRelevance.HIGH

    def _analyze_query_type(self, query: str, content: str) -> SemanticRelevance:
        """
        Analyze query type to detect definition/explanation queries
        that shouldn't match job titles or course names.
        """
        query_lower = query.lower()

        # Definition queries: "What is X?", "Define X", "Explain X"
        definition_patterns = [
            "what is ",
            "what are ",
            "define ",
            "explain ",
            "tell me about ",
            "describe ",
        ]

        is_definition_query = any(query_lower.startswith(p) for p in definition_patterns)

        if not is_definition_query:
            return SemanticRelevance.HIGH

        # For definition queries, check if content is definitional
        # vs just containing the term in a name/title
        definitional_indicators = [
            " is a ",
            " is the ",
            " are ",
            " refers to ",
            " means ",
            " defined as ",
            " involves ",
            " consists of ",
        ]

        has_definition = any(ind in content for ind in definitional_indicators)

        if has_definition:
            return SemanticRelevance.HIGH
        else:
            # Content mentions term but doesn't define it
            return SemanticRelevance.LOW

    def _build_context(self, documents: List) -> str:
        """Build context string from retrieved documents."""
        if not documents:
            return ""

        context_parts = []
        for i, doc in enumerate(documents[:6], 1):  # Limit to top 6
            section = doc.metadata.get("section", "Unknown")
            content = doc.page_content.strip()
            context_parts.append(f"[Source {i}: {section}]\n{content}")

        return "\n\n".join(context_parts)

    def _try_extractors(self, query: str, context: str) -> ExtractionResult:
        """
        Try deterministic extractors in sequence.
        Returns on first match.
        """
        result = ExtractionResult()

        if not context:
            return result

        # Try dean extractor
        if is_dean_enumeration_query(query):
            deans = extract_deans_from_text(context)
            if deans:
                result.matched = True
                result.extractor_name = "deans"
                result.extracted_data = deans
                result.formatted_output = format_dean_list(deans)
                return result

        # Try awards extractor
        if is_awards_enumeration_query(query):
            awards = extract_awards_from_text(context)
            if awards:
                result.matched = True
                result.extractor_name = "awards"
                result.extracted_data = awards
                result.formatted_output = format_awards_list(awards)
                return result

        # Try events extractor
        if is_event_date_query(query):
            events = extract_events_from_text(context)
            if events:
                result.matched = True
                result.extractor_name = "events"
                result.extracted_data = events
                result.formatted_output = format_event_list(events)
                return result

        # Try contacts extractor
        if is_contact_query(query):
            contacts = extract_contacts_from_text(context)
            if contacts:
                result.matched = True
                result.extractor_name = "contacts"
                result.extracted_data = contacts
                result.formatted_output = format_contact_list(contacts)
                return result

        return result

    def _determine_response_mode(
        self,
        governance: GovernanceResult,
        retrieval: RetrievalResult,
        extraction: ExtractionResult,
        rag_only_mode: bool = False
    ) -> ResponseMode:
        """
        Determine the appropriate response mode based on all layer results.
        """
        # If extractor matched with high-relevance retrieval, use extractor
        if extraction.matched and retrieval.semantic_relevance == SemanticRelevance.HIGH:
            return ResponseMode.EXTRACTOR_AUTHORITATIVE

        # If extractor matched but relevance is medium, still use extractor
        # (deterministic data is authoritative)
        if extraction.matched and retrieval.grounding and retrieval.grounding.is_grounded:
            return ResponseMode.EXTRACTOR_AUTHORITATIVE

        # High semantic relevance with grounding = authoritative RAG
        if (retrieval.grounding and
            retrieval.grounding.is_grounded and
            retrieval.semantic_relevance == SemanticRelevance.HIGH):
            return ResponseMode.RAG_AUTHORITATIVE

        # Grounded but low/medium semantic relevance = supplemented mode
        if retrieval.grounding and retrieval.grounding.is_grounded:
            if retrieval.semantic_relevance in [SemanticRelevance.MEDIUM, SemanticRelevance.LOW]:
                if rag_only_mode:
                    # In RAG-only mode, still use authoritative but with caution
                    return ResponseMode.RAG_AUTHORITATIVE
                return ResponseMode.RAG_SUPPLEMENTED

        # No grounding = general knowledge (unless RAG-only mode)
        if rag_only_mode:
            # Force RAG response even without grounding
            return ResponseMode.RAG_AUTHORITATIVE

        return ResponseMode.GENERAL_KNOWLEDGE

    def _synthesize_response(
        self,
        query: str,
        mode: ResponseMode,
        retrieval: RetrievalResult,
        extraction: ExtractionResult
    ) -> OrchestratedResponse:
        """
        Final LLM synthesis layer. ALL response paths terminate here.

        Phase 45: Includes query-aware formatting for kiosk/voice UX.
        """
        from query_analyzer import analyze_query, QueryType

        # Phase 45: Analyze query for response formatting
        query_analysis = analyze_query(query)
        query_type = query_analysis["query_type"]

        # Build prompt using extracted helper
        prompt = self._build_prompt_for_mode(query, mode, retrieval, extraction)

        # Call LLM
        try:
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            answer = response.content

            # Phase 45: Post-process - strip LaTeX for simple math queries
            if query_type == QueryType.MATH and not query_analysis["needs_latex"]:
                answer = self._strip_latex(answer)

        except Exception as e:
            logger.error(f"[ORCHESTRATOR] LLM error: {e}")
            answer = "I apologize, but I encountered an error processing your question. Please try again."

        # Build sources list
        sources = []
        for doc in retrieval.documents[:4]:
            sources.append({
                "document_name": doc.metadata.get("document_name", "Unknown"),
                "section": doc.metadata.get("section", "Unknown"),
                "chunk_id": doc.metadata.get("chunk_id", 0)
            })

        # Determine grounding mode string
        grounding_mode = "none"
        if retrieval.grounding:
            grounding_mode = retrieval.grounding.grounding_mode or "keyword"

        # Map mode to UI mode string
        mode_str = "campus"
        if mode == ResponseMode.GENERAL_KNOWLEDGE:
            mode_str = "general"

        return OrchestratedResponse(
            answer=answer,
            mode=mode,
            sources=sources,
            confidence_level=retrieval.confidence_level.value if retrieval.confidence_level else "LOW",
            confidence_score=retrieval.confidence_score,
            grounding_mode=grounding_mode,
            rejected=False,
            extractor_used=extraction.extractor_name,
            debug_info={
                "response_mode": mode.value,
                "semantic_relevance": retrieval.semantic_relevance.value,
                "query_terms": retrieval.query_terms,
                "grounded": retrieval.grounding.is_grounded if retrieval.grounding else False,
                "extractor_matched": extraction.matched,
                "extractor_name": extraction.extractor_name
            }
        )

    def _strip_latex(self, text: str) -> str:
        """
        Phase 45: Remove LaTeX notation and convert to plain text.

        Used for simple math queries where LaTeX is inappropriate for
        kiosk/voice output.

        Args:
            text: Response text that may contain LaTeX

        Returns:
            Plain text with LaTeX converted to words
        """
        import re

        # Remove $...$ inline math (preserve content)
        text = re.sub(r'\$([^$]+)\$', r'\1', text)

        # Remove \( ... \) inline math
        text = re.sub(r'\\\(([^)]+)\\\)', r'\1', text)

        # Remove \[ ... \] display math
        text = re.sub(r'\\\[([^\]]+)\\\]', r'\1', text)

        # Convert LaTeX operators to words
        text = re.sub(r'\\times', ' times ', text)
        text = re.sub(r'\\div', ' divided by ', text)
        text = re.sub(r'\\cdot', ' times ', text)
        text = re.sub(r'\\pm', ' plus or minus ', text)

        # Convert fractions
        text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1 over \2', text)

        # Convert square root
        text = re.sub(r'\\sqrt\{([^}]+)\}', r'square root of \1', text)

        # Convert exponents
        text = re.sub(r'\^(\d+)', r' to the power of \1', text)
        text = re.sub(r'\^\{(\d+)\}', r' to the power of \1', text)

        # Convert common symbols to words
        text = text.replace(' + ', ' plus ')
        text = text.replace(' - ', ' minus ')
        text = text.replace(' * ', ' times ')
        text = text.replace(' / ', ' divided by ')
        text = text.replace(' = ', ' equals ')

        # Phase 46 Fix: Preserve newlines, only collapse horizontal whitespace
        # Old: re.sub(r'\s+', ' ', text) - destroyed all newlines
        text = re.sub(r'[ \t]+', ' ', text)  # Collapse spaces/tabs only
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 consecutive newlines

        return text.strip()
