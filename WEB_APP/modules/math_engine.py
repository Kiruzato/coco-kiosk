"""
Math Engine - Phase 46: Deterministic Arithmetic Processing
============================================================
Provides secure, deterministic evaluation of simple arithmetic expressions.

Purpose:
- Detect if a query is a simple math calculation
- Safely evaluate expressions using AST (NOT eval())
- Format results for voice/kiosk output

Security:
- Uses Python's AST module for parsing (no code execution)
- Only allows: numbers, basic operators (+, -, *, /, **, //, %)
- No variables, function calls, imports, or attribute access
- Expression length limits to prevent DoS

This follows the deterministic extractor pattern used for deans/awards.
"""

import ast
import operator
import re
import logging
from typing import Optional, Union, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Maximum expression length to prevent DoS
MAX_EXPRESSION_LENGTH = 200

# Supported AST operators mapped to Python operator functions
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Patterns to detect math-like queries
MATH_QUERY_PATTERNS = [
    r'what\s+is\s+\d',
    r'calculate\s+\d',
    r'compute\s+\d',
    r'how\s+much\s+is\s+\d',
    r'^\d+\s*[+\-*/]',
    r'\d+\s*(plus|minus|times|divided|multiplied)',
]

# Word-to-operator conversions
WORD_TO_OPERATOR = {
    'plus': '+',
    'add': '+',
    'added to': '+',
    'and': '+',
    'minus': '-',
    'subtract': '-',
    'less': '-',
    'take away': '-',
    'times': '*',
    'multiplied by': '*',
    'multiply': '*',
    'x': '*',
    'divided by': '/',
    'divide by': '/',
    'over': '/',
    'to the power of': '**',
    'squared': '**2',
    'cubed': '**3',
}


# =============================================================================
# DETECTION
# =============================================================================

def is_calculable_expression(text: str) -> bool:
    """
    Check if text is a simple arithmetic expression we can evaluate.

    Args:
        text: Input text (should be preprocessed)

    Returns:
        True if this is a simple arithmetic expression
    """
    if not text or len(text) > MAX_EXPRESSION_LENGTH:
        return False

    # Must contain at least one digit
    if not re.search(r'\d', text):
        return False

    # Must contain an operator (symbol or word)
    has_symbol_op = bool(re.search(r'[+\-*/]', text))
    has_word_op = any(word in text.lower() for word in ['plus', 'minus', 'times', 'divided', 'multiplied', 'add', 'subtract'])

    if not (has_symbol_op or has_word_op):
        return False

    # Try to extract and validate
    expr = extract_expression(text)
    if not expr:
        return False

    # Try to evaluate - if it works, it's calculable
    result = safe_evaluate(expr)
    return result is not None


def is_math_query(text: str) -> bool:
    """
    Quick check if query looks like a math question.

    Args:
        text: Input text

    Returns:
        True if this looks like a math question
    """
    text_lower = text.lower().strip()

    # Check against patterns
    for pattern in MATH_QUERY_PATTERNS:
        if re.search(pattern, text_lower):
            return True

    return False


# =============================================================================
# EXPRESSION EXTRACTION
# =============================================================================

def extract_expression(text: str) -> Optional[str]:
    """
    Extract arithmetic expression from natural language text.

    Args:
        text: Input text like "what is 5 plus 3" or "calculate 10 * 2"

    Returns:
        Expression string like "5 + 3" or "10 * 2", or None if not extractable
    """
    if not text:
        return None

    result = text.lower().strip()

    # Remove common prefixes
    prefixes = [
        r'^what\s+is\s*',
        r'^what\'s\s*',
        r'^calculate\s*',
        r'^compute\s*',
        r'^solve\s*',
        r'^how\s+much\s+is\s*',
        r'^tell\s+me\s*',
        r'^the\s+answer\s+to\s*',
    ]
    for prefix in prefixes:
        result = re.sub(prefix, '', result, flags=re.IGNORECASE)

    # Remove trailing question mark and common suffixes
    result = re.sub(r'\?+\s*$', '', result)
    result = re.sub(r'equals?\s*\??\s*$', '', result)
    result = re.sub(r'equal\s+to\s*\??\s*$', '', result)

    # Convert word operators to symbols (order matters - longer phrases first)
    for word, symbol in sorted(WORD_TO_OPERATOR.items(), key=lambda x: -len(x[0])):
        result = re.sub(rf'\b{re.escape(word)}\b', f' {symbol} ', result, flags=re.IGNORECASE)

    # Handle "squared" and "cubed" specially (postfix)
    result = re.sub(r'(\d+)\s*squared\b', r'(\1)**2', result)
    result = re.sub(r'(\d+)\s*cubed\b', r'(\1)**3', result)

    # Keep only valid math characters: digits, operators, parentheses, decimal points, spaces
    result = re.sub(r'[^0-9+\-*/().%\s]', '', result)

    # Clean up whitespace
    result = re.sub(r'\s+', ' ', result).strip()

    # Remove trailing operators (malformed expression)
    result = re.sub(r'[+\-*/]+\s*$', '', result)

    # Basic validation: should have digits and operators
    if not re.search(r'\d', result):
        return None
    if not re.search(r'[+\-*/]', result):
        return None

    return result if result else None


# =============================================================================
# SAFE EVALUATION (AST-BASED)
# =============================================================================

def safe_evaluate(expression: str) -> Optional[float]:
    """
    Safely evaluate an arithmetic expression using AST.

    This does NOT use eval(). It parses the expression into an AST
    and only evaluates safe numeric operations.

    Args:
        expression: Mathematical expression string like "5 + 3 * 2"

    Returns:
        Result as float, or None if expression is invalid/unsafe
    """
    if not expression or len(expression) > MAX_EXPRESSION_LENGTH:
        return None

    try:
        # Clean up whitespace for parsing
        expression = expression.strip()

        # Parse into AST
        tree = ast.parse(expression, mode='eval')

        # Evaluate the tree
        result = _eval_node(tree.body)

        logger.debug(f"[MATH-ENGINE] Evaluated '{expression}' = {result}")
        return result

    except ZeroDivisionError:
        logger.warning(f"[MATH-ENGINE] Division by zero: {expression}")
        return None
    except (SyntaxError, ValueError, TypeError) as e:
        logger.debug(f"[MATH-ENGINE] Failed to evaluate '{expression}': {e}")
        return None
    except Exception as e:
        logger.warning(f"[MATH-ENGINE] Unexpected error evaluating '{expression}': {e}")
        return None


def _eval_node(node: ast.AST) -> float:
    """
    Recursively evaluate an AST node.

    Only handles safe numeric operations. Raises ValueError for
    anything that's not a supported operation.

    Args:
        node: AST node to evaluate

    Returns:
        Numeric result

    Raises:
        ValueError: If node type is not supported (security)
    """
    # Numeric constant (Python 3.8+)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Non-numeric constant: {type(node.value)}")

    # Numeric literal (older Python, fallback)
    if isinstance(node, ast.Num):
        return float(node.n)

    # Binary operation: left op right
    if isinstance(node, ast.BinOp):
        op_func = SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

        left = _eval_node(node.left)
        right = _eval_node(node.right)

        # Special handling for power (prevent huge numbers)
        if isinstance(node.op, ast.Pow):
            if abs(right) > 100:
                raise ValueError("Exponent too large")
            if abs(left) > 1e10:
                raise ValueError("Base too large for exponentiation")

        return op_func(left, right)

    # Unary operation: -x or +x
    if isinstance(node, ast.UnaryOp):
        op_func = SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        operand = _eval_node(node.operand)
        return op_func(operand)

    # Parenthesized expression
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    # Reject everything else for security
    raise ValueError(f"Unsupported node type: {type(node).__name__}")


# =============================================================================
# RESPONSE FORMATTING
# =============================================================================

def format_math_response(result: float, query: Optional[str] = None, voice_friendly: bool = True) -> str:
    """
    Format math result for voice/kiosk output.

    Args:
        result: The calculated result
        query: Original query (for context, optional)
        voice_friendly: If True, format for speech output

    Returns:
        Formatted response string
    """
    # Format the number nicely
    if result == int(result):
        # Whole number
        result_str = f"{int(result):,}"  # Add thousands separators for readability
    elif abs(result) < 0.01:
        # Very small number
        result_str = f"{result:.6f}".rstrip('0').rstrip('.')
    else:
        # Decimal, show up to 4 decimal places
        result_str = f"{result:,.4f}".rstrip('0').rstrip('.')

    if voice_friendly:
        # Remove commas for voice (TTS handles them poorly sometimes)
        result_str_voice = result_str.replace(',', '')
        return f"The answer is {result_str_voice}."
    else:
        return result_str


def format_math_response_with_expression(expression: str, result: float) -> str:
    """
    Format response showing the expression and result.

    Args:
        expression: The mathematical expression
        result: The calculated result

    Returns:
        Formatted response like "5 + 3 = 8"
    """
    # Format result
    if result == int(result):
        result_str = str(int(result))
    else:
        result_str = f"{result:.4f}".rstrip('0').rstrip('.')

    # Clean up expression for display
    expr_display = re.sub(r'\s+', ' ', expression).strip()

    return f"{expr_display} equals {result_str}."


# =============================================================================
# MAIN API
# =============================================================================

def try_calculate(text: str) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Try to calculate a math expression from text.

    This is the main entry point for the math engine.

    Args:
        text: Input text (should be preprocessed)

    Returns:
        Tuple of (success, formatted_response, raw_result)
        - success: True if calculation succeeded
        - formatted_response: Voice-friendly response string, or None
        - raw_result: Numeric result, or None
    """
    if not is_calculable_expression(text):
        return False, None, None

    expr = extract_expression(text)
    if not expr:
        return False, None, None

    result = safe_evaluate(expr)
    if result is None:
        return False, None, None

    response = format_math_response(result)
    logger.info(f"[MATH-ENGINE] Calculated: '{text}' -> {result}")

    return True, response, result
