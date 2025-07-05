# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server for academic paper search and retrieval. It provides a standardized interface for searching and downloading papers from multiple academic platforms including arXiv, PubMed, bioRxiv, medRxiv, Google Scholar, and IACR ePrint Archive.

## Development Commands

```bash
# Environment setup
uv venv && source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv add -e .

# Run tests
python -m pytest tests/
python tests/test_server.py  # Individual test file

# Run the MCP server
python -m paper_search_mcp.server

# Install for development with optional dev dependencies  
uv add pytest flake8

# Build the Docker image
docker build -t paper-search-server .

```

## Architecture

The codebase follows a plugin-based architecture with separate categories for different document types:

- **`paper_search_mcp/server.py`** - Main MCP server with FastMCP framework, defines all async tool functions
- **`paper_search_mcp/paper.py`** - Standardized `Paper` dataclass for consistent output across all platforms
- **`paper_search_mcp/academic_platforms/`** - Academic paper searcher implementations
- **`paper_search_mcp/government_platforms/`** - Government document searcher implementations
- **`tests/`** - Unit tests for each platform searcher and server functionality

### Academic Platform Integration

Each academic platform has its own searcher class in `academic_platforms/`:

- `arxiv.py` - arXiv preprint server (RSS feeds)
- `pubmed.py` - PubMed biomedical database (E-utilities API) 
- `biorxiv.py` / `medrxiv.py` - bioRxiv/medRxiv preprint servers (web scraping)
- `google_scholar.py` - Google Scholar (web scraping)
- `iacr.py` - IACR ePrint Archive for cryptography papers
- `hub.py` - Sci-Hub integration (commented out)

### Government Platform Integration

Government document platforms in `government_platforms/`:

- `gao.py` - Government Accountability Office reports and publications (RSS feeds + web scraping)
- `jan6.py` - January 6th Committee documents from Internet Archive (API + OCR text)

### Tool Categories

The MCP server exposes three types of tools for each platform:

- **Search tools**: `search_arxiv`, `search_pubmed`, `search_gao`, `search_jan6`, etc. - Return paper/document metadata
- **Download tools**: `download_arxiv`, `download_biorxiv`, `download_gao`, `download_jan6`, etc. - Download PDF files
- **Read tools**: `read_arxiv_paper`, `read_iacr_paper`, `read_gao_report`, `read_jan6_document`, etc. - Extract text from papers/documents

## Dependencies

Core dependencies (see `pyproject.toml`):

- `fastmcp` - MCP server framework
- `mcp[cli]>=1.6.0` - MCP SDK
- `requests` - HTTP client for API calls
- `feedparser` - XML/RSS parsing (arXiv)
- `PyPDF2>=3.0.0` - PDF text extraction
- `beautifulsoup4>=4.12.0` + `lxml>=4.9.0` - HTML parsing for web scraping

## Adding New Platforms

### Academic Platforms

1. Create new searcher class in `academic_platforms/` implementing the common interface
2. Add searcher instance to `server.py`
3. Define search/download/read tool functions following existing patterns
4. Add comprehensive tests in `tests/`
5. Update platform support list in README.md

### Government Platforms

1. Create new searcher class in `government_platforms/` extending `DocumentSource` interface
2. Add searcher instance to `server.py` with import from `government_platforms`
3. Define search/download/read tool functions (e.g., `search_[platform]`, `download_[platform]`, `read_[platform]_report`)
4. Handle government-specific metadata (report types, agency names, etc.) in `Paper.extra` field
5. Add comprehensive tests in `tests/`
6. Update government platform support list in README.md


## Coding standards

### Python

- Ensure that all files, classes, and methods have docstrings
- Ensure that all whitespace is removed from the ends of lines
- Ensure that all logger() calls use % interpolation rather than f-strings

### Markdown

- Ensure a blank line exists surounding each heading line and list

## Testing

Tests use Python's built-in `unittest` framework with `asyncio.run()` for async
tool testing. Each platform has dedicated test files that verify search
functionality and result format consistency.

Use a test-driven development (TDD) methodology where possible, writing tests
before producing the minimal viable code necessary to make tests pass. This focuses
development and results in more quickly converging on a production-ready product.
