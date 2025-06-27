# government_platforms/__init__.py
"""Government document platforms for accessing government reports and publications."""

from .gao import GAOSearcher
from .jan6 import Jan6Searcher

__all__ = ['GAOSearcher', 'Jan6Searcher']
