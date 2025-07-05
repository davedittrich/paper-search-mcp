"""MCP January 6th Committee document handler

This module provides access to January 6th Committee documents via multiple APIs:
1. GovInfo.gov API (primary) - Official government document repository
2. Internet Archive API (fallback) - Historical document archive
3. Just Security clearinghouse (enhanced fallback) - Legal analysis and document collection

API Documentation Sources:
- GovInfo.gov API: https://api.govinfo.gov/docs/
- Internet Archive Search API: https://archive.org/help/aboutsearch.htm
- Internet Archive Metadata API: https://archive.org/help/aboutmetadata.htm
- Just Security January 6th Clearinghouse: https://www.justsecurity.org/77022/january-6-clearinghouse/
"""

# Standard imports
import gzip
import logging
import os
import random
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

# External imports
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

# Local imports
from ..paper import Paper


logger = logging.getLogger(__name__)


class DocumentSource:
    """Abstract base class for government document sources"""

    def search(self, query: str, **kwargs: Any) -> List[Paper]:
        """Search for documents based on query and optional filters.

        Args:
            query: Search query string
            **kwargs: Additional search parameters

        Returns:
            List of Paper objects representing documents
        """
        raise NotImplementedError

    def download_pdf(self, document_id: str, save_path: str) -> str:
        """Download a document PDF file.

        Args:
            document_id: Unique identifier for the document
            save_path: Directory path to save the PDF

        Returns:
            Path to the downloaded PDF file
        """
        raise NotImplementedError

    def read_document(self, document_id: str, save_path: str) -> str:
        """Extract text content from a document PDF.

        Args:
            document_id: Unique identifier for the document
            save_path: Directory path where PDF is/will be saved

        Returns:
            Extracted text content of the document
        """
        raise NotImplementedError


class Jan6Searcher(DocumentSource):
    """Searcher for January 6th Committee reports and documents

    This searcher integrates with multiple APIs to provide comprehensive access
    to January 6th Committee documents:

    Primary Data Source: GovInfo.gov API
    - Official U.S. Government Publishing Office API
    - Documentation: https://api.govinfo.gov/docs/
    - Rate Limits: Generous for DEMO_KEY, higher limits with registered key
    - Search Query Syntax: Lucene-based (collection:CPRT january 6 weapons)

    Fallback Data Source: Internet Archive API
    - Historical document archive with January 6th collections
    - Search API: https://archive.org/advancedsearch.php
    - Metadata API: https://archive.org/metadata/{identifier}
    - Rate Limits: 1-2 second delays recommended

    API Response Times:
    - GovInfo.gov: ~2 seconds (government infrastructure)
    - Internet Archive: ~20ms (optimized for speed)
    """

    BASE_URL = "https://api.govinfo.gov"
    SEARCH_API = "https://api.govinfo.gov/search"

    # GovInfo.gov API configuration
    # API Documentation: https://api.govinfo.gov/docs/
    # API Key Registration: https://api.govinfo.gov/
    API_KEY = "DEMO_KEY"  # Should be configurable in production

    # Main January 6th Committee collections on GovInfo.gov
    # Collection Documentation: https://www.govinfo.gov/help/collection-browse
    # CPRT = Committee Prints collection contains January 6th Committee materials
    COLLECTIONS = {
        'all': 'CPRT',  # Congressional Committee Prints contain J6 materials
        'transcripts': 'CPRT',
        'reports': 'CPRT'
    }

    # Document type mapping for classification
    DOCUMENT_TYPES = {
        'testimony': ['testimony', 'witness', 'deposition'],
        'hearing': ['hearing', 'statement', 'opening'],
        'report': ['report', 'final', 'summary'],
        'disclosure': ['disclosure', 'financial'],
        'correspondence': ['letter', 'memo', 'email'],
        'video': ['video', 'recording', 'mp4']
    }

    # User agents for rotation
    USER_AGENTS = [
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"),
        ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    ]

    def __init__(self):
        self.session = requests.Session()
        self._setup_session()
        self.timeout = 30
        self.max_retries = 3

    def _setup_session(self):
        """Initialize session with rotating user agent and headers"""
        self.session.headers.update({
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'application/json,text/html,application/xhtml+xml,*/*;q=0.9',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = 'GET',
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and rate limiting"""

        for attempt in range(self.max_retries):
            if method.upper() not in ['GET', 'POST']:
                logger.error("Unexpected method '%s' (must be 'GET' or 'POST')", method)
                return None
            response = None
            try:
                # Rate limiting: wait 1-2 seconds between requests
                time.sleep(random.uniform(1.0, 2.0))
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=self.timeout)
                elif method.upper() == 'POST':
                    if json_data:
                        response = self.session.post(url, json=json_data, timeout=self.timeout)
                    else:
                        response = self.session.post(url, data=params, timeout=self.timeout)

                if response.status_code == 200:  # type: ignore
                    return response
                elif response.status_code == 429:  # type: ignore  # Rate limited
                    wait_time = 2 ** attempt * 5  # Exponential backoff
                    logger.warning("Rate limited, waiting %d seconds", wait_time)
                    time.sleep(wait_time)
                else:
                    logger.warning("HTTP %s for %s", response.status_code, url)  # type: ignore

            except requests.RequestException as e:
                logger.error("Request failed (attempt %d): %s", attempt + 1, e)
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff

        return None

    def search(
        self,
        query: str,
        max_results: int = 10,
        document_type: Optional[str] = None,
        date_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        collection: str = 'witness_testimony',
        **kwargs: Any
    ) -> List[Paper]:
        """
        Search January 6th Committee documents via GovInfo.gov API

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            document_type: Filter by document type ('testimony', 'hearing', 'report', etc.)
            date_filter: Date filter ('week', 'month', '6months', 'year')
            source_filter: Filter by source type ('govinfo'/'government'/'official',
                          'archive'/'internet_archive'/'historical', 'transcript'/'interview',
                          'hearing'/'committee')
            collection: Which collection to search ('witness_testimony', 'committee_materials')

        Returns:
            List of Paper objects representing Jan6 documents
        """
        try:
            # Primary search via GovInfo.gov API
            papers = self._search_via_govinfo_api(
                query, max_results, document_type, collection
            )

            if papers:
                # Apply additional filters if specified
                if date_filter:
                    papers = self._filter_by_date(papers, date_filter)

                if source_filter:
                    papers = self._filter_by_source(papers, source_filter)

                return papers[:max_results]

            # Fallback to Just Security clearinghouse if GovInfo fails
            logger.info("GovInfo.gov search returned no results, trying Just Security fallback")
            return self._search_via_justsecurity_fallback(query, max_results, document_type)

        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    def _search_via_govinfo_api(
        self,
        query: str,
        max_results: int,
        document_type: Optional[str] = None,
        collection: str = 'all'
    ) -> List[Paper]:
        """Search via GovInfo.gov API

        GovInfo.gov Search API Documentation: https://api.govinfo.gov/docs/

        Request Format (POST to https://api.govinfo.gov/search):
        {
            "query": "collection:CPRT january 6 weapons",
            "pageSize": 20,
            "offsetMark": "*"
        }

        Response Data Structure:
        {
            "count": 4,
            "nextPage": null,
            "previousPage": null,
            "packages": [],
            "results": [
                {
                    "packageId": "CTRL0000930041",
                    "lastModified": "2023-01-03T14:52:08Z",
                    "packageLink": "https://api.govinfo.gov/packages/CTRL0000930041",
                    "docClass": "cprt",
                    "title": "CTRL0000930041 - Continued Interview of Cassidy Hutchinson (May 17, 2022)",
                    "congress": "117",
                    "dateIssued": "2022-05-17",
                    "details": {},
                    "download": {
                        "pdfLink": "https://api.govinfo.gov/packages/CTRL0000930041/pdf",
                        "premiumLink": "https://api.govinfo.gov/packages/CTRL0000930041/zip"
                    },
                    "governmentAuthor": ["U.S. House Select Committee to Investigate January 6th"],
                    "collectionCode": "CPRT",
                    "collectionName": "Committee Prints",
                    "resultLink": "https://api.govinfo.gov/packages/CTRL0000930041/summary"
                }
            ]
        }
        """
        papers = []

        try:
            # Build search query for GovInfo API
            search_query = "collection:CPRT january 6"

            # Add user query if provided
            if query.strip():
                search_query += f" {query}"

            # Add document type filter if specified
            if document_type and document_type in self.DOCUMENT_TYPES:
                type_keywords = self.DOCUMENT_TYPES[document_type]
                # For GovInfo, include type keywords in the search
                search_query += f" ({' OR '.join(type_keywords)})"

            # Note: collection parameter is available for future use
            _ = collection  # Acknowledge unused parameter

            # Build API request payload
            payload = {
                "query": search_query,
                "pageSize": min(max_results * 2, 100),
                "offsetMark": "*"
            }

            logger.info("Searching GovInfo.gov with query: %s", search_query)

            # Make POST request to GovInfo API
            response = self._make_request(
                self.SEARCH_API + f"?api_key={self.API_KEY}",
                method='POST',
                json_data=payload
            )

            if not response:
                logger.error("Failed to fetch search results from GovInfo.gov")
                return []

            # Parse JSON response
            data = response.json()

            if 'results' not in data:
                logger.warning("Unexpected response format from GovInfo.gov")
                logger.debug("Response: %s", data)
                return []

            results = data['results']
            total_found = len(results)

            logger.info("Found %d total documents in GovInfo.gov", total_found)

            if total_found == 0:
                logger.warning("No documents found for query: %s", search_query)
                logger.info("Suggestion: Try broader search terms like 'weapons', 'testimony', or specific names")

            for result in results:
                try:
                    paper = self._create_paper_from_govinfo_result(result)
                    if paper:
                        papers.append(paper)

                        if len(papers) >= max_results:
                            break

                except Exception as e:
                    logger.warning("Failed to parse GovInfo result: %s", e)
                    continue

            logger.info("Successfully parsed %d Jan6 documents from GovInfo.gov", len(papers))
            return papers

        except Exception as e:
            logger.error("GovInfo.gov API search failed: %s", e)
            return []

    def _create_paper_from_archive_doc(self, doc: Dict[str, Any]) -> Optional[Paper]:
        """Create a Paper object from an Internet Archive document

        Internet Archive Search API Documentation:
        - https://archive.org/help/aboutsearch.htm
        - https://archive.org/advancedsearch.php

        Internet Archive Document Data Structure:
        {
            "identifier": "january-6th-committee-witness-testimony-20220707-jason-van-tatenhove",
            "title": "Jason Van Tatenhove - J6 Committee Witness Testimony Transcript",
            "description": "January 6th Committee witness testimony transcript. Witness: Jason Van Tatenhove",
            "date": "2022-07-07T00:00:00Z",
            "subject": ["january 6th committee witness testimony transcript"],
            "mediatype": "texts",
            "format": ["Text PDF", "Additional Text PDF"],
            "downloads": 73,
            "creator": ["U.S. House Select Committee to Investigate January 6th"],
            "language": ["English"],
            "collection": ["jan-6th-committee-docs"],
            "addeddate": "2022-07-08 01:23:45",
            "publicdate": "2022-07-08 01:23:45",
            "uploader": "january6committee@example.com"
        }
        """
        try:
            identifier = doc.get('identifier', '')
            title = doc.get('title', '')
            description = doc.get('description', '')

            if not identifier or not title:
                return None

            # Parse publication date
            published_date = None
            date_str = doc.get('date', '')
            if date_str:
                try:
                    # Archive.org dates are typically in ISO format
                    published_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    published_date = datetime.now()
            else:
                published_date = datetime.now()

            # Determine document type
            doc_type = self._determine_document_type(title, description)

            # Build URLs
            url = f"{self.BASE_URL}/details/{identifier}"
            pdf_url = self._build_pdf_url(identifier, doc)

            # Extract categories from subjects
            subjects = doc.get('subject', [])
            if isinstance(subjects, str):
                subjects = [subjects]
            categories = [s for s in subjects if s and len(s) < 50]  # Filter reasonable categories

            return Paper(
                paper_id=identifier,
                title=title,
                authors=['U.S. House Select Committee to Investigate January 6th'],
                abstract=description,
                doi='',  # Jan6 documents don't have DOIs
                published_date=published_date,
                pdf_url=pdf_url,
                url=url,
                source='jan6',
                categories=categories,
                extra={
                    'document_type': doc_type,
                    'archive_identifier': identifier,
                    'mediatype': doc.get('mediatype', ''),
                    'formats': doc.get('format', []),
                    'downloads': doc.get('downloads', 0),
                    'archive_source': True
                }
            )

        except Exception as e:
            logger.error("Failed to create paper from archive document: %s", e)
            return None

    def _create_paper_from_govinfo_result(self, result: Dict[str, Any]) -> Optional[Paper]:
        """Create a Paper object from a GovInfo.gov search result"""
        try:
            title = result.get('title', '')
            package_id = result.get('packageId', '')

            if not package_id or not title:
                return None

            # Parse publication date
            published_date = None
            date_str = result.get('dateIssued', '')
            if date_str:
                try:
                    published_date = datetime.fromisoformat(date_str)
                except ValueError:
                    published_date = datetime.now()
            else:
                published_date = datetime.now()

            # Determine document type from title and package ID
            doc_type = self._determine_govinfo_document_type(title, package_id)

            # Build URLs
            result_link = result.get('resultLink', '')
            pdf_link = result.get('download', {}).get('pdfLink', '')

            # Use result link as main URL, PDF link for download
            url = result_link if result_link else f"{self.BASE_URL}/packages/{package_id}/summary"
            pdf_url = pdf_link if pdf_link else f"{self.BASE_URL}/packages/{package_id}/pdf"

            # Extract government authors
            authors = result.get('governmentAuthor', ['U.S. House Select Committee to Investigate January 6th'])
            if not isinstance(authors, list):
                authors = ['U.S. House Select Committee to Investigate January 6th']

            return Paper(
                paper_id=package_id,
                title=title,
                authors=authors,
                abstract="",  # GovInfo results don't have abstracts in search results
                doi='',  # Committee documents don't have DOIs
                published_date=published_date,
                pdf_url=pdf_url,
                url=url,
                source='jan6',
                categories=[],  # Will be populated by filtering if needed
                extra={
                    'document_type': doc_type,
                    'package_id': package_id,
                    'collection_code': result.get('collectionCode', ''),
                    'last_modified': result.get('lastModified', ''),
                    'govinfo_source': True
                }
            )

        except Exception as e:
            logger.error("Failed to create paper from GovInfo result: %s", e)
            return None

    def _determine_govinfo_document_type(self, title: str, package_id: str) -> str:
        """Determine document type from GovInfo.gov title and package ID"""
        title_lower = title.lower()
        package_lower = package_id.lower()

        # Check for specific patterns in January 6th Committee documents
        if 'transcript' in title_lower or 'interview' in title_lower:
            return 'transcript'
        if 'hearing' in title_lower:
            return 'hearing'
        if 'final report' in title_lower or 'report' in title_lower:
            return 'report'
        if 'witholding' in package_lower or 'withhold' in title_lower:
            return 'withheld_document'
        if 'web-' in package_lower or 'video' in title_lower:
            return 'video'
        return 'document'

    def _build_pdf_url(self, identifier: str, doc: Dict[str, Any]) -> str:
        """Build PDF download URL for Internet Archive document"""
        # Check if document has PDF format
        formats = doc.get('format', [])
        if isinstance(formats, str):
            formats = [formats]

        # Look for PDF formats
        pdf_formats = [f for f in formats if 'pdf' in f.lower()]

        if pdf_formats:
            # Use the first PDF format found
            # Internet Archive PDF URLs typically follow this pattern
            return f"{self.BASE_URL}/download/{identifier}/{identifier}.pdf"
        # Some documents may have PDFs with different naming
        return f"{self.BASE_URL}/download/{identifier}"

    def _determine_document_type(self, title: str, description: str) -> str:
        """Determine document type based on title and description"""
        text_to_analyze = f"{title} {description}".lower()

        for doc_type, keywords in self.DOCUMENT_TYPES.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                return doc_type

        return 'document'  # Default type

    def _filter_by_date(self, papers: List[Paper], date_filter: str) -> List[Paper]:
        """Filter papers by date range"""
        now = datetime.now()
        if date_filter == 'week':
            cutoff = now - timedelta(weeks=1)
        elif date_filter == 'month':
            cutoff = now - timedelta(days=30)
        elif date_filter == '6months':
            cutoff = now - timedelta(days=180)
        elif date_filter == 'year':
            cutoff = now - timedelta(days=365)
        else:
            return papers  # Unknown filter, return all

        return [p for p in papers if p.published_date and p.published_date >= cutoff]

    def _filter_by_source(self, papers: List[Paper], source_filter: str) -> List[Paper]:
        """Filter papers by source type"""
        if not source_filter:
            return papers

        source_filter_lower = source_filter.lower()

        # Define source type mappings
        if source_filter_lower in ['govinfo', 'government', 'official']:
            # Filter for GovInfo.gov documents
            return [p for p in papers if p.extra and p.extra.get('govinfo_source', False)]
        if source_filter_lower in ['archive', 'internet_archive', 'historical']:
            # Filter for Internet Archive documents
            return [p for p in papers if p.extra and p.extra.get('archive_source', False)]
        if source_filter_lower in ['transcript', 'interview']:
            # Filter for transcripts/interviews
            return [p for p in papers if (p.extra and 'transcript' in p.extra.get('document_type', '').lower()) or 'interview' in p.title.lower()]
        if source_filter_lower in ['hearing', 'committee']:
            # Filter for hearings/committee materials
            return [p for p in papers if p.extra and 'hearing' in p.extra.get('document_type', '').lower()]
        # Unknown filter, return all
        logger.warning("Unknown source filter '%s', returning all results", source_filter)
        return papers

    def _search_via_justsecurity_fallback(
        self,
        query: str,
        max_results: int,
        document_type: Optional[str] = None
    ) -> List[Paper]:
        """Fallback search via Just Security January 6th clearinghouse

        Just Security Clearinghouse: https://www.justsecurity.org/77022/january-6-clearinghouse/

        This is a third-tier fallback that uses the Just Security platform
        to search their comprehensive January 6th Committee document clearinghouse.
        """
        try:
            # Import JustSecurity searcher for fallback
            from .justsecurity import JustSecuritySearcher

            justsecurity_searcher = JustSecuritySearcher()

            # Search Just Security's Jan6 clearinghouse
            papers = justsecurity_searcher.search(
                query=query,
                max_results=max_results,
                clearinghouse='jan6',
                document_type=document_type
            )

            # Convert source to maintain consistency with Jan6 API
            for paper in papers:
                paper.source = 'jan6'
                if paper.extra:
                    paper.extra['justsecurity_fallback'] = True

            logger.info("Just Security fallback returned %d documents", len(papers))
            return papers

        except Exception as e:
            logger.error("Just Security fallback search failed: %s", e)
            return []

    def download_pdf(
        self,
        document_id: str,
        save_path: str,
    ) -> str:
        """Download January 6th Committee document PDF from GovInfo.gov"""

        try:
            # Build GovInfo PDF URL
            pdf_url = f"{self.BASE_URL}/packages/{document_id}/pdf?api_key={self.API_KEY}"

            # Download the PDF
            response = self._make_request(pdf_url)
            if not response or response.status_code != 200:
                status_msg = response.status_code if response else 'no response'
                raise RuntimeError(f"Could not download PDF from GovInfo.gov (HTTP {status_msg})")

            # Save PDF file
            os.makedirs(save_path, exist_ok=True)
            filename = f"{document_id}.pdf"
            filepath = os.path.join(save_path, filename)

            with open(filepath, 'wb') as f:
                f.write(response.content)

            logger.info("Downloaded Jan6 document: %s", filepath)
            return filepath

        except Exception as e:
            logger.error("Failed to download Jan6 document %s: %s", document_id, e)
            raise

    def read_document(
        self,
        document_id: str,
        save_path: str,
    ) -> str:
        """Extract text from January 6th Committee document PDF"""

        try:
            filepath = os.path.join(save_path, f"{document_id}.pdf")

            # Download if not exists
            if not os.path.exists(filepath):
                self.download_pdf(document_id, save_path)

            # First, try to get text directly from GovInfo.gov (they often have text versions)
            text_content = self._get_govinfo_text(document_id)
            if text_content:
                return text_content

            # Fallback: Extract text using PyPDF2
            with open(filepath, 'rb') as file:
                pdf_reader = PdfReader(file)
                text_content = []

                for page in pdf_reader.pages:
                    text_content.append(page.extract_text())

                full_text = '\n'.join(text_content)

                if not full_text.strip():
                    return "Error: Could not extract text from PDF (may be image-based)"

                return full_text

        except Exception as e:
            logger.error("Failed to read Jan6 document %s: %s", document_id, e)
            return f"Error reading document: {str(e)}"

    def _get_govinfo_text(self, document_id: str) -> Optional[str]:
        """Try to get text content directly from GovInfo.gov

        GovInfo.gov Package API Documentation: https://api.govinfo.gov/docs/

        Text Content Endpoints:
        - HTML: https://api.govinfo.gov/packages/{packageId}/htm?api_key={API_KEY}
        - PDF: https://api.govinfo.gov/packages/{packageId}/pdf?api_key={API_KEY}
        - Summary: https://api.govinfo.gov/packages/{packageId}/summary?api_key={API_KEY}

        HTML Response Format:
        Returns raw HTML content that needs to be parsed to extract clean text.
        Common HTML structure includes:
        - <div class="document-content">...</div>
        - <p> tags for paragraphs
        - <h1>, <h2> tags for headings
        - <script> and <style> tags (should be removed)
        """
        try:
            # GovInfo often provides HTML/text versions
            text_url = f"{self.BASE_URL}/packages/{document_id}/htm?api_key={self.API_KEY}"

            response = self._make_request(text_url)
            if response and response.status_code == 200:
                # Parse HTML to extract text
                soup = BeautifulSoup(response.content, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text
                text = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)

                if text.strip():
                    return text

        except Exception as e:
            logger.debug("Could not get text content for %s: %s", document_id, e)

        return None

    def _get_archive_ocr_text(self, document_id: str) -> Optional[str]:
        """Try to get OCR text from Internet Archive

        Internet Archive File Access Documentation:
        - https://archive.org/help/aboutmetadata.htm
        - https://archive.org/download/{identifier}/

        OCR Text File Formats:
        1. DjVu Text: {identifier}_djvu.txt
           - Plain text extracted from DjVu format
           - One line per page or text block

        2. hOCR Searchtext: {identifier}_hocr_searchtext.txt.gz
           - Gzipped text file from hOCR (HTML-based OCR format)
           - More structured but needs decompression

        File URL Patterns:
        - https://archive.org/download/{identifier}/{identifier}_djvu.txt
        - https://archive.org/download/{identifier}/{identifier}_hocr_searchtext.txt.gz
        """
        try:
            # Internet Archive often provides OCR text files
            ocr_url = f"{self.BASE_URL}/download/{document_id}/{document_id}_djvu.txt"

            response = self._make_request(ocr_url)
            if response and response.status_code == 200:
                return response.text

            # Try alternative OCR format
            ocr_url = f"{self.BASE_URL}/download/{document_id}/{document_id}_hocr_searchtext.txt.gz"
            response = self._make_request(ocr_url)
            if response and response.status_code == 200:
                # Handle gzipped content
                return gzip.decompress(response.content).decode('utf-8')

        except Exception as e:
            logger.debug("Could not get OCR text for %s: %s", document_id, e)

        return None

# EOF
