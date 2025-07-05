"""MCP GovInfo.gov document handler

This module provides access to the official U.S. Government Publishing Office's
digital repository covering all three branches of government including Congressional
materials, Federal Register, Presidential documents, and legal publications.

API Documentation Sources:
- GovInfo.gov API: https://api.govinfo.gov/docs/
- GitHub Repository: https://github.com/usgpo/api
- Collection Documentation: https://www.govinfo.gov/help/collection-browse
"""

# Standard imports
import logging
import os
import random
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
import urllib.parse

# External imports
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

# Local imports
from ..paper import Paper
from .jan6 import DocumentSource


logger = logging.getLogger(__name__)


class GovInfoSearcher(DocumentSource):
    """
    Searcher for official U.S. Government documents via GovInfo.gov API

    This searcher provides comprehensive access to official Federal government
    publications from all three branches of government through the U.S. Government
    Publishing Office's standardized API infrastructure.

    Primary Data Source: GovInfo.gov API
    - Official U.S. Government Publishing Office API
    - Documentation: https://api.govinfo.gov/docs/
    - Rate Limits: 1,000 requests per hour with registered key
    - Search Query Syntax: Lucene-based with collection filtering

    Document Collections Supported:
    - Congressional materials (BILLS, CREC, CHRG, CPRT, CRPT, etc.)
    - Federal regulations (FR, CFR, LSA)
    - Presidential documents (CPD, PPP)
    - Legal materials (PLAW, USCODE, USCOURTS)
    - Government reports (GAO, Budget, Economic indicators)
    """

    BASE_URL = "https://api.govinfo.gov"
    SEARCH_API = f"{BASE_URL}/search"
    COLLECTIONS_API = f"{BASE_URL}/collections"
    PUBLISHED_API = f"{BASE_URL}/published"

    # GovInfo.gov API configuration
    # API Documentation: https://api.govinfo.gov/docs/
    # API Key Registration: https://api.govinfo.gov/
    API_KEY = "DEMO_KEY"  # Should be configurable in production

    # Major document collections organized by category
    # Collection Documentation: https://www.govinfo.gov/help/collection-browse
    COLLECTIONS = {
        'all': [],  # Search all collections
        'congressional': [
            'BILLS',      # Congressional Bills
            'BILLSTATUS', # Bill Status information
            'CREC',       # Congressional Record (daily)
            'CRECB',      # Congressional Record Bound Edition
            'CRPT',       # Congressional Reports
            'CHRG',       # Congressional Hearings
            'CPRT',       # Congressional Committee Prints
            'CDOC',       # Congressional Documents
            'CDIR',       # Congressional Directory
            'CCAL',       # Congressional Calendars
            'HJOURNAL'    # Journal of the House
        ],
        'regulatory': [
            'FR',         # Federal Register
            'CFR',        # Code of Federal Regulations
            'LSA'         # List of CFR Sections Affected
        ],
        'presidential': [
            'CPD',        # Compilation of Presidential Documents
            'PPP'         # Public Papers of the Presidents
        ],
        'legal': [
            'PLAW',       # Public and Private Laws
            'USCODE',     # United States Code
            'STATUTE',    # Statutes at Large
            'USCOURTS'    # U.S. Courts Opinions
        ],
        'reports': [
            'GAOREPORTS', # GAO Reports and Comptroller General Decisions
            'BUDGET',     # Budget of the U.S. Government
            'ERP',        # Economic Report of the President
            'ECONI',      # Economic Indicators
            'GOVMAN',     # United States Government Manual
            'PAI'         # Privacy Act Issuances
        ]
    }

    # Document type classification based on collection codes
    DOCUMENT_TYPE_MAP = {
        # Congressional
        'BILLS': 'bill',
        'BILLSTATUS': 'bill_status',
        'CREC': 'congressional_record',
        'CRECB': 'congressional_record',
        'CRPT': 'congressional_report',
        'CHRG': 'congressional_hearing',
        'CPRT': 'committee_print',
        'CDOC': 'congressional_document',
        'CDIR': 'congressional_directory',
        'CCAL': 'congressional_calendar',
        'HJOURNAL': 'house_journal',

        # Regulatory
        'FR': 'federal_register',
        'CFR': 'code_federal_regulations',
        'LSA': 'cfrr_sections_affected',

        # Presidential
        'CPD': 'presidential_document',
        'PPP': 'presidential_papers',

        # Legal
        'PLAW': 'public_law',
        'USCODE': 'us_code',
        'STATUTE': 'statute',
        'USCOURTS': 'court_opinion',

        # Reports
        'GAOREPORTS': 'gao_report',
        'BUDGET': 'budget_document',
        'ERP': 'economic_report',
        'ECONI': 'economic_indicators',
        'GOVMAN': 'government_manual',
        'PAI': 'privacy_act_issuance'
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
        """
        Initialize the GovInfo searcher
        """
        self.session = requests.Session()
        self._setup_session()
        self.timeout = 30
        self.max_retries = 3

    def _setup_session(self):
        """
        Initialize session with rotating user agent and headers
        """
        self.session.headers.update({
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'application/json,text/html,application/xhtml+xml,*/*;q=0.9',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

    def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = 'GET',
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[requests.Response]:
        """
        Make HTTP request with retry logic and rate limiting
        """
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

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt * 5  # Exponential backoff
                    logger.warning("Rate limited, waiting %d seconds", wait_time)
                    time.sleep(wait_time)
                else:
                    logger.warning("HTTP %s for %s", response.status_code, url)

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
        collection: str = 'all',
        date_range: Optional[str] = None,
        congress: Optional[str] = None,
        doc_class: Optional[str] = None,
        **kwargs: Any
    ) -> List[Paper]:
        """
        Search GovInfo.gov documents via official API

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            collection: Which collection category to search ('congressional', 'regulatory', etc.)
            date_range: Date range filter (e.g., '2023', '2023-01', '2023-01-01:2023-12-31')
            congress: Congress number filter (e.g., '118')
            doc_class: Document class filter (e.g., 'bills', 'hr')

        Returns:
            List of Paper objects representing government documents
        """
        try:
            # Validate collection parameter
            self._validate_collection(collection)

            # Build and execute search
            papers = self._search_via_govinfo_api(
                query, max_results, collection, date_range, congress, doc_class
            )

            return papers[:max_results]

        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    def _validate_collection(self, collection: str):
        """
        Validate collection parameter
        """
        valid_collections = list(self.COLLECTIONS.keys())
        # Also allow individual collection codes
        all_codes = []
        for codes in self.COLLECTIONS.values():
            all_codes.extend(codes)
        valid_collections.extend(all_codes)

        if collection not in valid_collections:
            raise ValueError(f"Invalid collection: {collection}. "
                           f"Valid options: {valid_collections}")

    def _search_via_govinfo_api(
        self,
        query: str,
        max_results: int,
        collection: str = 'all',
        date_range: Optional[str] = None,
        congress: Optional[str] = None,
        doc_class: Optional[str] = None
    ) -> List[Paper]:
        """
        Search via GovInfo.gov API

        GovInfo.gov Search API Documentation: https://api.govinfo.gov/docs/

        Request Format (POST to https://api.govinfo.gov/search):
        {
            "query": "collection:(BILLS) climate change congress:118",
            "pageSize": 100,
            "offsetMark": "*",
            "sortBy": "relevance"
        }
        """
        papers = []

        try:
            # Build search query
            search_query = self._build_search_query(
                query, collection, date_range, congress, doc_class
            )

            # Build API request payload
            payload = {
                "query": search_query,
                "pageSize": min(max_results * 2, 100),
                "offsetMark": "*",
                "sortBy": "relevance"
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
                logger.info("Suggestion: Try broader search terms or different collection filters")

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

            logger.info("Successfully parsed %d government documents from GovInfo.gov", len(papers))
            return papers

        except Exception as e:
            logger.error("GovInfo.gov API search failed: %s", e)
            return []

    def _build_search_query(
        self,
        query: str,
        collection: str = 'all',
        date_range: Optional[str] = None,
        congress: Optional[str] = None,
        doc_class: Optional[str] = None
    ) -> str:
        """
        Build search query for GovInfo API using Lucene syntax
        """
        query_parts = []

        # Add collection filter
        if collection != 'all':
            if collection in self.COLLECTIONS and self.COLLECTIONS[collection]:
                # Collection category (multiple collection codes)
                collection_codes = self.COLLECTIONS[collection]
                collection_filter = f"collection:({' OR '.join(collection_codes)})"
                query_parts.append(collection_filter)
            else:
                # Individual collection code
                query_parts.append(f"collection:{collection}")

        # Add user query
        if query.strip():
            query_parts.append(query.strip())

        # Add date range filter
        if date_range:
            start_date, end_date = self._parse_date_range(date_range)
            if start_date and end_date:
                if start_date == end_date:
                    query_parts.append(f"dateIssued:{start_date}")
                else:
                    query_parts.append(f"dateIssued:[{start_date} TO {end_date}]")

        # Add congress filter
        if congress:
            query_parts.append(f"congress:{congress}")

        # Add document class filter
        if doc_class:
            query_parts.append(f"docClass:{doc_class}")

        return " AND ".join(query_parts) if query_parts else "*"

    def _parse_date_range(self, date_range: str) -> tuple[str, str]:
        """
        Parse date range parameter into start and end dates
        """
        if ':' in date_range:
            # Range format: "2023-01-01:2023-12-31"
            start, end = date_range.split(':', 1)
            return start.strip(), end.strip()
        elif len(date_range) == 4:
            # Year format: "2023"
            return f"{date_range}-01-01", f"{date_range}-12-31"
        elif len(date_range) == 7:
            # Month format: "2023-01"
            year, month = date_range.split('-')
            # Get last day of month
            if month in ['01', '03', '05', '07', '08', '10', '12']:
                last_day = '31'
            elif month in ['04', '06', '09', '11']:
                last_day = '30'
            elif month == '02':
                # Simple leap year check
                year_int = int(year)
                if year_int % 4 == 0 and (year_int % 100 != 0 or year_int % 400 == 0):
                    last_day = '29'
                else:
                    last_day = '28'
            else:
                last_day = '31'
            return f"{date_range}-01", f"{date_range}-{last_day}"
        else:
            # Full date format: "2023-01-15"
            return date_range, date_range

    def _create_paper_from_govinfo_result(self, result: Dict[str, Any]) -> Optional[Paper]:
        """
        Create a Paper object from a GovInfo.gov search result
        """
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

            # Determine document type from collection and details
            doc_type = self._determine_document_type(result)

            # Build URLs
            result_link = result.get('resultLink', '')
            download_info = result.get('download', {})
            pdf_link = download_info.get('pdfLink', '')

            # Use result link as main URL, PDF link for download
            url = result_link if result_link else f"{self.BASE_URL}/packages/{package_id}/summary"
            pdf_url = pdf_link if pdf_link else f"{self.BASE_URL}/packages/{package_id}/pdf"

            # Extract government authors
            authors = result.get('governmentAuthor', [])
            if not isinstance(authors, list):
                authors = [str(authors)] if authors else []

            # Extract collection information
            collection_code = result.get('collectionCode', '')
            collection_name = result.get('collectionName', '')

            # Extract additional details
            details = result.get('details', {})

            return Paper(
                paper_id=package_id,
                title=title,
                authors=authors,
                abstract="",  # GovInfo results don't have abstracts in search results
                doi='',  # Government documents don't have DOIs
                published_date=published_date,
                pdf_url=pdf_url,
                url=url,
                source='govinfo',
                categories=[collection_name] if collection_name else [],
                extra={
                    'document_type': doc_type,
                    'package_id': package_id,
                    'collection_code': collection_code,
                    'collection_name': collection_name,
                    'doc_class': result.get('docClass', ''),
                    'congress': result.get('congress', ''),
                    'last_modified': result.get('lastModified', ''),
                    'details': details,
                    'govinfo_source': True
                }
            )

        except Exception as e:
            logger.error("Failed to create paper from GovInfo result: %s", e)
            return None

    def _determine_document_type(self, result: Dict[str, Any]) -> str:
        """
        Determine document type from GovInfo result
        """
        collection_code = result.get('collectionCode', '')

        # Use collection-based mapping first
        if collection_code in self.DOCUMENT_TYPE_MAP:
            return self.DOCUMENT_TYPE_MAP[collection_code]

        # Fallback to doc class
        doc_class = result.get('docClass', '')
        if doc_class:
            return doc_class

        return 'government_document'  # Default type

    def get_collections(self) -> List[Dict[str, Any]]:
        """
        Fetch available collections from GovInfo API
        """
        try:
            response = self._make_request(
                self.COLLECTIONS_API + f"?api_key={self.API_KEY}"
            )

            if response and response.status_code == 200:
                data = response.json()
                return data.get('collections', [])

        except Exception as e:
            logger.error("Failed to fetch collections: %s", e)

        return []

    def get_package_summary(self, package_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed package information
        """
        try:
            url = f"{self.BASE_URL}/packages/{package_id}/summary"
            response = self._make_request(url + f"?api_key={self.API_KEY}")

            if response and response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.debug("Could not get package summary for %s: %s", package_id, e)

        return None

    def get_published_packages(
        self,
        start_date: str,
        end_date: str,
        collection: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch packages by publication date range
        """
        try:
            url = f"{self.PUBLISHED_API}/{start_date}/{end_date}"
            params = {'api_key': self.API_KEY, 'pageSize': 100}

            if collection:
                params['collection'] = collection

            response = self._make_request(url, params=params)

            if response and response.status_code == 200:
                data = response.json()
                return data.get('packages', [])

        except Exception as e:
            logger.error("Failed to fetch published packages: %s", e)

        return []

    def download_pdf(self, package_id: str, save_path: str) -> str:
        """
        Download government document PDF from GovInfo.gov
        """
        try:
            # Build GovInfo PDF URL
            pdf_url = f"{self.BASE_URL}/packages/{package_id}/pdf?api_key={self.API_KEY}"

            # Download the PDF
            response = self._make_request(pdf_url)
            if not response or response.status_code != 200:
                status_msg = response.status_code if response else 'no response'
                raise RuntimeError(f"Could not download PDF from GovInfo.gov (HTTP {status_msg})")

            # Save PDF file
            os.makedirs(save_path, exist_ok=True)
            filename = f"{package_id}.pdf"
            filepath = os.path.join(save_path, filename)

            with open(filepath, 'wb') as f:
                f.write(response.content)

            logger.info("Downloaded government document: %s", filepath)
            return filepath

        except Exception as e:
            logger.error("Failed to download government document %s: %s", package_id, e)
            raise

    def read_document(self, package_id: str, save_path: str) -> str:
        """
        Extract text from government document
        """
        try:
            filepath = os.path.join(save_path, f"{package_id}.pdf")

            # Download if not exists
            if not os.path.exists(filepath):
                self.download_pdf(package_id, save_path)

            # First, try to get text directly from GovInfo.gov (HTML/TXT versions)
            text_content = self._get_govinfo_text(package_id)
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
            logger.error("Failed to read government document %s: %s", package_id, e)
            return f"Error reading document: {str(e)}"

    def _get_govinfo_text(self, package_id: str) -> Optional[str]:
        """
        Try to get text content directly from GovInfo.gov HTML version
        """
        try:
            # GovInfo often provides HTML/text versions
            text_url = f"{self.BASE_URL}/packages/{package_id}/htm?api_key={self.API_KEY}"

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
            logger.debug("Could not get text content for %s: %s", package_id, e)

        return None

    def _extract_next_page_url(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract next page URL from search response for pagination
        """
        return response_data.get('nextPage')

    def _build_search_url(self) -> str:
        """
        Build search API URL
        """
        return self.SEARCH_API

    def _build_collections_url(self) -> str:
        """
        Build collections API URL
        """
        return self.COLLECTIONS_API

    def _build_package_url(self, package_id: str) -> str:
        """
        Build package API URL
        """
        return f"{self.BASE_URL}/packages/{package_id}"

    def _build_published_url(self, start_date: str, end_date: str) -> str:
        """
        Build published packages API URL
        """
        return f"{self.PUBLISHED_API}/{start_date}/{end_date}"

# EOF
