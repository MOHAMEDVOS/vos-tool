"""
HTML Sanitization Utilities
Prevents XSS (Cross-Site Scripting) attacks by sanitizing user input before rendering.
"""

import bleach
from html import escape
from typing import Optional

# Allowed HTML tags for safe rendering (minimal set)
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'b', 'i', 'span', 'div',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'blockquote', 'code', 'pre',
]

# Allowed HTML attributes
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    '*': ['class', 'id', 'style'],  # Allow class, id, and style on any tag
}

# Allowed CSS properties (for style attribute)
ALLOWED_STYLES = [
    'color', 'background-color', 'font-size', 'font-weight',
    'text-align', 'margin', 'padding', 'border', 'border-radius',
    'width', 'height', 'display', 'position',
]


def sanitize_html(html_content: str, allow_style: bool = False) -> str:
    """
    Sanitize HTML content to prevent XSS attacks.
    
    This function removes dangerous HTML tags and attributes that could be used
    for XSS attacks, while preserving safe formatting.
    
    Why this is important:
    - Prevents malicious scripts from being injected into the page
    - Protects user sessions from being hijacked
    - Prevents data theft and phishing attacks
    
    Args:
        html_content: HTML string to sanitize
        allow_style: If True, allows style attributes (use with caution)
        
    Returns:
        Sanitized HTML string safe for rendering
    """
    if not html_content:
        return ""
    
    # If style is not allowed, strip all style attributes
    if not allow_style:
        # Remove style attributes using bleach
        html_content = bleach.clean(
            html_content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            styles=[],  # No styles allowed
            strip=True,
        )
    else:
        # Allow safe CSS styles
        html_content = bleach.clean(
            html_content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            styles=ALLOWED_STYLES,
            strip=True,
        )
    
    return html_content


def sanitize_text(text: str) -> str:
    """
    Escape plain text to prevent XSS when rendered as HTML.
    
    This is the safest option - it escapes all HTML special characters,
    preventing any HTML/JavaScript from being executed.
    
    Use this for user-provided text that should be displayed as plain text.
    
    Args:
        text: Plain text to escape
        
    Returns:
        Escaped text safe for HTML rendering
    """
    if not text:
        return ""
    return escape(str(text))


def safe_markdown(content: str, allow_html: bool = False, allow_style: bool = False) -> tuple[str, bool]:
    """
    Prepare content for Streamlit markdown rendering safely.
    
    This function sanitizes content before passing to st.markdown().
    It returns both the sanitized content and whether unsafe_allow_html should be used.
    
    Args:
        content: Content to prepare (may contain HTML)
        allow_html: If True, allow HTML tags (will be sanitized)
        allow_style: If True, allow style attributes (only if allow_html is True)
        
    Returns:
        Tuple of (sanitized_content, should_allow_html)
    """
    if not content:
        return "", False
    
    if allow_html:
        # Sanitize HTML but allow it
        sanitized = sanitize_html(content, allow_style=allow_style)
        return sanitized, True
    else:
        # Escape all HTML - safest option
        sanitized = sanitize_text(content)
        return sanitized, False


