"""MCP Just Security document handler

This module provides access to Just Security's comprehensive document clearinghouses
including January 6th Committee materials, Trump trials, congressional investigations,
and other legal/national security documents.

API Documentation Sources:
- Just Security: https://www.justsecurity.org/
- Algolia Search API: https://www.algolia.com/doc/api-reference/search-api/
- WordPress REST API: https://developer.wordpress.org/rest-api/
- RSS Feed: https://www.justsecurity.org/feed/
"""

# Standard imports
import gzip
import logging
import os
import random
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
import urllib.parse

# External imports
import requests
import feedparser
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

# Local imports
from ..paper import Paper
from .jan6 import DocumentSource


logger = logging.getLogger(__name__)


class JustSecuritySearcher(DocumentSource):
    """
    Searcher for Just Security legal and national security documents

    This searcher integrates with multiple APIs to provide comprehensive access
    to Just Security's document clearinghouses covering legal proceedings,
    congressional oversight, national security matters, and government accountability.

    Primary Data Sources:
    1. Algolia Search API - Real-time document search with advanced filtering
    2. WordPress REST API - Detailed post metadata and content
    3. RSS Feeds - Bulk document access and updates

    Document Collections:
    - January 6th Committee materials and analysis
    - Trump criminal and civil trial documents
    - Congressional Russia investigation materials
    - Mar-a-Lago classified documents case
    - Manhattan DA prosecution materials
    - National security and legal analysis
    """

    BASE_URL = "https://www.justsecurity.org"

    # Algolia Search API configuration
    # Documentation: https://www.algolia.com/doc/api-reference/search-api/
    ALGOLIA_APP_ID = "00O7E2708B"
    ALGOLIA_API_KEY = "0cae588c66eb9d1f0c73cd7d70e9be68"  # Read-only public key
    ALGOLIA_INDEX = "prod_wp_searchable_posts"

    # WordPress REST API endpoints
    # Documentation: https://developer.wordpress.org/rest-api/
    WORDPRESS_API = f"{BASE_URL}/wp-json/wp/v2/"

    # RSS Feed for bulk access
    RSS_FEED = f"{BASE_URL}/feed/"

    # Document clearinghouses available
    CLEARINGHOUSES = {
        'all': '',  # Search all clearinghouses
        'jan6': 'january-6-clearinghouse',
        'trump_trials': 'trump-trials-clearinghouse',
        'russia': 'congressional-russia-investigations',
        'mar_a_lago': 'mar-a-lago-documents-clearinghouse',
        'manhattan_da': 'manhattan-da-trump-hush-money',
        'national_security': 'national-security',
        'legal': 'legal-analysis'
    }

    # Document type classification keywords
    DOCUMENT_TYPES = {
        'analysis': ['analysis', 'commentary', 'explainer', 'breakdown'],
        'report': ['report', 'findings', 'summary', 'investigation'],
        'court_filing': ['filing', 'motion', 'brief', 'pleading', 'order', 'ruling'],
        'transcript': ['transcript', 'hearing', 'testimony', 'deposition'],
        'timeline': ['timeline', 'chronology', 'sequence', 'events'],
        'document': ['document', 'letter', 'memo', 'correspondence'],
        'news': ['news', 'update', 'breaking', 'latest']
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
        Initialize the Just Security searcher
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
            'Upgrade-Insecure-Requests': '1',
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
        clearinghouse: str = 'all',
        document_type: Optional[str] = None,
        date_filter: Optional[str] = None,
        **kwargs: Any
    ) -> List[Paper]:
        """
        Search Just Security documents via Algolia API

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            clearinghouse: Which clearinghouse to search ('jan6', 'trump_trials', etc.)
            document_type: Filter by document type ('analysis', 'court_filing', etc.)
            date_filter: Date filter ('week', 'month', '6months', 'year')

        Returns:
            List of Paper objects representing Just Security documents
        """
        try:
            # Validate clearinghouse parameter
            self._validate_clearinghouse(clearinghouse)

            # Primary search via Algolia API
            papers = self._search_via_algolia(
                query, max_results, clearinghouse, document_type
            )

            if papers:
                # Apply additional filters if specified
                if date_filter:
                    papers = self._filter_by_date(papers, date_filter)

                return papers[:max_results]

            # Fallback to RSS feed search if Algolia fails
            logger.info("Algolia search returned no results, trying RSS fallback")
            return self._search_via_rss(query, max_results, document_type)

        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    def _validate_clearinghouse(self, clearinghouse: str):
        """
        Validate clearinghouse parameter
        """
        if clearinghouse not in self.CLEARINGHOUSES:
            raise ValueError(f"Invalid clearinghouse: {clearinghouse}. "
                           f"Valid options: {list(self.CLEARINGHOUSES.keys())}")

    def _search_via_algolia(
        self,
        query: str,
        max_results: int,
        clearinghouse: str = 'all',
        document_type: Optional[str] = None
    ) -> List[Paper]:
        """
        Search via Algolia API

        Algolia Search API Documentation: https://www.algolia.com/doc/api-reference/search-api/

        Request Format (POST to https://APP_ID-dsn.algolia.net/1/indexes/INDEX/query):
        {
            "query": "search terms",
            "hitsPerPage": 20,
            "page": 0,
            "filters": "category:legal",
            "facetFilters": [["clearinghouse:jan6"]]
        }
        """
        papers = []

        try:
            # Build Algolia search URL
            algolia_url = f"https://{self.ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{self.ALGOLIA_INDEX}/query"

            # Build search query
            search_query = query.strip()

            # Add clearinghouse filter if specified
            filters = []
            if clearinghouse != 'all' and clearinghouse in self.CLEARINGHOUSES:
                clearinghouse_slug = self.CLEARINGHOUSES[clearinghouse]
                if clearinghouse_slug:
                    filters.append(f"clearinghouse:{clearinghouse_slug}")

            # Add document type filter if specified
            if document_type and document_type in self.DOCUMENT_TYPES:
                type_keywords = self.DOCUMENT_TYPES[document_type]
                # Add as search terms rather than strict filter
                search_query += f" ({' OR '.join(type_keywords)})"

            # Build request payload
            payload = {
                "query": search_query,
                "hitsPerPage": min(max_results * 2, 100),
                "page": 0,
                "attributesToRetrieve": [
                    "objectID", "title", "content", "url", "date",
                    "author", "categories", "tags"
                ]
            }

            if filters:
                payload["filters"] = " AND ".join(filters)

            logger.info("Searching Just Security via Algolia with query: %s", search_query)

            # Set Algolia-specific headers
            headers = {
                'X-Algolia-Application-Id': self.ALGOLIA_APP_ID,
                'X-Algolia-API-Key': self.ALGOLIA_API_KEY,
                'Content-Type': 'application/json'
            }

            # Make POST request to Algolia
            response = self.session.post(
                algolia_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error("Algolia API request failed: HTTP %s", response.status_code)
                return []

            # Parse JSON response
            data = response.json()

            if 'hits' not in data:
                logger.warning("Unexpected response format from Algolia")
                logger.debug("Response: %s", data)
                return []

            hits = data['hits']
            total_found = len(hits)

            logger.info("Found %d total documents in Just Security", total_found)

            for hit in hits:
                try:
                    paper = self._create_paper_from_algolia_hit(hit)
                    if paper:
                        papers.append(paper)

                        if len(papers) >= max_results:
                            break

                except Exception as e:
                    logger.warning("Failed to parse Algolia hit: %s", e)
                    continue

            logger.info("Successfully parsed %d Just Security documents", len(papers))
            return papers

        except Exception as e:
            logger.error("Algolia API search failed: %s", e)
            return []

    def _create_paper_from_algolia_hit(self, hit: Dict[str, Any]) -> Optional[Paper]:
        """
        Create a Paper object from an Algolia search hit
        """
        try:
            object_id = hit.get('objectID', '')
            title = hit.get('title', '')
            content = hit.get('content', '')

            if not object_id or not title:
                return None

            # Parse publication date
            published_date = None
            date_str = hit.get('date', '')
            if date_str:
                try:
                    # Handle various date formats
                    if 'T' in date_str:
                        published_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        published_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    published_date = datetime.now()
            else:
                published_date = datetime.now()

            # Determine document type
            doc_type = self._determine_document_type(title, content)

            # Extract URL
            url = hit.get('url', f"{self.BASE_URL}/{object_id}/")

            # Extract author information
            authors = []
            author_info = hit.get('author', '')
            if author_info:
                if isinstance(author_info, str):
                    authors = [author_info]
                elif isinstance(author_info, list):
                    authors = author_info

            # Extract categories and tags
            categories = hit.get('categories', [])
            if isinstance(categories, str):
                categories = [categories]
            tags = hit.get('tags', [])
            if isinstance(tags, str):
                tags = [tags]

            # Combine categories and tags
            all_categories = list(set(categories + tags))

            # Create abstract from content excerpt
            abstract = content[:500] + "..." if len(content) > 500 else content

            return Paper(
                paper_id=object_id,
                title=title,
                authors=authors,
                abstract=abstract,
                doi='',  # Just Security articles don't have DOIs
                published_date=published_date,
                pdf_url='',  # Will be determined during download
                url=url,
                source='justsecurity',
                categories=all_categories,
                extra={
                    'document_type': doc_type,
                    'algolia_object_id': object_id,
                    'content_excerpt': content[:1000],
                    'justsecurity_source': True
                }
            )

        except Exception as e:
            logger.error("Failed to create paper from Algolia hit: %s", e)
            return None

    def _determine_document_type(self, title: str, content: str) -> str:
        """
        Determine document type based on title and content
        """
        text_to_analyze = f"{title} {content}".lower()

        for doc_type, keywords in self.DOCUMENT_TYPES.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                return doc_type

        return 'document'  # Default type

    def _search_via_rss(
        self,
        query: str,
        max_results: int,
        document_type: Optional[str] = None
    ) -> List[Paper]:
        """
        Fallback search via RSS feed parsing
        """
        try:
            response = self._make_request(self.RSS_FEED)
            if not response:
                logger.error("Failed to fetch RSS feed")
                return []

            # Parse RSS feed
            papers = self._parse_rss_feed(response.text)

            # Filter by query terms
            query_lower = query.lower()
            filtered_papers = []

            for paper in papers:
                if (query_lower in paper.title.lower() or
                    query_lower in paper.abstract.lower()):
                    filtered_papers.append(paper)

            return filtered_papers[:max_results]

        except Exception as e:
            logger.error("RSS fallback search failed: %s", e)
            return []

    def _parse_rss_feed(self, rss_content: Optional[str] = None) -> List[Paper]:
        """
        Parse RSS feed to extract documents
        """
        try:
            if rss_content:
                feed = feedparser.parse(rss_content)
            else:
                feed = feedparser.parse(self.RSS_FEED)

            papers = []

            for entry in feed.entries:
                try:
                    # Extract basic information
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    summary = entry.get('summary', '')

                    if not title or not link:
                        continue

                    # Parse publication date
                    published_date = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'published'):
                        try:
                            published_date = datetime.strptime(
                                entry.published, '%a, %d %b %Y %H:%M:%S %z'
                            )
                        except ValueError:
                            pass

                    # Extract author
                    authors = []
                    if hasattr(entry, 'author'):
                        authors = [entry.author]

                    # Extract categories/tags
                    categories = []
                    if hasattr(entry, 'tags'):
                        categories = [tag.term for tag in entry.tags]

                    # Determine document type
                    doc_type = self._determine_document_type(title, summary)

                    # Extract document ID from URL
                    doc_id = link.split('/')[-2] if link.endswith('/') else link.split('/')[-1]

                    paper = Paper(
                        paper_id=doc_id,
                        title=title,
                        authors=authors,
                        abstract=summary,
                        doi='',
                        published_date=published_date,
                        pdf_url='',
                        url=link,
                        source='justsecurity',
                        categories=categories,
                        extra={
                            'document_type': doc_type,
                            'rss_source': True
                        }
                    )

                    papers.append(paper)

                except Exception as e:
                    logger.warning("Failed to parse RSS entry: %s", e)
                    continue

            return papers

        except Exception as e:
            logger.error("RSS feed parsing failed: %s", e)
            return []

    def _filter_by_date(self, papers: List[Paper], date_filter: str) -> List[Paper]:
        """
        Filter papers by date range
        """
        from datetime import timedelta

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

    def _get_wordpress_post_details(self, post_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed post information from WordPress API
        """
        try:
            url = f"{self.WORDPRESS_API}posts/{post_id}"
            params = {'_embed': '1'}  # Include embedded data (author, categories, etc.)

            response = self._make_request(url, params=params)
            if response and response.status_code == 200:
                return response.json()

        except Exception as e:
            logger.debug("Could not get WordPress post details for %s: %s", post_id, e)

        return None

    def _create_paper_from_wordpress_post(self, post: Dict[str, Any]) -> Optional[Paper]:
        """
        Create a Paper object from WordPress API response
        """
        try:
            post_id = str(post.get('id', ''))
            title = post.get('title', {}).get('rendered', '')
            content = post.get('content', {}).get('rendered', '')
            excerpt = post.get('excerpt', {}).get('rendered', '')

            if not post_id or not title:
                return None

            # Parse publication date
            published_date = datetime.now()
            date_str = post.get('date', '')
            if date_str:
                try:
                    published_date = datetime.fromisoformat(date_str)
                except ValueError:
                    pass

            # Extract authors from embedded data
            authors = []
            embedded = post.get('_embedded', {})
            if 'author' in embedded:
                for author in embedded['author']:
                    authors.append(author.get('name', ''))

            # Extract categories and tags from embedded data
            categories = []
            if 'wp:term' in embedded:
                for term_group in embedded['wp:term']:
                    for term in term_group:
                        categories.append(term.get('name', ''))

            # Get URL
            url = post.get('link', f"{self.BASE_URL}/{post_id}/")

            # Determine document type
            doc_type = self._determine_document_type(title, content)

            # Create abstract from excerpt or content
            abstract = excerpt or (content[:500] + "..." if len(content) > 500 else content)
            # Strip HTML tags from abstract
            soup = BeautifulSoup(abstract, 'html.parser')
            abstract = soup.get_text()

            return Paper(
                paper_id=post_id,
                title=title,
                authors=authors,
                abstract=abstract,
                doi='',
                published_date=published_date,
                pdf_url='',
                url=url,
                source='justsecurity',
                categories=categories,
                extra={
                    'document_type': doc_type,
                    'wordpress_post_id': post_id,
                    'wordpress_source': True
                }
            )

        except Exception as e:
            logger.error("Failed to create paper from WordPress post: %s", e)
            return None

    def download_document(self, document_id: str, save_path: str) -> str:
        """
        Download document as PDF (if available) or HTML
        """
        try:
            # First try to get detailed post information
            post_details = self._get_wordpress_post_details(document_id)

            if post_details:
                url = post_details.get('link', f"{self.BASE_URL}/{document_id}/")
            else:
                url = f"{self.BASE_URL}/{document_id}/"

            # Download the HTML content
            response = self._make_request(url)
            if not response or response.status_code != 200:
                status_msg = response.status_code if response else 'no response'
                raise RuntimeError(f"Could not download document from Just Security (HTTP {status_msg})")

            # Save as HTML file
            os.makedirs(save_path, exist_ok=True)
            filename = f"{document_id}.html"
            filepath = os.path.join(save_path, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response.text)

            logger.info("Downloaded Just Security document: %s", filepath)
            return filepath

        except Exception as e:
            logger.error("Failed to download Just Security document %s: %s", document_id, e)
            raise

    def read_document(self, document_id: str, save_path: str) -> str:
        """
        Extract text from Just Security document
        """
        try:
            filepath = os.path.join(save_path, f"{document_id}.html")

            # Download if not exists
            if not os.path.exists(filepath):
                self.download_document(document_id, save_path)

            # Read and parse HTML content
            with open(filepath, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Parse HTML to extract text
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            if not text.strip():
                return "Error: Could not extract text from document"

            return text

        except Exception as e:
            logger.error("Failed to read Just Security document %s: %s", document_id, e)
            return f"Error reading document: {str(e)}"

    def _build_algolia_search_url(self, query: str, max_results: int) -> str:
        """
        Build Algolia search URL
        """
        return f"https://{self.ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{self.ALGOLIA_INDEX}/query"

    def _build_wordpress_api_url(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Build WordPress API URL with parameters
        """
        url = f"{self.WORDPRESS_API}{endpoint}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url += f"?{query_string}"
        return url

# EOF
