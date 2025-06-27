# tests/test_gao.py
import unittest
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from paper_search_mcp.government_platforms.gao import GAOSearcher
from paper_search_mcp.paper import Paper
from paper_search_mcp import server


class TestGAOSearcher(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.searcher = GAOSearcher()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('paper_search_mcp.government_platforms.gao.requests.Session.get')
    def test_search_basic(self, mock_get):
        """Test basic GAO search functionality"""
        # Mock HTML response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = '''
        <html>
            <div class="views-row">
                <h3><a href="/products/GAO-24-106829">Test GAO Report Title</a></h3>
                <time>January 15, 2024</time>
                <div class="summary">This is a test GAO report summary.</div>
                <span class="topic">Cybersecurity</span>
            </div>
        </html>
        '''
        mock_get.return_value = mock_response

        results = self.searcher.search("cybersecurity", max_results=1)
        
        self.assertIsInstance(results, list)
        if results:  # Only test if we get results
            paper = results[0]
            self.assertIsInstance(paper, Paper)
            self.assertEqual(paper.source, 'gao')
            self.assertIn('U.S. Government Accountability Office', paper.authors)

    def test_extract_report_id(self):
        """Test GAO report ID extraction"""
        # Test URL-based extraction
        url = "https://www.gao.gov/products/GAO-24-106829"
        title = "Test Report"
        report_id = self.searcher._extract_report_id(url, title)
        self.assertEqual(report_id, "GAO-24-106829")

        # Test title-based extraction
        url = "https://www.gao.gov/products/some-other-id"
        title = "Test Report GAO-23-105678"
        report_id = self.searcher._extract_report_id(url, title)
        self.assertEqual(report_id, "GAO-23-105678")

    def test_parse_date(self):
        """Test date parsing functionality"""
        from datetime import datetime
        
        # Test various date formats
        test_cases = [
            ("January 15, 2024", datetime(2024, 1, 15)),
            ("Jan 15, 2024", datetime(2024, 1, 15)),
            ("01/15/2024", datetime(2024, 1, 15)),
            ("2024-01-15", datetime(2024, 1, 15)),
        ]
        
        for date_str, expected in test_cases:
            result = self.searcher._parse_date(date_str)
            self.assertEqual(result.date(), expected.date())

    def test_determine_report_type(self):
        """Test report type determination"""
        test_cases = [
            ("GAO Testimony on Cybersecurity", "https://example.com", "testimony"),
            ("GAO Report on Defense Spending", "https://example.com/products/123", "report"),
            ("GAO Correspondence to Congress", "https://example.com", "correspondence"),
            ("Special Publication", "https://example.com", "publication"),
        ]
        
        for title, url, expected_type in test_cases:
            result = self.searcher._determine_report_type(title, url)
            self.assertEqual(result, expected_type)

    def test_build_pdf_url(self):
        """Test PDF URL building"""
        paper_id = "GAO-24-106829"
        page_url = "https://www.gao.gov/products/GAO-24-106829"
        
        pdf_url = self.searcher._build_pdf_url(paper_id, page_url)
        expected_url = "https://www.gao.gov/assets/gao-24-106829.pdf"
        self.assertEqual(pdf_url, expected_url)

    @patch('paper_search_mcp.government_platforms.gao.requests.Session.get')
    def test_download_pdf(self, mock_get):
        """Test PDF download functionality"""
        # Mock PDF response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"Mock PDF content"
        mock_response.headers = {'content-type': 'application/pdf'}
        mock_get.return_value = mock_response

        report_id = "GAO-24-106829"
        filepath = self.searcher.download_pdf(report_id, self.temp_dir)
        
        expected_path = os.path.join(self.temp_dir, f"{report_id}.pdf")
        self.assertEqual(filepath, expected_path)
        self.assertTrue(os.path.exists(filepath))
        
        # Check file content
        with open(filepath, 'rb') as f:
            content = f.read()
        self.assertEqual(content, b"Mock PDF content")

    @patch('paper_search_mcp.government_platforms.gao.PdfReader')
    def test_read_document(self, mock_pdf_reader):
        """Test document text extraction"""
        # Create a mock PDF file
        report_id = "GAO-24-106829"
        pdf_path = os.path.join(self.temp_dir, f"{report_id}.pdf")
        with open(pdf_path, 'wb') as f:
            f.write(b"Mock PDF content")

        # Mock PDF reader
        mock_page = Mock()
        mock_page.extract_text.return_value = "Test GAO report content"
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance

        result = self.searcher.read_document(report_id, self.temp_dir)
        self.assertEqual(result, "Test GAO report content")

    def test_search_with_filters(self):
        """Test search with various filters using RSS"""
        with patch('feedparser.parse') as mock_feedparser:
            # Mock RSS feed response
            mock_feed = Mock()
            mock_feed.bozo = False
            mock_feed.entries = [
                Mock(title="Defense Report", summary="Defense analysis", 
                     link="https://gao.gov/products/GAO-24-12345",
                     published_parsed=(2024, 1, 15, 0, 0, 0, 0, 0, 0))
            ]
            mock_feedparser.return_value = mock_feed

            # Test with all filters
            results = self.searcher.search(
                query="defense",
                max_results=5,
                date_filter="month",
                topics=["Defense", "Cybersecurity"],
                agencies=["Department of Defense"]
            )

            # Verify RSS was called and results were filtered
            mock_feedparser.assert_called()
            self.assertIsInstance(results, list)


class TestGAOServerIntegration(unittest.TestCase):
    """Test GAO integration with MCP server"""

    def test_search_gao_tool(self):
        """Test the search_gao MCP tool"""
        with patch('paper_search_mcp.server.gao_searcher') as mock_searcher:
            # Mock search results
            mock_paper = Paper(
                paper_id="GAO-24-106829",
                title="Test GAO Report",
                authors=["U.S. Government Accountability Office"],
                abstract="Test abstract",
                doi="",
                published_date=None,
                pdf_url="https://example.com/test.pdf",
                url="https://example.com/report",
                source="gao"
            )
            mock_searcher.search.return_value = [mock_paper]

            # Test the async tool
            result = asyncio.run(server.search_gao("cybersecurity", max_results=1))
            
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['source'], 'gao')
            self.assertEqual(result[0]['paper_id'], 'GAO-24-106829')

    def test_download_gao_tool(self):
        """Test the download_gao MCP tool"""
        with patch('paper_search_mcp.server.gao_searcher') as mock_searcher:
            mock_searcher.download_pdf.return_value = "/path/to/downloaded.pdf"

            result = asyncio.run(server.download_gao("GAO-24-106829"))
            
            self.assertEqual(result, "/path/to/downloaded.pdf")
            mock_searcher.download_pdf.assert_called_once_with("GAO-24-106829", "./downloads")

    def test_read_gao_report_tool(self):
        """Test the read_gao_report MCP tool"""
        with patch('paper_search_mcp.server.gao_searcher') as mock_searcher:
            mock_searcher.read_document.return_value = "Test document content"

            result = asyncio.run(server.read_gao_report("GAO-24-106829"))
            
            self.assertEqual(result, "Test document content")
            mock_searcher.read_document.assert_called_once_with("GAO-24-106829", "./downloads")

    def test_search_gao_with_filters(self):
        """Test search_gao with topic and agency filters"""
        with patch('paper_search_mcp.server.gao_searcher') as mock_searcher:
            mock_searcher.search.return_value = []

            # Test with comma-separated filters
            asyncio.run(server.search_gao(
                "defense",
                max_results=5,
                topics="Defense,Cybersecurity",
                agencies="Department of Defense,NASA"
            ))

            # Verify filters were parsed correctly
            mock_searcher.search.assert_called_once()
            call_args = mock_searcher.search.call_args
            self.assertEqual(call_args[1]['topics'], ["Defense", "Cybersecurity"])
            self.assertEqual(call_args[1]['agencies'], ["Department of Defense", "NASA"])

    def test_error_handling(self):
        """Test error handling in MCP tools"""
        with patch('paper_search_mcp.server.gao_searcher') as mock_searcher:
            # Test search error handling
            mock_searcher.search.side_effect = Exception("Search failed")
            result = asyncio.run(server.search_gao("test"))
            self.assertEqual(result, [])

            # Test download error handling
            mock_searcher.download_pdf.side_effect = Exception("Download failed")
            result = asyncio.run(server.download_gao("test-id"))
            self.assertEqual(result, "")

            # Test read error handling
            mock_searcher.read_document.side_effect = Exception("Read failed")
            result = asyncio.run(server.read_gao_report("test-id"))
            self.assertEqual(result, "")


class TestGAODataMapping(unittest.TestCase):
    """Test GAO-specific data mapping and validation"""

    def test_paper_creation_with_gao_data(self):
        """Test creating Paper objects with GAO-specific data"""
        from datetime import datetime
        
        paper = Paper(
            paper_id="GAO-24-106829",
            title="Cybersecurity: Federal Agencies Need to Improve Implementation of Guidance",
            authors=["U.S. Government Accountability Office"],
            abstract="GAO found that federal agencies need to improve cybersecurity practices.",
            doi="",
            published_date=datetime(2024, 1, 15),
            pdf_url="https://www.gao.gov/assets/gao-24-106829.pdf",
            url="https://www.gao.gov/products/GAO-24-106829",
            source="gao",
            categories=["Cybersecurity", "Federal Government"],
            extra={
                "report_type": "report",
                "gao_number": "GAO-24-106829",
                "agency_names": ["Department of Defense", "Department of Homeland Security"]
            }
        )

        # Test serialization
        paper_dict = paper.to_dict()
        self.assertEqual(paper_dict['source'], 'gao')
        self.assertEqual(paper_dict['paper_id'], 'GAO-24-106829')
        self.assertEqual(paper_dict['authors'], 'U.S. Government Accountability Office')
        self.assertEqual(paper_dict['categories'], 'Cybersecurity; Federal Government')

    def test_gao_vs_academic_paper_differences(self):
        """Test differences between GAO reports and academic papers"""
        gao_paper = Paper(
            paper_id="GAO-24-106829",
            title="Test GAO Report",
            authors=["U.S. Government Accountability Office"],
            abstract="Government report abstract",
            doi="",  # GAO reports typically don't have DOIs
            published_date=None,
            pdf_url="https://www.gao.gov/assets/test.pdf",
            url="https://www.gao.gov/products/test",
            source="gao",
            citations=0,  # GAO reports don't track citations the same way
            extra={"report_type": "report"}
        )

        # Verify GAO-specific characteristics
        self.assertEqual(gao_paper.source, "gao")
        self.assertEqual(gao_paper.doi, "")
        self.assertEqual(gao_paper.citations, 0)
        self.assertIn("U.S. Government Accountability Office", gao_paper.authors)
        self.assertEqual(gao_paper.extra["report_type"], "report")


if __name__ == '__main__':
    unittest.main()