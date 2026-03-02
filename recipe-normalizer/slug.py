"""Slug generation for recipe titles."""

from slugify import slugify as _slugify


def make_slug(title: str) -> str:
    """Convert a recipe title into a URL-friendly slug."""
    return _slugify(title, allow_unicode=False, separator="-")
