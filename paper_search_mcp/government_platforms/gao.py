"""MCP Government Accountability Office document handler"""

# Standard imports
import logging
import os
import random
import re
import time
from typing import List, Optional, Dict, Union, Any
from datetime import datetime, timedelta

# External imports
import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from PyPDF2 import PdfReader
import feedparser

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


class GAOSearcher(DocumentSource):
    """Searcher for Government Accountability Office reports and publications"""

    BASE_URL = "https://www.gao.gov"
    SEARCH_URL = "https://www.gao.gov/reports-testimonies"

    # RSS feed URLs for different types of content
    RSS_FEEDS = {
        'reports': f'{BASE_URL}/rss/reports.xml',
        'reports_brief': f'{BASE_URL}/rss/reports_450.xml',
        'legal': f'{BASE_URL}/rss/reportslegal.xml',
        'major_rules': f'{BASE_URL}/rss/reports_majrule.xml',
        'press': f'{BASE_URL}/rss/press.xml'
    }

    # User agents for rotation to appear more natural
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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
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
    ) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and rate limiting"""

        for attempt in range(self.max_retries):
            try:
                # Rate limiting: wait 1-3 seconds between requests
                time.sleep(random.uniform(1.0, 3.0))

                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=self.timeout)
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
        date_filter: Optional[str] = None,
        topics: Optional[List[str]] = None,
        agencies: Optional[List[str]] = None,
        feed_type: str = 'reports',
        **kwargs: Any
    ) -> List[Paper]:
        """
        Search GAO reports and publications using RSS feeds

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            date_filter: Date filter ('week', 'month', '6months', 'year', or custom range)
            topics: List of topic filters (e.g., ['Agriculture', 'Healthcare'])
            agencies: List of agency filters (e.g., ['Department of Defense'])
            feed_type: Type of RSS feed to use ('reports', 'reports_brief', 'legal',
                      'major_rules', 'press')

        Returns:
            List of Paper objects representing GAO reports
        """
        try:
            # First try RSS feed approach (more reliable)
            papers = self._search_via_rss(query, max_results, feed_type)

            if papers:
                # Apply additional filters if specified
                if date_filter or topics or agencies:
                    papers = self._apply_filters(papers, date_filter, topics, agencies)

                return papers[:max_results]

            # Fallback to web scraping if RSS fails
            logger.info("RSS search returned no results, trying web scraping as fallback")
            return self._search_via_web_scraping(query, max_results, date_filter, topics, agencies)

        except Exception as e:
            logger.error("Search failed: %s", e)
            return []

    def _search_via_rss(self, query: str, max_results: int, feed_type: str = 'reports') -> List[Paper]:
        """Search GAO reports via RSS feeds"""
        papers = []

        # Get the RSS feed URL
        feed_url = self.RSS_FEEDS.get(feed_type, self.RSS_FEEDS['reports'])

        try:
            logger.info("Fetching GAO RSS feed: %s", feed_url)
            # Parse the RSS feed
            feed = feedparser.parse(feed_url)

            if feed.bozo:
                logger.warning("RSS feed parsing had errors: %s", feed.bozo_exception)

            query_lower = query.lower()

            for entry in feed.entries:
                # Check if query matches title or summary
                title = entry.get('title', '') or ''
                summary = entry.get('summary', '') or ''

                if (query_lower in title.lower() or
                    query_lower in summary.lower()):

                    paper = self._create_paper_from_rss_entry(entry)
                    if paper:
                        papers.append(paper)

                        if len(papers) >= max_results:
                            break

            logger.info("Found %d matching GAO reports via RSS", len(papers))
            return papers

        except Exception as e:
            logger.error("RSS search failed: %s", e)
            return []

    def _create_paper_from_rss_entry(self, entry) -> Optional[Paper]:
        """Create a Paper object from an RSS feed entry"""
        try:
            title = entry.get('title', '')
            link = entry.get('link', '')
            summary = entry.get('summary', '')

            # Extract publication date
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_date = datetime(*entry.updated_parsed[:6])
            else:
                published_date = datetime.now()

            # Extract GAO report ID
            paper_id = self._extract_report_id(link, title)

            # Build PDF URL
            pdf_url = self._build_pdf_url(paper_id, link)

            # Determine report type
            report_type = self._determine_report_type(title, link)

            return Paper(
                paper_id=paper_id,
                title=title,
                authors=['U.S. Government Accountability Office'],
                abstract=summary,
                doi='',  # GAO reports don't have DOIs
                published_date=published_date,
                pdf_url=pdf_url,
                url=link,
                source='gao',
                categories=[],  # Will be populated by filtering if needed
                extra={
                    'report_type': report_type,
                    'gao_number': paper_id,
                    'rss_source': True
                }
            )

        except Exception as e:
            logger.error("Failed to create paper from RSS entry: %s", e)
            return None

    def _apply_filters(self, papers: List[Paper], date_filter: Optional[str] = None,
                      topics: Optional[List[str]] = None, agencies: Optional[List[str]] = None) -> List[Paper]:
        """Apply additional filters to paper results"""
        filtered_papers = papers

        # Apply date filter
        if date_filter:
            filtered_papers = self._filter_by_date(filtered_papers, date_filter)

        # Apply topic filters
        if topics:
            filtered_papers = self._filter_by_topics(filtered_papers, topics)

        # Apply agency filters
        if agencies:
            filtered_papers = self._filter_by_agencies(filtered_papers, agencies)

        return filtered_papers

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

    def _filter_by_topics(self, papers: List[Paper], topics: List[str]) -> List[Paper]:
        """Filter papers by topic keywords in title/abstract"""
        topic_keywords = [topic.lower() for topic in topics]
        filtered = []

        for paper in papers:
            text_to_search = f"{paper.title} {paper.abstract}".lower()
            if any(keyword in text_to_search for keyword in topic_keywords):
                # Add matching topics to categories
                matching_topics = [topic for topic in topics
                                 if topic.lower() in text_to_search]
                paper.categories.extend(matching_topics)
                filtered.append(paper)

        return filtered

    def _filter_by_agencies(self, papers: List[Paper], agencies: List[str]) -> List[Paper]:
        """Filter papers by agency keywords in title/abstract"""
        agency_keywords = [agency.lower() for agency in agencies]
        filtered = []

        for paper in papers:
            text_to_search = f"{paper.title} {paper.abstract}".lower()
            if any(keyword in text_to_search for keyword in agency_keywords):
                # Add matching agencies to extra metadata
                matching_agencies = [agency for agency in agencies
                                   if agency.lower() in text_to_search]
                if paper.extra is None:
                    paper.extra = {}
                if 'agency_names' not in paper.extra:
                    paper.extra['agency_names'] = []
                paper.extra['agency_names'].extend(matching_agencies)
                filtered.append(paper)

        return filtered

    def _search_via_web_scraping(self, query: str, max_results: int,
                                date_filter: Optional[str] = None, topics: Optional[List[str]] = None,
                                agencies: Optional[List[str]] = None) -> List[Paper]:
        """Fallback web scraping search method"""
        papers = []
        page = 0

        while len(papers) < max_results:
            # Build search parameters
            params = {
                'search': query,
                'page': page
            }

            # Add filters if specified
            if date_filter:
                params['f[0]'] = f'field_date_published:{date_filter}'

            filter_index = 1 if date_filter else 0

            if topics:
                for topic in topics:
                    params[f'f[{filter_index}]'] = f'field_topic_area:{topic}'
                    filter_index += 1

            if agencies:
                for agency in agencies:
                    params[f'f[{filter_index}]'] = f'field_agency:{agency}'
                    filter_index += 1

            response = self._make_request(self.SEARCH_URL, params)
            if not response:
                logger.error("Failed to fetch search results")
                break

            soup = BeautifulSoup(response.content, 'html.parser')

            # Parse search results
            results = self._parse_search_results(soup)
            if not results:
                break  # No more results

            papers.extend(results)
            page += 1

            # Avoid infinite loops
            if page > 10:  # Reasonable limit
                break

        return papers[:max_results]

    def _parse_search_results(self, soup: BeautifulSoup) -> List[Paper]:
        """Parse search results from GAO search page"""
        papers = []

        # Look for result items (this selector may need adjustment based on actual HTML structure)
        result_items = (soup.find_all('div', class_=['views-row', 'search-result-item']) or
                       soup.find_all('article') or
                       soup.find_all('div', class_='node'))

        for item in result_items:
            try:
                paper = self._extract_paper_from_result(item)
                if paper:
                    papers.append(paper)
            except Exception as e:
                logger.warning("Failed to parse result item: %s", e)
                continue

        return papers

    def _extract_paper_from_result(self, item: Union[Tag, BeautifulSoup]) -> Optional[Paper]:
        """Extract paper information from a search result item"""
        try:
            # Extract title (adjust selectors based on actual HTML)
            title_elem = (item.find('h3') or item.find('h2') or
                         item.find('a', class_='title'))
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)

            # Extract URL
            link_elem = (title_elem.find('a') if title_elem and title_elem.name != 'a'
                        else title_elem)
            if not link_elem:
                return None

            url_attr = link_elem.get('href', '')
            url = str(url_attr) if url_attr else ''
            if url.startswith('/'):
                url = self.BASE_URL + url

            # Extract GAO report ID from URL or title
            paper_id = self._extract_report_id(url, title)

            # Extract publication date
            date_elem = (item.find('time') or item.find('span', class_='date') or
                        item.find('div', class_='date'))
            published_date = self._parse_date(
                date_elem.get_text(strip=True) if date_elem else '')

            # Extract abstract/summary
            summary_elem = (item.find('div', class_='summary') or
                           item.find('p') or
                           item.find('div', class_='field-content'))
            abstract = summary_elem.get_text(strip=True) if summary_elem else ''

            # Extract categories/topics
            categories = self._extract_categories(item)

            # Build PDF URL (GAO reports typically have direct PDF links)
            pdf_url = self._build_pdf_url(paper_id, url)

            return Paper(
                paper_id=paper_id,
                title=title,
                authors=['U.S. Government Accountability Office'],
                abstract=abstract,
                doi='',  # GAO reports don't typically have DOIs
                published_date=published_date,
                pdf_url=pdf_url,
                url=url,
                source='gao',
                categories=categories,
                extra={
                    'report_type': self._determine_report_type(title, url),
                    'gao_number': paper_id
                }
            )

        except Exception as e:
            logger.error("Error extracting paper data: %s", e)
            return None

    def _extract_report_id(
        self,
        url: str,
        title: str,
    ) -> str:
        """Extract GAO report ID from URL or title"""

        # Look for GAO report number in URL

        # Pattern: GAO-YY-NNNNNN
        gao_pattern = r'GAO-\d{2}-\d{6}'

        # First try URL
        match = re.search(gao_pattern, url)
        if match:
            return match.group()

        # Then try title
        match = re.search(gao_pattern, title)
        if match:
            return match.group()

        # Fallback: use URL path as ID
        if '/products/' in url:
            return url.split('/products/')[-1].split('?')[0]

        # Final fallback: generate from URL
        return url.split('/')[-1][:20]

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string into datetime object"""

        if not date_str:
            return datetime.now()

        # Common GAO date formats
        date_formats = [
            '%B %d, %Y',      # January 15, 2024
            '%b %d, %Y',      # Jan 15, 2024
            '%m/%d/%Y',       # 01/15/2024
            '%Y-%m-%d',       # 2024-01-15
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        # If all parsing fails, return current date
        logger.warning("Could not parse date: %s", date_str)
        return datetime.now()

    def _extract_categories(self, item: BeautifulSoup) -> List[str]:
        """Extract topic categories from result item"""

        categories = []

        # Look for topic/category elements
        topic_elems = (item.find_all('span', class_='topic') or
                      item.find_all('div', class_='field-topic') or
                      item.find_all('a', class_='taxonomy-term'))

        for elem in topic_elems:
            category = elem.get_text(strip=True)
            if category and category not in categories:
                categories.append(category)

        return categories

    def _determine_report_type(
        self,
        title: str,
        url: str,
    ) -> str:
        """Determine the type of GAO document"""

        title_lower = title.lower()
        url_lower = url.lower()

        if 'testimony' in title_lower or 'testimony' in url_lower:
            return 'testimony'
        elif 'correspondence' in title_lower or 'correspondence' in url_lower:
            return 'correspondence'
        elif 'report' in title_lower or 'products' in url_lower:
            return 'report'
        else:
            return 'publication'

    def _build_pdf_url(
        self,
        paper_id: str,
        page_url: str,
    ) -> str:
        """Build PDF download URL for GAO report"""

        # GAO typically provides PDF links, but pattern may vary
        # This is a best guess - may need adjustment based on actual structure
        if 'GAO-' in paper_id:
            return f"{self.BASE_URL}/assets/{paper_id.lower()}.pdf"
        else:
            # Alternative: try to find PDF link on the report page
            return page_url  # Fallback to page URL

    def download_pdf(
        self,
        document_id: str,
        save_path: str,
    ) -> str:
        """Download GAO report PDF"""

        try:
            # First, try direct PDF URL
            pdf_url = self._build_pdf_url(document_id, '')

            response = self._make_request(pdf_url)
            content_type = response.headers.get('content-type', '').lower() if response else ''
            if not response or content_type != 'application/pdf':
                # If direct PDF fails, try to find PDF link on report page
                report_url = f"{self.BASE_URL}/products/{document_id}"
                response = self._make_request(report_url)

                if response:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    pdf_link = soup.find('a',
                                         href=lambda x: x and str(x).endswith('.pdf'))

                    if pdf_link:
                        pdf_url_attr = pdf_link.get('href', '')
                        pdf_url = str(pdf_url_attr) if pdf_url_attr else ''
                        if pdf_url.startswith('/'):
                            pdf_url = self.BASE_URL + pdf_url

                        response = self._make_request(pdf_url)

            if not response:
                raise Exception("Could not download PDF")

            # Save PDF file
            os.makedirs(save_path, exist_ok=True)
            filename = f"{document_id}.pdf"
            filepath = os.path.join(save_path, filename)

            with open(filepath, 'wb') as f:
                f.write(response.content)

            logger.info("Downloaded GAO report: %s", filepath)
            return filepath

        except Exception as e:
            logger.error("Failed to download GAO report %s: %s", document_id, e)
            raise

    def read_document(
        self,
        document_id: str,
        save_path: str,
    ) -> str:
        """Extract text from GAO report PDF"""

        try:
            filepath = os.path.join(save_path, f"{document_id}.pdf")

            # Download if not exists
            if not os.path.exists(filepath):
                self.download_pdf(document_id, save_path)

            # Extract text using PyPDF2
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
            logger.error("Failed to read GAO document %s: %s", document_id, e)
            return f"Error reading document: {str(e)}"

# EOF
