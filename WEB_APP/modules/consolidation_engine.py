# ==============================================================================
# WARNING: SYNCHRONIZED FILE
# ==============================================================================
# This file exists in TWO locations:
#   1. WEB_APP/modules/consolidation_engine.py       (runtime)
#   2. INGESTION_MODULE/modules/consolidation_engine.py  (ingestion)
#
# These copies are intentionally independent to maintain strict architectural
# isolation between WEB_APP and INGESTION_MODULE. Neither module may import
# from the other.
#
# ANY CHANGES to this file MUST be manually mirrored to the other copy.
# Failure to synchronize will cause behavioral divergence between runtime
# and ingestion environments.
# ==============================================================================
"""
Phase 24: Generic Consolidation Engine
=======================================

Config-driven consolidation framework that replaces hardcoded entity consolidation.
Enables adding new entity types via configuration without code changes.

Pattern Types:
- semantic: Match chunks containing required + anchor patterns (e.g., deans)
- anchor_continuation: Find anchor chunk, then collect continuations by proximity (e.g., prayer)
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from WEB_APP.modules.text_normalizer import normalize_text

logger = logging.getLogger(__name__)

# Default rules path
DEFAULT_RULES_PATH = Path(__file__).parent / "data" / "consolidation_rules.json"

# Embedded fallback rules (used if config file not found)
EMBEDDED_RULES = {
    "version": "1.0",
    "rules": [
        {
            "entity_type": "deans",
            "chunk_id": -1,
            "phase": "18",
            "enabled": True,
            "pattern_type": "semantic",
            "semantic_config": {
                "required_patterns": ["dean"],
                "anchor_patterns": ["Dr.", "Engr.", "Arch.", "Prof.", "Mr.", "Ms.", "Mrs."],
                "exclude_patterns": ["dean's office", "is tasked", "responsibilities"],
                "exclude_in_first_n_chars": 150,
                "exclude_office_patterns": ["office", "building", "room"]
            },
            "content_config": {
                "section_title": "Deans",
                "separator": "\n\n---\n\n",
                "sort_by": "page_number",
                "deduplicate": True,
                "cleanup_patterns": [
                    "^[A-Z][A-Z\\s&]+$",
                    "^\\d+\\.\\s+[A-Z][A-Z\\s]+$",
                    "^Provision\\s+\\d+",
                    "^Article\\s+[IVXLC]+",
                    "^Section\\s+\\d+"
                ]
            }
        },
        {
            "entity_type": "prayer",
            "chunk_id": -2,
            "phase": "21.1",
            "enabled": True,
            "pattern_type": "anchor_continuation",
            "anchor_config": {
                "patterns": ["prayer to st. columban", "prayer to st columban"],
                "match_in": ["section_title", "content"]
            },
            "continuation_config": {
                "max_distance": 3,
                "patterns": ["o beloved columban", "o blessed columban", "through christ our lord",
                            "amen", "because of your love for christ", "fullness of life"],
                "short_match_threshold": 100
            },
            "content_config": {
                "section_title": "Prayer to St. Columban",
                "separator": " ",
                "normalize_whitespace": True,
                "deduplicate": True
            }
        }
    ]
}


class ConsolidationEngine:
    """
    Generic consolidation engine that processes declarative rules.

    Usage:
        engine = ConsolidationEngine()
        documents = engine.consolidate_all(documents)
    """

    def __init__(self, rules_path: Optional[str] = None):
        """
        Initialize engine with rules from config file or embedded defaults.

        Args:
            rules_path: Path to consolidation_rules.json. If None, uses default path.
        """
        self.rules_path = Path(rules_path) if rules_path else DEFAULT_RULES_PATH
        self.rules = self._load_rules()

    def _load_rules(self) -> List[Dict[str, Any]]:
        """Load consolidation rules from config file or embedded defaults."""
        if self.rules_path.exists():
            try:
                with open(self.rules_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                rules = config.get('rules', [])
                # Filter to only enabled rules
                enabled_rules = [r for r in rules if r.get('enabled', True)]
                logger.info(f"[PHASE24] Loaded {len(enabled_rules)} consolidation rules from {self.rules_path}")
                return enabled_rules
            except Exception as e:
                logger.warning(f"[PHASE24] Failed to load rules from {self.rules_path}: {e}")
                logger.info("[PHASE24] Using embedded fallback rules")
                return EMBEDDED_RULES['rules']
        else:
            logger.info(f"[PHASE24] Rules file not found at {self.rules_path}, using embedded rules")
            return EMBEDDED_RULES['rules']

    def consolidate_all(self, documents: List[Document]) -> List[Document]:
        """
        Apply all consolidation rules to documents.

        Args:
            documents: List of Document objects from chunking

        Returns:
            Modified document list with synthetic chunks prepended
        """
        for rule in self.rules:
            entity_type = rule.get('entity_type', 'unknown')
            pattern_type = rule.get('pattern_type')

            try:
                if pattern_type == 'semantic':
                    documents = self._apply_semantic_rule(documents, rule)
                elif pattern_type == 'anchor_continuation':
                    documents = self._apply_anchor_continuation_rule(documents, rule)
                else:
                    logger.warning(f"[PHASE24] Unknown pattern type '{pattern_type}' for entity '{entity_type}'")
            except Exception as e:
                logger.error(f"[PHASE24] Error applying rule for '{entity_type}': {e}")
                # Continue with other rules

        return documents

    def _apply_semantic_rule(self, documents: List[Document], rule: Dict) -> List[Document]:
        """
        Apply semantic pattern rule (e.g., deans).

        Matches chunks containing BOTH required patterns AND anchor patterns,
        while excluding false positive patterns.
        """
        entity_type = rule.get('entity_type')
        config = rule.get('semantic_config', {})
        content_config = rule.get('content_config', {})

        required_patterns = [p.lower() for p in config.get('required_patterns', [])]
        anchor_patterns = [p.lower() for p in config.get('anchor_patterns', [])]
        exclude_patterns = [p.lower() for p in config.get('exclude_patterns', [])]
        exclude_office_patterns = [p.lower() for p in config.get('exclude_office_patterns', [])]
        exclude_in_first_n = config.get('exclude_in_first_n_chars', 150)

        # Collect matching chunks
        matched_chunks = []

        for i, doc in enumerate(documents):
            content = doc.metadata.get('original_text', doc.page_content)
            content_lower = content.lower()

            # Check required patterns (must have ALL)
            has_required = all(p in content_lower for p in required_patterns)
            if not has_required:
                continue

            # Check anchor patterns (must have at least one)
            has_anchor = any(p in content_lower for p in anchor_patterns)
            if not has_anchor:
                continue

            # Check exclusions
            has_exclusion = any(p in content_lower for p in exclude_patterns)
            if has_exclusion:
                continue

            # Check office patterns in first N chars
            first_n_lower = content_lower[:exclude_in_first_n]
            has_office_exclusion = any(p in first_n_lower for p in exclude_office_patterns)
            if has_office_exclusion:
                continue

            # Passed all filters
            matched_chunks.append({
                'chunk_id': doc.metadata.get('chunk_id', i),
                'content': content,
                'pages': doc.metadata.get('page_numbers', []),
                'document': doc
            })

        if not matched_chunks:
            return documents

        # Sort by page number or chunk_id
        sort_by = content_config.get('sort_by', 'page_number')
        if sort_by == 'page_number':
            matched_chunks.sort(key=lambda x: min(x['pages']) if x['pages'] else 999)
        else:
            matched_chunks.sort(key=lambda x: x['chunk_id'])

        # Create synthetic chunk
        synthetic_doc = self._create_synthetic_chunk(matched_chunks, rule)

        logger.info(f"[PHASE24] Created synthetic '{entity_type}' chunk from {len(matched_chunks)} source chunks")

        # Prepend synthetic chunk
        return [synthetic_doc] + documents

    def _apply_anchor_continuation_rule(self, documents: List[Document], rule: Dict) -> List[Document]:
        """
        Apply anchor-continuation pattern rule (e.g., prayer).

        Finds anchor chunk first, then collects continuation chunks
        within max_distance that match continuation patterns.
        """
        entity_type = rule.get('entity_type')
        anchor_config = rule.get('anchor_config', {})
        cont_config = rule.get('continuation_config', {})

        anchor_patterns = [p.lower() for p in anchor_config.get('patterns', [])]
        match_in = anchor_config.get('match_in', ['content'])

        cont_patterns = [p.lower() for p in cont_config.get('patterns', [])]
        max_distance = cont_config.get('max_distance', 3)
        short_threshold = cont_config.get('short_match_threshold', 100)

        # First pass: Find anchor chunk
        anchor_chunk = None
        anchor_chunk_id = None

        for i, doc in enumerate(documents):
            content = doc.metadata.get('original_text', doc.page_content)
            content_lower = content.lower()
            section = doc.metadata.get('section', '').lower()
            section_title = doc.metadata.get('section_title', '').lower()

            is_anchor = False
            for pattern in anchor_patterns:
                if 'section_title' in match_in and pattern in section_title:
                    is_anchor = True
                    break
                if 'section' in match_in and pattern in section:
                    is_anchor = True
                    break
                if 'content' in match_in and pattern in content_lower:
                    is_anchor = True
                    break

            if is_anchor:
                chunk_id = doc.metadata.get('chunk_id', i)
                anchor_chunk_id = chunk_id
                anchor_chunk = {
                    'chunk_id': chunk_id,
                    'content': content,
                    'pages': doc.metadata.get('page_numbers', []),
                    'document': doc
                }
                break

        if anchor_chunk is None:
            return documents

        # Collect chunks starting with anchor
        matched_chunks = [anchor_chunk]

        # Second pass: Find continuation chunks
        for i, doc in enumerate(documents):
            chunk_id = doc.metadata.get('chunk_id', i)

            # Skip anchor
            if chunk_id == anchor_chunk_id:
                continue

            # Check proximity
            if isinstance(chunk_id, int) and isinstance(anchor_chunk_id, int):
                if not (anchor_chunk_id < chunk_id <= anchor_chunk_id + max_distance):
                    continue
            else:
                continue

            content = doc.metadata.get('original_text', doc.page_content)
            content_lower = content.lower()

            # Check for continuation patterns
            is_continuation = False
            for pattern in cont_patterns:
                # Special handling for short patterns like "amen"
                if pattern == 'amen' and len(content) >= short_threshold:
                    continue
                if pattern in content_lower:
                    is_continuation = True
                    break

            if is_continuation:
                matched_chunks.append({
                    'chunk_id': chunk_id,
                    'content': content,
                    'pages': doc.metadata.get('page_numbers', []),
                    'document': doc
                })

        if len(matched_chunks) < 1:
            return documents

        # Sort by chunk_id to maintain order
        matched_chunks.sort(key=lambda x: x['chunk_id'])

        # Create synthetic chunk
        synthetic_doc = self._create_synthetic_chunk(matched_chunks, rule)

        logger.info(f"[PHASE24] Created synthetic '{entity_type}' chunk from {len(matched_chunks)} source chunks")

        # Prepend synthetic chunk
        return [synthetic_doc] + documents

    def _create_synthetic_chunk(self, chunks: List[Dict], rule: Dict) -> Document:
        """
        Create synthetic chunk with standard metadata.

        Handles content joining, deduplication, cleanup, and metadata creation.
        """
        entity_type = rule.get('entity_type')
        chunk_id = rule.get('chunk_id', -1)
        phase = rule.get('phase', '24')
        content_config = rule.get('content_config', {})

        section_title = content_config.get('section_title', entity_type.title())
        separator = content_config.get('separator', '\n\n')
        deduplicate = content_config.get('deduplicate', True)
        normalize_ws = content_config.get('normalize_whitespace', False)
        cleanup_patterns = content_config.get('cleanup_patterns', [])

        # Collect and deduplicate content
        combined_content = []
        source_chunk_ids = []
        source_pages = []

        for chunk in chunks:
            content = chunk['content'].strip()

            if deduplicate and content in combined_content:
                continue

            if content:
                combined_content.append(content)
                source_chunk_ids.append(chunk['chunk_id'])
                source_pages.extend(chunk['pages'])

        # Join content
        synthetic_content = f"{section_title}\n\n" + separator.join(combined_content)

        # Apply cleanup patterns
        if cleanup_patterns:
            lines = synthetic_content.split('\n')
            cleaned_lines = []
            for line in lines:
                line_stripped = line.strip()
                should_remove = False
                for pattern in cleanup_patterns:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        should_remove = True
                        break
                if not should_remove:
                    cleaned_lines.append(line)
            synthetic_content = '\n'.join(cleaned_lines)

        # Apply additional cleanup for deans entity type
        if entity_type == 'deans':
            synthetic_content = self._cleanup_deans_content(synthetic_content)

        # Normalize whitespace if requested
        if normalize_ws:
            synthetic_content = re.sub(r'\s+', ' ', synthetic_content)
            synthetic_content = synthetic_content.replace(' .', '.').replace(' ,', ',')

        # Collapse excessive spaces
        synthetic_content = re.sub(r' {2,}', ' ', synthetic_content)
        synthetic_content = synthetic_content.strip()

        # Get template metadata from first chunk
        template_metadata = chunks[0]['document'].metadata.copy()

        # Create synthetic metadata
        synthetic_metadata = {
            **template_metadata,
            'chunk_id': chunk_id,
            'section': section_title,
            'section_title': section_title,
            'original_text': synthetic_content,
            'is_synthetic': True,
            'entity_type': entity_type,
            'source_chunk_ids': source_chunk_ids,
            'page_numbers': sorted(list(set(source_pages))),
            'element_types': ['Synthetic'],
            'consolidation_phase': phase,
            'num_entities': len(combined_content)
        }

        # Create document with normalized text
        synthetic_doc = Document(
            page_content=normalize_text(synthetic_content),
            metadata=synthetic_metadata
        )

        return synthetic_doc

    def _cleanup_deans_content(self, content: str) -> str:
        """
        Additional cleanup specific to deans consolidation.
        Removes noise headers that may have made it through sectioning.
        """
        noise_headers = [
            'Student Organizations',
            'Student OIrganizations',
            '9 Special Provision',
            'SAS Directors',
            'DIRECTORS & RESEARCH PROPONENTS'
        ]

        lines = content.split('\n')
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Skip noise header lines
            is_noise = any(noise.lower() == line_stripped.lower() for noise in noise_headers)

            # Skip numbered provision lines
            is_provision = re.match(r'^\d+\s+(Special\s+)?Provision\s*$', line_stripped, re.IGNORECASE)

            # Skip SAS Directors list line
            is_sas_directors = line_stripped.startswith('SAS Directors')

            # Skip empty or single-char fragments
            is_fragment = len(line_stripped) == 1 and not line_stripped.isalnum()

            if not is_noise and not is_provision and not is_sas_directors and not is_fragment:
                if line_stripped:  # Skip truly empty lines
                    cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)


# Convenience function for backward compatibility
def consolidate_with_engine(documents: List[Document], rules_path: Optional[str] = None) -> List[Document]:
    """
    Convenience function to consolidate documents using the engine.

    Args:
        documents: List of Document objects
        rules_path: Optional path to rules JSON file

    Returns:
        Documents with synthetic chunks prepended
    """
    engine = ConsolidationEngine(rules_path)
    return engine.consolidate_all(documents)
