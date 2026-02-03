"""Template content validation and sanitization."""

import re
from typing import Optional

# Dangerous Jinja2 constructs that could be used for template injection
DANGEROUS_PATTERNS = [
    r'__import__',
    r'eval\s*\(',
    r'exec\s*\(',
    r'compile\s*\(',
    r'open\s*\(',
    r'file\s*\(',
    r'\.__class__',
    r'\.__bases__',
    r'\.__subclasses__',
    r'\.__globals__',
    r'\.__dict__',
    r'config\s*\.',
    r'request\s*\.',
    r'session\s*\.',
]


def validate_template_content(content: str, max_length: int = 10000) -> tuple[bool, Optional[str]]:
    """Validate template content for security.
    
    Args:
        content: Template content to validate
        max_length: Maximum allowed length
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check length
    if len(content) > max_length:
        return False, f"Template content exceeds maximum length of {max_length} characters"
    
    # Check for dangerous patterns (case-insensitive)
    content_lower = content.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, content_lower):
            return False, f"Template content contains potentially dangerous pattern: {pattern}"
    
    # Basic syntax check - try to parse as Jinja2 template
    try:
        from jinja2 import Environment, TemplateSyntaxError
        env = Environment()
        env.parse(content)
    except TemplateSyntaxError as e:
        return False, f"Invalid Jinja2 syntax: {str(e)}"
    except Exception as e:
        # Other errors are OK (e.g., undefined variables)
        pass
    
    return True, None


def sanitize_template_content(content: str) -> str:
    """Sanitize template content (basic cleanup).
    
    Args:
        content: Template content to sanitize
    
    Returns:
        Sanitized content
    """
    # Remove null bytes
    content = content.replace('\x00', '')
    
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Strip leading/trailing whitespace
    content = content.strip()
    
    return content


