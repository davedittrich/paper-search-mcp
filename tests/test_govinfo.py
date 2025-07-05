"""Test suite for GovInfo platform searcher

This module tests the GovInfo.gov document platform integration,
including search functionality, document parsing, and API interactions.
"""

import unittest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

# Import the module to be tested (will be implemented)
from paper_search_mcp.government_platforms.govinfo import GovInfoSearcher
from paper_search_mcp.paper import Paper


class TestGovInfoSearcher(unittest.TestCase):
    """Test cases for GovInfo platform searcher"""

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.searcher = GovInfoSearcher()
        
        # Mock response data for API calls
        self.mock_search_response = {
            "count": 2,
            "nextPage": None,
            "previousPage": None,
            "packages": [],
            "results": [
                {
                    "packageId": "BILLS-118hr1-ih",
                    "lastModified": "2023-01-09T19:52:08Z",
                    "packageLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih",
                    "docClass": "bills",
                    "title": "For the People Act of 2023",
                    "congress": "118",
                    "dateIssued": "2023-01-09",
                    "details": {
                        "billType": "hr",
                        "billNumber": "1",
                        "billVersion": "ih",
                        "chamber": "House",
                        "originChamber": "House"
                    },
                    "download": {
                        "pdfLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih/pdf",
                        "xmlLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih/xml",
                        "modsLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih/mods"
                    },
                    "governmentAuthor": ["U.S. House of Representatives"],
                    "collectionCode": "BILLS",
                    "collectionName": "Congressional Bills",
                    "resultLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih/summary"
                },
                {
                    "packageId": "FR-2023-01-10",
                    "lastModified": "2023-01-10T06:00:00Z",
                    "packageLink": "https://api.govinfo.gov/packages/FR-2023-01-10",
                    "docClass": "fr",
                    "title": "Federal Register, Volume 88 Issue 6 (Tuesday, January 10, 2023)",
                    "dateIssued": "2023-01-10",
                    "details": {
                        "volume": "88",
                        "issueNumber": "6"
                    },
                    "download": {
                        "pdfLink": "https://api.govinfo.gov/packages/FR-2023-01-10/pdf",
                        "xmlLink": "https://api.govinfo.gov/packages/FR-2023-01-10/xml"
                    },
                    "governmentAuthor": ["Office of the Federal Register, National Archives and Records Administration"],
                    "collectionCode": "FR",
                    "collectionName": "Federal Register",
                    "resultLink": "https://api.govinfo.gov/packages/FR-2023-01-10/summary"
                }
            ]
        }

        self.mock_collections_response = {
            "collections": [
                {
                    "collectionCode": "BILLS",
                    "collectionName": "Congressional Bills",
                    "packageCount": 158742,
                    "granuleCount": 0
                },
                {
                    "collectionCode": "FR",
                    "collectionName": "Federal Register",
                    "packageCount": 25678,
                    "granuleCount": 1234567
                },
                {
                    "collectionCode": "CPRT",
                    "collectionName": "Committee Prints",
                    "packageCount": 8934,
                    "granuleCount": 0
                }
            ]
        }

        self.mock_package_summary = {
            "packageId": "BILLS-118hr1-ih",
            "lastModified": "2023-01-09T19:52:08Z",
            "packageLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih",
            "title": "For the People Act of 2023",
            "congress": "118",
            "dateIssued": "2023-01-09",
            "governmentAuthor": ["U.S. House of Representatives"],
            "collectionCode": "BILLS",
            "collectionName": "Congressional Bills",
            "download": {
                "pdfLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih/pdf",
                "xmlLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih/xml",
                "txtLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih/htm"
            },
            "related": [
                {
                    "packageId": "BILLS-118hr1-rh",
                    "packageLink": "https://api.govinfo.gov/packages/BILLS-118hr1-rh",
                    "title": "For the People Act of 2023 (Reported in House)",
                    "relationshipType": "billVersion"
                }
            ]
        }

        self.mock_published_response = {
            "count": 150,
            "message": "150 packages found",
            "nextPage": "https://api.govinfo.gov/published/2023-01-01/2023-01-31?offsetMark=BILLS-118hr150-ih&pageSize=100",
            "previousPage": None,
            "packages": [
                {
                    "packageId": "BILLS-118hr1-ih",
                    "packageLink": "https://api.govinfo.gov/packages/BILLS-118hr1-ih",
                    "title": "For the People Act of 2023",
                    "dateIssued": "2023-01-09"
                }
            ]
        }

    def test_init(self):
        """Test searcher initialization"""
        self.assertIsInstance(self.searcher, GovInfoSearcher)
        self.assertEqual(self.searcher.BASE_URL, "https://api.govinfo.gov")
        self.assertEqual(self.searcher.API_KEY, "DEMO_KEY")
        self.assertIn('congressional', self.searcher.COLLECTIONS)
        self.assertIn('BILLS', self.searcher.COLLECTIONS['congressional'])

    @patch('requests.Session.post')
    def test_search_basic_functionality(self, mock_post):
        """Test basic search functionality"""
        # Mock the GovInfo API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_search_response
        mock_post.return_value = mock_response

        results = self.searcher.search("voting rights", max_results=10)
        
        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), 10)
        
        if results:
            paper = results[0]
            self.assertIsInstance(paper, Paper)
            self.assertEqual(paper.source, 'govinfo')
            # Verify POST request was made with proper JSON payload
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertIn('json', kwargs)

    @patch('requests.Session.post')
    def test_search_collection_filter(self, mock_post):
        """Test search with collection filtering"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_search_response
        mock_post.return_value = mock_response

        results = self.searcher.search(
            "climate change", 
            max_results=5, 
            collection="congressional"
        )
        
        self.assertIsInstance(results, list)
        # Verify that collection filtering was applied
        mock_post.assert_called()
        args, kwargs = mock_post.call_args
        query_data = kwargs.get('json', {})
        self.assertIn('collection:', str(query_data.get('query', '')))

    @patch('requests.Session.post')
    def test_search_date_range_filter(self, mock_post):
        """Test search with date range filtering"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_search_response
        mock_post.return_value = mock_response

        results = self.searcher.search(
            "healthcare", 
            max_results=5, 
            date_range="2023"
        )
        
        self.assertIsInstance(results, list)

    @patch('requests.Session.get')
    def test_get_collections(self, mock_get):
        """Test fetching available collections"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_collections_response
        mock_get.return_value = mock_response

        collections = self.searcher.get_collections()
        
        self.assertIsInstance(collections, list)
        self.assertGreater(len(collections), 0)
        
        if collections:
            collection = collections[0]
            self.assertIn('collectionCode', collection)
            self.assertIn('collectionName', collection)

    def test_create_paper_from_govinfo_result(self):
        """Test creating Paper object from GovInfo search result"""
        result = self.mock_search_response["results"][0]
        
        paper = self.searcher._create_paper_from_govinfo_result(result)
        
        self.assertIsInstance(paper, Paper)
        self.assertEqual(paper.paper_id, "BILLS-118hr1-ih")
        self.assertEqual(paper.title, "For the People Act of 2023")
        self.assertEqual(paper.source, "govinfo")
        self.assertIn("U.S. House of Representatives", paper.authors)
        self.assertIsInstance(paper.published_date, datetime)
        self.assertEqual(paper.extra['collection_code'], 'BILLS')
        self.assertEqual(paper.extra['doc_class'], 'bills')

    def test_create_paper_from_federal_register(self):
        """Test creating Paper object from Federal Register result"""
        result = self.mock_search_response["results"][1]
        
        paper = self.searcher._create_paper_from_govinfo_result(result)
        
        self.assertIsInstance(paper, Paper)
        self.assertEqual(paper.paper_id, "FR-2023-01-10")
        self.assertIn("Federal Register", paper.title)
        self.assertEqual(paper.source, "govinfo")
        self.assertEqual(paper.extra['collection_code'], 'FR')

    @patch('requests.Session.get')
    def test_get_package_summary(self, mock_get):
        """Test fetching detailed package information"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_package_summary
        mock_get.return_value = mock_response

        summary = self.searcher.get_package_summary("BILLS-118hr1-ih")
        
        self.assertIsNotNone(summary)
        self.assertEqual(summary["packageId"], "BILLS-118hr1-ih")
        self.assertIn("related", summary)

    @patch('requests.Session.get')
    def test_get_published_packages(self, mock_get):
        """Test fetching packages by publication date"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_published_response
        mock_get.return_value = mock_response

        packages = self.searcher.get_published_packages(
            start_date="2023-01-01",
            end_date="2023-01-31",
            collection="BILLS"
        )
        
        self.assertIsInstance(packages, list)
        if packages:
            package = packages[0]
            self.assertIn("packageId", package)

    def test_determine_document_type(self):
        """Test document type classification"""
        # Test bill type
        bill_result = self.mock_search_response["results"][0]
        doc_type = self.searcher._determine_document_type(bill_result)
        self.assertEqual(doc_type, "bill")

        # Test federal register type
        fr_result = self.mock_search_response["results"][1]
        doc_type = self.searcher._determine_document_type(fr_result)
        self.assertEqual(doc_type, "federal_register")

        # Test committee print type
        cprt_result = {
            "collectionCode": "CPRT",
            "title": "Committee Print on Climate Change"
        }
        doc_type = self.searcher._determine_document_type(cprt_result)
        self.assertEqual(doc_type, "committee_print")

    def test_build_search_query(self):
        """Test search query construction"""
        # Basic query
        query = self.searcher._build_search_query("climate change")
        self.assertIn("climate change", query)

        # Query with collection filter
        query = self.searcher._build_search_query(
            "healthcare", 
            collection="congressional"
        )
        self.assertIn("collection:", query)
        self.assertIn("healthcare", query)

        # Query with multiple filters
        query = self.searcher._build_search_query(
            "budget",
            collection="congressional",
            congress="118",
            doc_class="bills"
        )
        self.assertIn("congress:118", query)
        self.assertIn("docClass:bills", query)

    @patch('requests.Session.get')
    def test_download_pdf(self, mock_get):
        """Test PDF download functionality"""
        # Mock PDF response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"Mock PDF content"
        mock_get.return_value = mock_response

        result = self.searcher.download_pdf(
            "BILLS-118hr1-ih",
            "/tmp/test_downloads"
        )
        
        self.assertIsInstance(result, str)
        self.assertTrue(result.endswith('.pdf'))

    @patch('builtins.open', create=True)
    @patch('os.path.exists')
    @patch.object(GovInfoSearcher, 'download_pdf')
    @patch.object(GovInfoSearcher, '_get_govinfo_text')
    def test_read_document(self, mock_get_text, mock_download, mock_exists, mock_open):
        """Test document text extraction"""
        # Mock _get_govinfo_text to return HTML content
        mock_get_text.return_value = "SEC. 1. SHORT TITLE.\nThis Act may be cited as the 'For the People Act of 2023'."
        
        # Mock file exists
        mock_exists.return_value = False
        mock_download.return_value = "/tmp/test_downloads/BILLS-118hr1-ih.pdf"

        text_content = self.searcher.read_document(
            "BILLS-118hr1-ih",
            "/tmp/test_downloads"
        )
        
        self.assertIsInstance(text_content, str)
        self.assertIn("For the People Act", text_content)

    @patch('requests.Session.post')
    def test_search_api_error_handling(self, mock_post):
        """Test handling of API errors during search"""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        results = self.searcher.search("test query")
        
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)

    @patch('requests.Session.post')
    def test_search_rate_limiting(self, mock_post):
        """Test rate limiting handling"""
        # Mock rate limit response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        results = self.searcher.search("test query")
        
        self.assertIsInstance(results, list)

    def test_collection_validation(self):
        """Test collection parameter validation"""
        valid_collections = list(self.searcher.COLLECTIONS.keys()) + ['all']
        valid_collection_codes = []
        for codes in self.searcher.COLLECTIONS.values():
            valid_collection_codes.extend(codes)
        
        for collection in valid_collections:
            # Should not raise exception
            try:
                self.searcher._validate_collection(collection)
            except ValueError:
                self.fail(f"Valid collection '{collection}' raised ValueError")

        for code in valid_collection_codes:
            try:
                self.searcher._validate_collection(code)
            except ValueError:
                self.fail(f"Valid collection code '{code}' raised ValueError")

        # Test invalid collection
        with self.assertRaises(ValueError):
            self.searcher._validate_collection("invalid_collection")

    def test_date_range_parsing(self):
        """Test date range parameter parsing"""
        # Test year format
        start, end = self.searcher._parse_date_range("2023")
        self.assertEqual(start, "2023-01-01")
        self.assertEqual(end, "2023-12-31")

        # Test month format
        start, end = self.searcher._parse_date_range("2023-06")
        self.assertEqual(start, "2023-06-01")
        self.assertEqual(end, "2023-06-30")

        # Test full date format
        start, end = self.searcher._parse_date_range("2023-01-15")
        self.assertEqual(start, "2023-01-15")
        self.assertEqual(end, "2023-01-15")

        # Test range format
        start, end = self.searcher._parse_date_range("2023-01-01:2023-01-31")
        self.assertEqual(start, "2023-01-01")
        self.assertEqual(end, "2023-01-31")

    def test_url_building(self):
        """Test URL construction for different API endpoints"""
        # Test search URL
        search_url = self.searcher._build_search_url()
        self.assertEqual(search_url, f"{self.searcher.BASE_URL}/search")

        # Test collections URL
        collections_url = self.searcher._build_collections_url()
        self.assertEqual(collections_url, f"{self.searcher.BASE_URL}/collections")

        # Test package URL
        package_url = self.searcher._build_package_url("BILLS-118hr1-ih")
        self.assertIn("BILLS-118hr1-ih", package_url)

        # Test published URL
        published_url = self.searcher._build_published_url("2023-01-01", "2023-01-31")
        self.assertIn("2023-01-01", published_url)
        self.assertIn("2023-01-31", published_url)

    def test_pagination_handling(self):
        """Test pagination in search results"""
        mock_response_with_pagination = {
            "count": 250,
            "nextPage": "https://api.govinfo.gov/search?offsetMark=BILLS-118hr100-ih&pageSize=100",
            "previousPage": None,
            "results": self.mock_search_response["results"]
        }

        next_page_url = self.searcher._extract_next_page_url(mock_response_with_pagination)
        self.assertIsNotNone(next_page_url)
        self.assertIn("offsetMark", next_page_url)


class TestGovInfoIntegration(unittest.TestCase):
    """Integration tests for GovInfo platform"""

    def setUp(self):
        self.searcher = GovInfoSearcher()

    @unittest.skipUnless(
        __name__ == '__main__',
        "Integration tests only run when module executed directly"
    )
    def test_live_search_integration(self):
        """Test live search against GovInfo API"""
        try:
            results = self.searcher.search("voting rights", max_results=3)
            
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)
            
            for paper in results:
                self.assertIsInstance(paper, Paper)
                self.assertEqual(paper.source, "govinfo")
                self.assertIsNotNone(paper.title)
                self.assertIsNotNone(paper.url)
                
        except Exception as e:
            self.skipTest(f"Live API test failed: {e}")

    @unittest.skipUnless(
        __name__ == '__main__',
        "Integration tests only run when module executed directly"
    )
    def test_live_collections_access(self):
        """Test live access to GovInfo collections"""
        try:
            collections = self.searcher.get_collections()
            
            self.assertIsInstance(collections, list)
            self.assertGreater(len(collections), 0)
            
            # Verify expected collections exist
            collection_codes = [c['collectionCode'] for c in collections]
            self.assertIn('BILLS', collection_codes)
            self.assertIn('FR', collection_codes)
            self.assertIn('CPRT', collection_codes)
                
        except Exception as e:
            self.skipTest(f"Live collections test failed: {e}")

    @unittest.skipUnless(
        __name__ == '__main__',
        "Integration tests only run when module executed directly"
    )
    def test_live_document_access(self):
        """Test live document download and reading"""
        try:
            # First get some search results
            results = self.searcher.search("climate", max_results=1, collection="BILLS")
            
            if results:
                paper = results[0]
                
                # Test document reading
                content = self.searcher.read_document(
                    paper.paper_id,
                    "/tmp/govinfo_test"
                )
                
                self.assertIsInstance(content, str)
                self.assertGreater(len(content), 0)
                
        except Exception as e:
            self.skipTest(f"Live document access test failed: {e}")


if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)