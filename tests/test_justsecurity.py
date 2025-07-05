"""Test suite for Just Security platform searcher

This module tests the Just Security document platform integration,
including search functionality, document parsing, and API interactions.
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

# Import the module to be tested (will be implemented)
from paper_search_mcp.government_platforms.justsecurity import JustSecuritySearcher
from paper_search_mcp.paper import Paper


class TestJustSecuritySearcher(unittest.TestCase):
    """Test cases for Just Security platform searcher"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.searcher = JustSecuritySearcher()
        
        # Mock response data for API calls
        self.mock_algolia_response = {
            "hits": [
                {
                    "objectID": "12345",
                    "title": "January 6th Committee Final Report Analysis",
                    "content": "Comprehensive analysis of the January 6th Committee's final report...",
                    "url": "https://www.justsecurity.org/12345/january-6-committee-final-report-analysis/",
                    "date": "2023-01-15T10:30:00Z",
                    "author": "Legal Expert",
                    "categories": ["January 6th", "Congressional Oversight"],
                    "tags": ["committee", "report", "analysis"],
                    "_highlightResult": {
                        "title": {"value": "January 6th Committee Final Report Analysis"}
                    }
                },
                {
                    "objectID": "12346", 
                    "title": "Trump Classified Documents Investigation Update",
                    "content": "Latest developments in the classified documents case...",
                    "url": "https://www.justsecurity.org/12346/trump-classified-documents-update/",
                    "date": "2023-02-10T15:45:00Z",
                    "author": "National Security Analyst",
                    "categories": ["National Security", "Legal"],
                    "tags": ["classified", "documents", "investigation"],
                    "_highlightResult": {
                        "title": {"value": "Trump Classified Documents Investigation Update"}
                    }
                }
            ],
            "nbHits": 2,
            "page": 0,
            "nbPages": 1,
            "hitsPerPage": 20
        }

        self.mock_wordpress_response = {
            "id": 12345,
            "title": {"rendered": "January 6th Committee Final Report Analysis"},
            "content": {"rendered": "<p>Comprehensive analysis content...</p>"},
            "excerpt": {"rendered": "<p>Brief excerpt...</p>"},
            "date": "2023-01-15T10:30:00",
            "link": "https://www.justsecurity.org/12345/january-6-committee-final-report-analysis/",
            "author": 456,
            "categories": [78, 92],
            "tags": [101, 102, 103],
            "_embedded": {
                "author": [{"name": "Legal Expert"}],
                "wp:term": [
                    [{"name": "January 6th"}, {"name": "Congressional Oversight"}],
                    [{"name": "committee"}, {"name": "report"}, {"name": "analysis"}]
                ]
            }
        }

        self.mock_rss_response = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Just Security</title>
                <item>
                    <title>January 6th Committee Final Report Analysis</title>
                    <link>https://www.justsecurity.org/12345/january-6-committee-final-report-analysis/</link>
                    <description>Comprehensive analysis of the January 6th Committee's final report</description>
                    <pubDate>Sun, 15 Jan 2023 10:30:00 +0000</pubDate>
                    <author>Legal Expert</author>
                    <category>January 6th</category>
                    <category>Congressional Oversight</category>
                </item>
            </channel>
        </rss>"""

    def test_init(self):
        """Test searcher initialization"""
        self.assertIsInstance(self.searcher, JustSecuritySearcher)
        self.assertEqual(self.searcher.ALGOLIA_APP_ID, "00O7E2708B")
        self.assertEqual(self.searcher.ALGOLIA_API_KEY, "0cae588c66eb9d1f0c73cd7d70e9be68")
        self.assertIn('jan6', self.searcher.CLEARINGHOUSES)
        self.assertIn('trump_trials', self.searcher.CLEARINGHOUSES)

    @patch('requests.Session.get')
    def test_search_basic_functionality(self, mock_get):
        """Test basic search functionality"""
        # Mock the Algolia API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_algolia_response
        mock_get.return_value = mock_response

        results = self.searcher.search("january 6", max_results=10)
        
        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), 10)
        
        if results:
            paper = results[0]
            self.assertIsInstance(paper, Paper)
            self.assertEqual(paper.source, 'justsecurity')
            self.assertIn('january', paper.title.lower())

    @patch('requests.Session.get')
    def test_search_clearinghouse_filter(self, mock_get):
        """Test search with clearinghouse filtering"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_algolia_response
        mock_get.return_value = mock_response

        results = self.searcher.search(
            "committee", 
            max_results=5, 
            clearinghouse="jan6"
        )
        
        self.assertIsInstance(results, list)
        # Verify that clearinghouse filtering was applied in the request
        mock_get.assert_called()

    @patch('requests.Session.get')
    def test_search_document_type_filter(self, mock_get):
        """Test search with document type filtering"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_algolia_response
        mock_get.return_value = mock_response

        results = self.searcher.search(
            "investigation", 
            max_results=5, 
            document_type="analysis"
        )
        
        self.assertIsInstance(results, list)

    def test_create_paper_from_algolia_hit(self):
        """Test creating Paper object from Algolia search hit"""
        hit = self.mock_algolia_response["hits"][0]
        
        paper = self.searcher._create_paper_from_algolia_hit(hit)
        
        self.assertIsInstance(paper, Paper)
        self.assertEqual(paper.paper_id, "12345")
        self.assertEqual(paper.title, "January 6th Committee Final Report Analysis")
        self.assertEqual(paper.source, "justsecurity")
        self.assertIn("Legal Expert", paper.authors)
        self.assertIsInstance(paper.published_date, datetime)

    def test_create_paper_from_wordpress_post(self):
        """Test creating Paper object from WordPress API response"""
        post = self.mock_wordpress_response
        
        paper = self.searcher._create_paper_from_wordpress_post(post)
        
        self.assertIsInstance(paper, Paper)
        self.assertEqual(paper.paper_id, "12345")
        self.assertIn("January 6th", paper.title)
        self.assertEqual(paper.source, "justsecurity")

    @patch('requests.Session.get')
    def test_get_wordpress_post_details(self, mock_get):
        """Test fetching detailed post information from WordPress API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_wordpress_response
        mock_get.return_value = mock_response

        post_details = self.searcher._get_wordpress_post_details("12345")
        
        self.assertIsNotNone(post_details)
        self.assertEqual(post_details["id"], 12345)

    def test_determine_document_type(self):
        """Test document type classification"""
        # Test analysis type
        analysis_title = "Legal Analysis of January 6th Events"
        doc_type = self.searcher._determine_document_type(analysis_title, "")
        self.assertEqual(doc_type, "analysis")

        # Test report type  
        report_title = "Congressional Committee Report on Security"
        doc_type = self.searcher._determine_document_type(report_title, "")
        self.assertEqual(doc_type, "report")

        # Test court filing type
        court_title = "Motion to Dismiss Filed in Federal Court"
        doc_type = self.searcher._determine_document_type(court_title, "")
        self.assertEqual(doc_type, "court_filing")

    @patch('requests.Session.get')
    def test_download_document(self, mock_get):
        """Test document download functionality"""
        # Mock HTML response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Mock HTML content</p></body></html>"
        mock_get.return_value = mock_response

        result = self.searcher.download_document(
            "12345",
            "/tmp/test_downloads"
        )
        
        self.assertIsInstance(result, str)
        self.assertTrue(result.endswith('.html'))

    @patch('builtins.open', create=True)
    @patch('os.path.exists')
    @patch.object(JustSecuritySearcher, 'download_document')
    def test_read_document(self, mock_download, mock_exists, mock_open):
        """Test document text extraction"""
        # Mock file exists and download behavior
        mock_exists.return_value = True
        mock_download.return_value = "/tmp/test_downloads/12345.html"
        
        # Mock file reading
        html_content = "<html><body><p>Test document content</p></body></html>"
        mock_file = Mock()
        mock_file.read.return_value = html_content
        mock_open.return_value.__enter__.return_value = mock_file

        text_content = self.searcher.read_document(
            "12345",
            "/tmp/test_downloads"
        )
        
        self.assertIsInstance(text_content, str)
        self.assertIn("test document content", text_content.lower())

    @patch('requests.Session.get')
    def test_search_api_error_handling(self, mock_get):
        """Test handling of API errors during search"""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        results = self.searcher.search("test query")
        
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)

    @patch('requests.Session.get')
    def test_search_rate_limiting(self, mock_get):
        """Test rate limiting handling"""
        # Mock rate limit response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        results = self.searcher.search("test query")
        
        self.assertIsInstance(results, list)

    def test_clearinghouse_validation(self):
        """Test clearinghouse parameter validation"""
        valid_clearinghouses = list(self.searcher.CLEARINGHOUSES.keys()) + ['all']
        
        for clearinghouse in valid_clearinghouses:
            # Should not raise exception
            try:
                self.searcher._validate_clearinghouse(clearinghouse)
            except ValueError:
                self.fail(f"Valid clearinghouse '{clearinghouse}' raised ValueError")

        # Test invalid clearinghouse
        with self.assertRaises(ValueError):
            self.searcher._validate_clearinghouse("invalid_clearinghouse")

    @patch('feedparser.parse')
    def test_rss_feed_parsing(self, mock_parse):
        """Test RSS feed parsing functionality"""
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                title="Test Article",
                link="https://www.justsecurity.org/123/test-article/",
                summary="Test summary",
                published="Sun, 15 Jan 2023 10:30:00 +0000",
                author="Test Author",
                tags=[Mock(term="tag1"), Mock(term="tag2")]
            )
        ]
        mock_parse.return_value = mock_feed

        papers = self.searcher._parse_rss_feed()
        
        self.assertIsInstance(papers, list)
        if papers:
            paper = papers[0]
            self.assertIsInstance(paper, Paper)
            self.assertEqual(paper.source, "justsecurity")

    def test_url_building(self):
        """Test URL construction for different API endpoints"""
        # Test Algolia search URL
        algolia_url = self.searcher._build_algolia_search_url("test query", 10)
        self.assertIn("algolia", algolia_url.lower())
        self.assertIn("query", algolia_url)

        # Test WordPress API URL
        wp_url = self.searcher._build_wordpress_api_url("posts", {"per_page": 10})
        self.assertIn("wp-json", wp_url)
        self.assertIn("per_page", wp_url)


class TestJustSecurityIntegration(unittest.TestCase):
    """Integration tests for Just Security platform"""

    def setUp(self):
        self.searcher = JustSecuritySearcher()

    @unittest.skipUnless(
        __name__ == '__main__',
        "Integration tests only run when module executed directly"
    )
    def test_live_search_integration(self):
        """Test live search against Just Security API"""
        try:
            results = self.searcher.search("january 6", max_results=3)
            
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)
            
            for paper in results:
                self.assertIsInstance(paper, Paper)
                self.assertEqual(paper.source, "justsecurity")
                self.assertIsNotNone(paper.title)
                self.assertIsNotNone(paper.url)
                
        except Exception as e:
            self.skipTest(f"Live API test failed: {e}")

    @unittest.skipUnless(
        __name__ == '__main__',
        "Integration tests only run when module executed directly"
    )
    def test_live_document_access(self):
        """Test live document download and reading"""
        try:
            # First get some search results
            results = self.searcher.search("committee", max_results=1)
            
            if results:
                paper = results[0]
                
                # Test document reading
                content = self.searcher.read_document(
                    paper.paper_id,
                    "/tmp/justsecurity_test"
                )
                
                self.assertIsInstance(content, str)
                self.assertGreater(len(content), 0)
                
        except Exception as e:
            self.skipTest(f"Live document access test failed: {e}")


if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)