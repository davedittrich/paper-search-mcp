# Paper Search MCP

A Model Context Protocol (MCP) server for searching and downloading academic papers from multiple sources, including arXiv, PubMed, bioRxiv, and Sci-Hub (optional). Designed for seamless integration with large language models like Claude Desktop.

![PyPI](https://img.shields.io/pypi/v/paper-search-mcp.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
[![smithery badge](https://smithery.ai/badge/@openags/paper-search-mcp)](https://smithery.ai/server/@openags/paper-search-mcp)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
  - [Quick Start](#quick-start)
    - [Install Package](#install-package)
    - [Configure Claude Desktop](#configure-claude-desktop)
  - [For Development](#for-development)
    - [Setup Environment](#setup-environment)
    - [Install Dependencies](#install-dependencies)
- [Contributing](#contributing)
- [Demo](#demo)
- [License](#license)
- [TODO](#todo)

---

## Overview

`paper-search-mcp` is a Python-based MCP server that enables users to search and download academic papers from various platforms. It provides tools for searching papers (e.g., `search_arxiv`) and downloading PDFs (e.g., `download_arxiv`), making it ideal for researchers and AI-driven workflows. Built with the MCP Python SDK, it integrates seamlessly with LLM clients like Claude Desktop.

---

## Features

- **Multi-Source Support**: Search and download papers from arXiv, PubMed, bioRxiv, medRxiv, Google Scholar, and IACR ePrint Archive.
- **Government Document Access**: Search and download government reports from GAO (Government Accountability Office), January 6th Committee documents, official U.S. Government publications via GovInfo.gov, and legal analysis from Just Security.
- **Comprehensive Coverage**: Access to 40+ government document collections including Congressional materials, Federal Register, Presidential documents, and legal publications.
- **Legal & National Security Documents**: Specialized access to Just Security's document clearinghouses covering January 6th Committee materials, Trump trials, congressional investigations, and national security analysis.
- **Standardized Output**: Papers and reports are returned in a consistent dictionary format via the `Paper` class.
- **Asynchronous Tools**: Efficiently handles network requests using `httpx`.
- **MCP Integration**: Compatible with MCP clients for LLM context enhancement.
- **Extensible Design**: Easily add new platforms by extending the `academic_platforms` or `government_platforms` modules.

---

## Installation

`paper-search-mcp` can be installed using `uv` or `pip`. Below are two approaches: a quick start for immediate use and a detailed setup for development.

### Installing via Smithery

To install paper-search-mcp for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@openags/paper-search-mcp):

```bash
npx -y @smithery/cli install @openags/paper-search-mcp --client claude
```

### Quick Start

For users who want to quickly run the server:

1. **Install Package**:

   ```bash
   uv add paper-search-mcp
   ```

2. **Configure Claude Desktop**:
   Add this configuration to `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):
   ```json
   {
     "mcpServers": {
       "paper_search_server": {
         "command": "uv",
         "args": [
           "run",
           "--directory",
           "/path/to/your/paper-search-mcp",
           "-m",
           "paper_search_mcp.server"
         ]
       }
     }
   }
   ```
   > Note: Replace `/path/to/your/paper-search-mcp` with your actual installation path.

### For Development

For developers who want to modify the code or contribute:

1. **Setup Environment**:

   ```bash
   # Install uv if not installed
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Clone repository
   git clone https://github.com/openags/paper-search-mcp.git
   cd paper-search-mcp

   # Create and activate virtual environment
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install Dependencies**:

   ```bash
   # Install project in editable mode
   uv add -e .

   # Add development dependencies (optional)
   uv add pytest flake8
   ```

---

## Contributing

We welcome contributions! Here's how to get started:

1. **Fork the Repository**:
   Click "Fork" on GitHub.

2. **Clone and Set Up**:

   ```bash
   git clone https://github.com/yourusername/paper-search-mcp.git
   cd paper-search-mcp
   pip install -e ".[dev]"  # Install dev dependencies (if added to pyproject.toml)
   ```

3. **Make Changes**:

   - Add new platforms in `academic_platforms/`.
   - Update tests in `tests/`.

4. **Submit a Pull Request**:
   Push changes and create a PR on GitHub.

---

## Demo

<img src="docs\images\demo.png" alt="Demo" width="800">

## TODO

### Supported Platforms

#### Academic Platforms
- [√] arXiv
- [√] PubMed
- [√] bioRxiv
- [√] medRxiv
- [√] Google Scholar
- [√] IACR ePrint Archive

#### Government Platforms
- [√] GAO (Government Accountability Office)
- [√] January 6th Committee (witness testimony, hearings, reports)
- [√] GovInfo.gov (Official U.S. Government documents from all three branches)
- [√] Just Security (Legal analysis and national security document clearinghouses)

### Government Document Collections (via GovInfo.gov)

#### Congressional Materials
- [√] Congressional Bills (BILLS)
- [√] Congressional Record (CREC, CRECB)
- [√] Congressional Reports (CRPT)
- [√] Congressional Hearings (CHRG)
- [√] Committee Prints (CPRT)
- [√] Congressional Documents (CDOC)
- [√] Congressional Directory (CDIR)
- [√] House Journal (HJOURNAL)

#### Federal Regulations & Presidential Documents
- [√] Federal Register (FR)
- [√] Code of Federal Regulations (CFR)
- [√] Presidential Documents (CPD)
- [√] Public Papers of Presidents (PPP)

#### Legal Publications
- [√] Public and Private Laws (PLAW)
- [√] United States Code (USCODE)
- [√] Statutes at Large (STATUTE)
- [√] U.S. Courts Opinions (USCOURTS)

#### Government Reports
- [√] GAO Reports (GAOREPORTS)
- [√] Budget Documents (BUDGET)
- [√] Economic Reports (ERP, ECONI)
- [√] Government Manual (GOVMAN)

### Just Security Document Clearinghouses
- [√] January 6th Committee materials and analysis
- [√] Trump criminal and civil trial documents
- [√] Congressional Russia investigation materials
- [√] Mar-a-Lago classified documents case
- [√] Manhattan DA prosecution materials
- [√] National security legal analysis

### Planned Academic Platforms
- [ ] Semantic Scholar
- [ ] PubMed Central (PMC)
- [ ] Science Direct
- [ ] Springer Link
- [ ] IEEE Xplore
- [ ] ACM Digital Library
- [ ] Web of Science
- [ ] Scopus
- [ ] JSTOR
- [ ] ResearchGate
- [ ] CORE
- [ ] Microsoft Academic

### Planned Government Platforms
- [ ] Federal Court Documents (PACER integration)
- [ ] Congressional Research Service (CRS)
- [ ] Inspector General Reports (cross-agency)
- [ ] USPTO Patent Database
- [ ] EPA Reports
- [ ] CDC Publications
- [ ] Public Citizen document archives
- [ ] Additional legal clearinghouses

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.

---

Happy researching with `paper-search-mcp`! If you encounter issues, open a GitHub issue.
