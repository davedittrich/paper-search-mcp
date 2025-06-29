# paper_search_mcp/server.py
from typing import List, Dict, Optional
import httpx
from mcp.server.fastmcp import FastMCP
from .academic_platforms.arxiv import ArxivSearcher
from .academic_platforms.pubmed import PubMedSearcher
from .academic_platforms.biorxiv import BioRxivSearcher
from .academic_platforms.medrxiv import MedRxivSearcher
from .academic_platforms.google_scholar import GoogleScholarSearcher
from .academic_platforms.iacr import IACRSearcher
from .academic_platforms.semantic import SemanticSearcher

# from .academic_platforms.hub import SciHubSearcher
from .government_platforms.gao import GAOSearcher
from .government_platforms.jan6 import Jan6Searcher
from .government_platforms.justsecurity import JustSecuritySearcher
from .government_platforms.govinfo import GovInfoSearcher
from .paper import Paper

# Initialize MCP server
mcp = FastMCP("paper_search_server")

# Instances of searchers
arxiv_searcher = ArxivSearcher()
pubmed_searcher = PubMedSearcher()
biorxiv_searcher = BioRxivSearcher()
medrxiv_searcher = MedRxivSearcher()
google_scholar_searcher = GoogleScholarSearcher()
iacr_searcher = IACRSearcher()
semantic_searcher = SemanticSearcher()
# scihub_searcher = SciHubSearcher()
gao_searcher = GAOSearcher()
jan6_searcher = Jan6Searcher()
justsecurity_searcher = JustSecuritySearcher()
govinfo_searcher = GovInfoSearcher()

# Asynchronous helper to adapt synchronous searchers
async def async_search(searcher, query: str, max_results: int, **kwargs) -> List[Dict]:
    async with httpx.AsyncClient() as client:
        # Assuming searchers use requests internally; we'll call synchronously for now
        if 'year' in kwargs:
            papers = searcher.search(query, year=kwargs['year'], max_results=max_results)
        else:
            papers = searcher.search(query, max_results=max_results)
        return [paper.to_dict() for paper in papers]


# Tool definitions
@mcp.tool()
async def search_arxiv(query: str, max_results: int = 10) -> List[Dict]:
    """Search academic papers from arXiv.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(arxiv_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_pubmed(query: str, max_results: int = 10) -> List[Dict]:
    """Search academic papers from PubMed.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(pubmed_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_biorxiv(query: str, max_results: int = 10) -> List[Dict]:
    """Search academic papers from bioRxiv.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(biorxiv_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_medrxiv(query: str, max_results: int = 10) -> List[Dict]:
    """Search academic papers from medRxiv.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(medrxiv_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_google_scholar(query: str, max_results: int = 10) -> List[Dict]:
    """Search academic papers from Google Scholar.

    Args:
        query: Search query string (e.g., 'machine learning').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    papers = await async_search(google_scholar_searcher, query, max_results)
    return papers if papers else []


@mcp.tool()
async def search_iacr(
    query: str, max_results: int = 10, fetch_details: bool = True
) -> List[Dict]:
    """Search academic papers from IACR ePrint Archive.

    Args:
        query: Search query string (e.g., 'cryptography', 'secret sharing').
        max_results: Maximum number of papers to return (default: 10).
        fetch_details: Whether to fetch detailed information for each paper (default: True).
    Returns:
        List of paper metadata in dictionary format.
    """
    async with httpx.AsyncClient() as client:
        papers = iacr_searcher.search(query, max_results, fetch_details)
        return [paper.to_dict() for paper in papers] if papers else []


@mcp.tool()
async def download_arxiv(paper_id: str, save_path: str = "./downloads") -> str:
    """Download PDF of an arXiv paper.

    Args:
        paper_id: arXiv paper ID (e.g., '2106.12345').
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        Path to the downloaded PDF file.
    """
    async with httpx.AsyncClient() as client:
        return arxiv_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def download_pubmed(paper_id: str, save_path: str = "./downloads") -> str:
    """Attempt to download PDF of a PubMed paper.

    Args:
        paper_id: PubMed ID (PMID).
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        str: Message indicating that direct PDF download is not supported.
    """
    try:
        return pubmed_searcher.download_pdf(paper_id, save_path)
    except NotImplementedError as e:
        return str(e)


@mcp.tool()
async def download_biorxiv(paper_id: str, save_path: str = "./downloads") -> str:
    """Download PDF of a bioRxiv paper.

    Args:
        paper_id: bioRxiv DOI.
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        Path to the downloaded PDF file.
    """
    return biorxiv_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def download_medrxiv(paper_id: str, save_path: str = "./downloads") -> str:
    """Download PDF of a medRxiv paper.

    Args:
        paper_id: medRxiv DOI.
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        Path to the downloaded PDF file.
    """
    return medrxiv_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def download_iacr(paper_id: str, save_path: str = "./downloads") -> str:
    """Download PDF of an IACR ePrint paper.

    Args:
        paper_id: IACR paper ID (e.g., '2009/101').
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        Path to the downloaded PDF file.
    """
    return iacr_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_arxiv_paper(paper_id: str, save_path: str = "./downloads") -> str:
    """Read and extract text content from an arXiv paper PDF.

    Args:
        paper_id: arXiv paper ID (e.g., '2106.12345').
        save_path: Directory where the PDF is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return arxiv_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
async def read_pubmed_paper(paper_id: str, save_path: str = "./downloads") -> str:
    """Read and extract text content from a PubMed paper.

    Args:
        paper_id: PubMed ID (PMID).
        save_path: Directory where the PDF would be saved (unused).
    Returns:
        str: Message indicating that direct paper reading is not supported.
    """
    return pubmed_searcher.read_paper(paper_id, save_path)


@mcp.tool()
async def read_biorxiv_paper(paper_id: str, save_path: str = "./downloads") -> str:
    """Read and extract text content from a bioRxiv paper PDF.

    Args:
        paper_id: bioRxiv DOI.
        save_path: Directory where the PDF is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return biorxiv_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
async def read_medrxiv_paper(paper_id: str, save_path: str = "./downloads") -> str:
    """Read and extract text content from a medRxiv paper PDF.

    Args:
        paper_id: medRxiv DOI.
        save_path: Directory where the PDF is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return medrxiv_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
async def read_iacr_paper(paper_id: str, save_path: str = "./downloads") -> str:
    """Read and extract text content from an IACR ePrint paper PDF.

    Args:
        paper_id: IACR paper ID (e.g., '2009/101').
        save_path: Directory where the PDF is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return iacr_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


@mcp.tool()
async def search_semantic(query: str, year: Optional[str] = None, max_results: int = 10) -> List[Dict]:
    """Search academic papers from Semantic Scholar.

    Args:
        query: Search query string (e.g., 'machine learning').
        year: Optional year filter (e.g., '2019', '2016-2020', '2010-', '-2015').
        max_results: Maximum number of papers to return (default: 10).
    Returns:
        List of paper metadata in dictionary format.
    """
    kwargs = {}
    if year is not None:
        kwargs['year'] = year
    papers = await async_search(semantic_searcher, query, max_results, **kwargs)
    return papers if papers else []


@mcp.tool()
async def download_semantic(paper_id: str, save_path: str = "./downloads") -> str:
    """Download PDF of a Semantic Scholar paper.    

    Args:
        paper_id: Semantic Scholar paper ID, Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        Path to the downloaded PDF file.
    """ 
    return semantic_searcher.download_pdf(paper_id, save_path)


@mcp.tool()
async def read_semantic_paper(paper_id: str, save_path: str = "./downloads") -> str:
    """Read and extract text content from a Semantic Scholar paper. 

    Args:
        paper_id: Semantic Scholar paper ID, Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")
        save_path: Directory where the PDF is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the paper.
    """
    try:
        return semantic_searcher.read_paper(paper_id, save_path)
    except Exception as e:
        print(f"Error reading paper {paper_id}: {e}")
        return ""


# GAO (Government Accountability Office) tools
@mcp.tool()
async def search_gao(
    query: str,
    max_results: int = 10,
    date_filter: str = None,
    topics: str = None,
    agencies: str = None,
) -> List[Dict]:
    """Search Government Accountability Office (GAO) reports and publications.

    Args:
        query: Search query string (e.g., 'cybersecurity', 'defense spending').
        max_results: Maximum number of reports to return (default: 10).
        date_filter: Date filter ('week', 'month', '6months', 'year') or None.
        topics: Comma-separated topic filters (e.g., 'Agriculture,Healthcare').
        agencies: Comma-separated agency filters (e.g., 'Department of Defense,NASA').
    Returns:
        List of GAO report metadata in dictionary format.
    """
    try:
        # Parse comma-separated filters
        topic_list = [t.strip() for t in topics.split(',')] if topics else None
        agency_list = [a.strip() for a in agencies.split(',')] if agencies else None

        reports = gao_searcher.search(
            query=query,
            max_results=max_results,
            date_filter=date_filter,
            topics=topic_list,
            agencies=agency_list
        )
        return [report.to_dict() for report in reports]
    except Exception as e:
        print(f"Error searching GAO: {e}")
        return []


@mcp.tool()
async def download_gao(
    report_id: str,
    save_path: str = "./downloads",
) -> str:
    """Download a GAO report PDF.

    Args:
        report_id: GAO report ID (e.g., 'GAO-24-106829').
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        str: Path to the downloaded PDF file.
    """
    try:
        return gao_searcher.download_pdf(report_id, save_path)
    except Exception as e:
        print(f"Error downloading GAO report {report_id}: {e}")
        return ""


@mcp.tool()
async def read_gao_report(
    report_id: str,
    save_path: str = "./downloads",
) -> str:
    """Read and extract text content from a GAO report PDF.

    Args:
        report_id: GAO report ID (e.g., 'GAO-24-106829').
        save_path: Directory where the PDF is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the report.
    """
    try:
        return gao_searcher.read_document(report_id, save_path)
    except Exception as e:
        print(f"Error reading GAO report {report_id}: {e}")
        return ""


# January 6th Committee tools
@mcp.tool()
async def search_jan6(
    query: str,
    max_results: int = 10,
    document_type: str = None,
    date_filter: str = None,
    source_filter: str = None,
    collection: str = "witness_testimony",
) -> List[Dict]:
    """Search January 6th Committee documents and materials.

    Args:
        query: Search query string (e.g., 'trump', 'testimony', 'capitol police').
        max_results: Maximum number of documents to return (default: 10).
        document_type: Filter by type ('testimony', 'hearing', 'report', 'disclosure').
        date_filter: Date filter ('week', 'month', '6months', 'year') or None.
        source_filter: Source collection filter or None.
        collection: Which collection to search ('witness_testimony', 'committee_materials').
    Returns:
        List of January 6th Committee document metadata in dictionary format.
    """
    try:
        documents = jan6_searcher.search(
            query=query,
            max_results=max_results,
            document_type=document_type,
            date_filter=date_filter,
            source_filter=source_filter,
            collection=collection
        )
        return [doc.to_dict() for doc in documents]
    except Exception as e:
        print(f"Error searching Jan6: {e}")
        return []


@mcp.tool()
async def download_jan6(
    document_id: str,
    save_path: str = "./downloads",
) -> str:
    """Download a January 6th Committee document PDF.

    Args:
        document_id: Document identifier (e.g., Internet Archive identifier).
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        str: Path to the downloaded PDF file.
    """
    try:
        return jan6_searcher.download_pdf(document_id, save_path)
    except Exception as e:
        print(f"Error downloading Jan6 document {document_id}: {e}")
        return ""


@mcp.tool()
async def read_jan6_document(
    document_id: str,
    save_path: str = "./downloads",
) -> str:
    """Read and extract text content from a January 6th Committee document PDF.

    Args:
        document_id: Document identifier (e.g., Internet Archive identifier).
        save_path: Directory where the PDF is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the document.
    """
    try:
        return jan6_searcher.read_document(document_id, save_path)
    except Exception as e:
        print(f"Error reading Jan6 document {document_id}: {e}")
        return ""


# Just Security tools
@mcp.tool()
async def search_justsecurity(
    query: str,
    max_results: int = 10,
    clearinghouse: str = "all",
    document_type: str = None,
    date_filter: str = None,
) -> List[Dict]:
    """Search Just Security legal and national security documents.

    Args:
        query: Search query string (e.g., 'january 6', 'trump trials', 'classified documents').
        max_results: Maximum number of documents to return (default: 10).
        clearinghouse: Which clearinghouse to search ('jan6', 'trump_trials', 'russia', 'mar_a_lago', 'manhattan_da', 'all').
        document_type: Filter by type ('analysis', 'court_filing', 'transcript', 'timeline', 'report').
        date_filter: Date filter ('week', 'month', '6months', 'year') or None.
    Returns:
        List of Just Security document metadata in dictionary format.
    """
    try:
        documents = justsecurity_searcher.search(
            query=query,
            max_results=max_results,
            clearinghouse=clearinghouse,
            document_type=document_type,
            date_filter=date_filter
        )
        return [doc.to_dict() for doc in documents]
    except Exception as e:
        print(f"Error searching Just Security: {e}")
        return []


@mcp.tool()
async def download_justsecurity(
    document_id: str,
    save_path: str = "./downloads",
) -> str:
    """Download a Just Security document as HTML.

    Args:
        document_id: Document identifier (e.g., post ID or URL slug).
        save_path: Directory to save the document (default: './downloads').
    Returns:
        str: Path to the downloaded HTML file.
    """
    try:
        return justsecurity_searcher.download_document(document_id, save_path)
    except Exception as e:
        print(f"Error downloading Just Security document {document_id}: {e}")
        return ""


@mcp.tool()
async def read_justsecurity_document(
    document_id: str,
    save_path: str = "./downloads",
) -> str:
    """Read and extract text content from a Just Security document.

    Args:
        document_id: Document identifier (e.g., post ID or URL slug).
        save_path: Directory where the document is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the document.
    """
    try:
        return justsecurity_searcher.read_document(document_id, save_path)
    except Exception as e:
        print(f"Error reading Just Security document {document_id}: {e}")
        return ""


# GovInfo tools
@mcp.tool()
async def search_govinfo(
    query: str,
    max_results: int = 10,
    collection: str = "all",
    date_range: str = None,
    congress: str = None,
    doc_class: str = None,
) -> List[Dict]:
    """Search official U.S. Government documents via GovInfo.gov.

    Args:
        query: Search query string (e.g., 'climate change', 'healthcare', 'defense').
        max_results: Maximum number of documents to return (default: 10).
        collection: Collection category ('congressional', 'regulatory', 'presidential', 'legal', 'reports', 'all') or specific collection code (e.g., 'BILLS', 'FR').
        date_range: Date range filter (e.g., '2023', '2023-01', '2023-01-01:2023-12-31').
        congress: Congress number filter (e.g., '118').
        doc_class: Document class filter (e.g., 'bills', 'hr').
    Returns:
        List of government document metadata in dictionary format.
    """
    try:
        documents = govinfo_searcher.search(
            query=query,
            max_results=max_results,
            collection=collection,
            date_range=date_range,
            congress=congress,
            doc_class=doc_class
        )
        return [doc.to_dict() for doc in documents]
    except Exception as e:
        print(f"Error searching GovInfo: {e}")
        return []


@mcp.tool()
async def download_govinfo(
    package_id: str,
    save_path: str = "./downloads",
) -> str:
    """Download a government document PDF from GovInfo.gov.

    Args:
        package_id: GovInfo package ID (e.g., 'BILLS-118hr1-ih', 'FR-2023-01-10').
        save_path: Directory to save the PDF (default: './downloads').
    Returns:
        str: Path to the downloaded PDF file.
    """
    try:
        return govinfo_searcher.download_pdf(package_id, save_path)
    except Exception as e:
        print(f"Error downloading GovInfo document {package_id}: {e}")
        return ""


@mcp.tool()
async def read_govinfo_document(
    package_id: str,
    save_path: str = "./downloads",
) -> str:
    """Read and extract text content from a government document.

    Args:
        package_id: GovInfo package ID (e.g., 'BILLS-118hr1-ih', 'FR-2023-01-10').
        save_path: Directory where the PDF is/will be saved (default: './downloads').
    Returns:
        str: The extracted text content of the document.
    """
    try:
        return govinfo_searcher.read_document(package_id, save_path)
    except Exception as e:
        print(f"Error reading GovInfo document {package_id}: {e}")
        return ""


@mcp.tool()
async def get_govinfo_collections() -> List[Dict]:
    """Get available document collections from GovInfo.gov.

    Returns:
        List of available collections with metadata.
    """
    try:
        return govinfo_searcher.get_collections()
    except Exception as e:
        print(f"Error fetching GovInfo collections: {e}")
        return []


if __name__ == "__main__":
    mcp.run(transport="stdio")
