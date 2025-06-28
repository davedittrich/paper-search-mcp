# tests/test_jan6.py
import unittest
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch
from paper_search_mcp.government_platforms.jan6 import Jan6Searcher
from paper_search_mcp.paper import Paper
from paper_search_mcp import server


class TestJan6Searcher(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.searcher = Jan6Searcher()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('paper_search_mcp.government_platforms.jan6.requests.Session.get')
    def test_search_via_archive_api(self, mock_get):
        """Test Internet Archive API search functionality"""
        # Mock JSON response from Internet Archive
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': {
                'numFound': 2,
                'docs': [
                    {
                        'identifier': 'january-6th-committee-witness-testimony-20220707-jason-van-tatenhove',
                        'title': 'Jason Van Tatenhove - J6 Committee Witness Testimony Transcript',
                        'description': 'January 6th Committee witness testimony transcript. Witness: Jason Van Tatenhove',
                        'date': '2022-07-07T00:00:00Z',
                        'subject': ['january 6th committee witness testimony transcript'],
                        'mediatype': 'texts',
                        'format': ['Text PDF', 'Additional Text PDF'],
                        'downloads': 73
                    },
                    {
                        'identifier': 'january-6th-committee-witness-testimony-20220420-audra-joy-lemons-johnson',
                        'title': 'Audra Joy Lemons-Johnson - J6 Committee Witness Testimony Transcript',
                        'description': 'January 6th Committee witness testimony transcript. Witness: Audra Joy Lemons-Johnson',
                        'date': '2022-04-20T00:00:00Z',
                        'subject': ['january 6th committee witness testimony transcript'],
                        'mediatype': 'texts',
                        'format': ['Text PDF'],
                        'downloads': 136
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        results = self.searcher.search("testimony", max_results=2)

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)

        # Test first result
        paper = results[0]
        self.assertIsInstance(paper, Paper)
        self.assertEqual(paper.source, 'jan6')
        self.assertIn('U.S. House Select Committee', paper.authors[0])
        self.assertEqual(paper.paper_id, 'january-6th-committee-witness-testimony-20220707-jason-van-tatenhove')
        self.assertIn('Jason Van Tatenhove', paper.title)

    def test_determine_document_type(self):
        """Test document type determination"""
        test_cases = [
            ("Jason Van Tatenhove - J6 Committee Witness Testimony", "testimony transcript", "testimony"),
            ("January 6th Committee Hearing - Opening Statements", "hearing video", "hearing"),
            ("Final Report of the Select Committee", "committee report", "report"),
            ("Financial Disclosure Document", "disclosure form", "disclosure"),
            ("Committee Correspondence Letter", "letter to agency", "correspondence"),
            ("Video Recording of Hearing", "mp4 video file", "video"),
            ("Unknown Document Type", "miscellaneous content", "document")
        ]

        for title, description, expected_type in test_cases:
            result = self.searcher._determine_document_type(title, description)
            self.assertEqual(result, expected_type,
                           f"Failed for title: {title}, description: {description}")

    def test_build_pdf_url(self):
        """Test PDF URL building from Archive.org document"""
        identifier = "january-6th-committee-witness-testimony-20220707-jason-van-tatenhove"

        # Test with PDF format present
        doc_with_pdf = {
            'format': ['Text PDF', 'Additional Text PDF', 'Archive BitTorrent']
        }
        pdf_url = self.searcher._build_pdf_url(identifier, doc_with_pdf)
        expected_url = f"https://archive.org/download/{identifier}/{identifier}.pdf"
        self.assertEqual(pdf_url, expected_url)

        # Test without PDF format
        doc_without_pdf = {
            'format': ['Archive BitTorrent', 'Metadata']
        }
        pdf_url = self.searcher._build_pdf_url(identifier, doc_without_pdf)
        expected_url = f"https://archive.org/download/{identifier}"
        self.assertEqual(pdf_url, expected_url)

    def test_filter_by_date(self):
        """Test date filtering functionality"""
        from datetime import datetime, timedelta

        now = datetime.now()
        old_date = now - timedelta(days=365)
        recent_date = now - timedelta(days=15)

        papers = [
            Paper(
                paper_id="old-doc",
                title="Old Document",
                authors=["Committee"],
                abstract="Old",
                doi="",
                published_date=old_date,
                pdf_url="",
                url="",
                source="jan6"
            ),
            Paper(
                paper_id="recent-doc",
                title="Recent Document",
                authors=["Committee"],
                abstract="Recent",
                doi="",
                published_date=recent_date,
                pdf_url="",
                url="",
                source="jan6"
            )
        ]

        # Test month filter (should only return recent document)
        filtered = self.searcher._filter_by_date(papers, 'month')
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].paper_id, 'recent-doc')

        # Test year filter (should return both)
        filtered = self.searcher._filter_by_date(papers, 'year')
        self.assertEqual(len(filtered), 2)

    @patch('paper_search_mcp.government_platforms.jan6.requests.Session.get')
    def test_download_pdf_with_metadata(self, mock_get):
        """Test PDF download with metadata lookup"""
        document_id = "test-doc-id"

        # Mock metadata response
        metadata_response = Mock()
        metadata_response.status_code = 200
        metadata_response.json.return_value = {
            'files': [
                {
                    'name': 'test-doc-id.pdf',
                    'format': 'Text PDF',
                    'size': '1000000'
                },
                {
                    'name': 'test-doc-id_djvu.txt',
                    'format': 'DjVuTXT',
                    'size': '50000'
                }
            ]
        }

        # Mock PDF download response
        pdf_response = Mock()
        pdf_response.status_code = 200
        pdf_response.content = b"Mock PDF content for Jan6 document"

        # Configure mock to return metadata first, then PDF
        mock_get.side_effect = [metadata_response, pdf_response]

        filepath = self.searcher.download_pdf(document_id, self.temp_dir)

        expected_path = os.path.join(self.temp_dir, f"{document_id}.pdf")
        self.assertEqual(filepath, expected_path)
        self.assertTrue(os.path.exists(filepath))

        # Check file content
        with open(filepath, 'rb') as f:
            content = f.read()
        self.assertEqual(content, b"Mock PDF content for Jan6 document")

    @patch('paper_search_mcp.government_platforms.jan6.requests.Session.get')
    def test_get_archive_ocr_text(self, mock_get):
        """Test OCR text retrieval from Internet Archive"""
        document_id = "test-doc-id"

        # Mock OCR text response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "This is OCR extracted text from the Jan6 document."
        mock_get.return_value = mock_response

        ocr_text = self.searcher._get_archive_ocr_text(document_id)
        self.assertEqual(ocr_text, "This is OCR extracted text from the Jan6 document.")

        # Verify URL was constructed correctly
        expected_url = f"https://archive.org/download/{document_id}/{document_id}_djvu.txt"
        mock_get.assert_called_with(expected_url, params=None, timeout=30)

    @patch('paper_search_mcp.government_platforms.jan6.PdfReader')
    def test_read_document_with_pdf_extraction(self, mock_pdf_reader):
        """Test document text extraction using PyPDF2"""
        document_id = "test-doc-id"
        pdf_path = os.path.join(self.temp_dir, f"{document_id}.pdf")

        # Create mock PDF file
        with open(pdf_path, 'wb') as f:
            f.write(b"Mock PDF content")

        # Mock PDF reader
        mock_page = Mock()
        mock_page.extract_text.return_value = "Test Jan6 document content extracted from PDF"
        mock_reader_instance = Mock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader_instance

        result = self.searcher.read_document(document_id, self.temp_dir)
        self.assertEqual(result, "Test Jan6 document content extracted from PDF")

    def test_search_with_filters(self):
        """Test search with various filter combinations"""
        with patch('paper_search_mcp.government_platforms.jan6.requests.Session.get') as mock_get:
            # Mock Archive.org API response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'response': {
                    'numFound': 1,
                    'docs': [
                        {
                            'identifier': 'test-hearing-doc',
                            'title': 'January 6th Committee Hearing Transcript',
                            'description': 'Hearing testimony and statements',
                            'date': '2022-06-09T00:00:00Z',
                            'subject': ['hearing', 'testimony'],
                            'mediatype': 'texts',
                            'format': ['Text PDF'],
                            'downloads': 100
                        }
                    ]
                }
            }
            mock_get.return_value = mock_response

            # Test with all filters
            results = self.searcher.search(
                query="hearing",
                max_results=5,
                document_type="hearing",
                date_filter="year",
                collection="witness_testimony"
            )

            # Verify API was called and results were processed
            mock_get.assert_called_once()
            self.assertIsInstance(results, list)

    def test_collections_configuration(self):
        """Test that collections are properly configured"""
        expected_collections = {
            'witness_testimony': 'jan-6th-committee-docs',
            'committee_materials': 'House-January-6-Committee-Materials',
            'us_house_hearings': 'us_house_hearings'
        }

        self.assertEqual(self.searcher.COLLECTIONS, expected_collections)

    def test_document_types_configuration(self):
        """Test that document types are properly configured"""
        # Test that all expected document types exist
        expected_types = ['testimony', 'hearing', 'report', 'disclosure', 'correspondence', 'video']

        for doc_type in expected_types:
            self.assertIn(doc_type, self.searcher.DOCUMENT_TYPES)
            self.assertIsInstance(self.searcher.DOCUMENT_TYPES[doc_type], list)
            self.assertTrue(len(self.searcher.DOCUMENT_TYPES[doc_type]) > 0)


class TestJan6ServerIntegration(unittest.TestCase):
    """Test Jan6 integration with MCP server"""

    def test_search_jan6_tool(self):
        """Test the search_jan6 MCP tool"""
        with patch('paper_search_mcp.server.jan6_searcher') as mock_searcher:
            # Mock search results
            mock_paper = Paper(
                paper_id="january-6th-committee-witness-testimony-test",
                title="Test Jan6 Committee Document",
                authors=["U.S. House Select Committee to Investigate January 6th"],
                abstract="Test document abstract",
                doi="",
                published_date=None,
                pdf_url="https://archive.org/download/test/test.pdf",
                url="https://archive.org/details/test",
                source="jan6"
            )
            mock_searcher.search.return_value = [mock_paper]

            # Test the async tool
            result = asyncio.run(server.search_jan6("testimony", max_results=1))

            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['source'], 'jan6')
            self.assertEqual(result[0]['paper_id'], 'january-6th-committee-witness-testimony-test')

    def test_download_jan6_tool(self):
        """Test the download_jan6 MCP tool"""
        with patch('paper_search_mcp.server.jan6_searcher') as mock_searcher:
            mock_searcher.download_pdf.return_value = "/path/to/downloaded_jan6.pdf"

            result = asyncio.run(server.download_jan6("test-doc-id"))

            self.assertEqual(result, "/path/to/downloaded_jan6.pdf")
            mock_searcher.download_pdf.assert_called_once_with("test-doc-id", "./downloads")

    def test_read_jan6_document_tool(self):
        """Test the read_jan6_document MCP tool"""
        with patch('paper_search_mcp.server.jan6_searcher') as mock_searcher:
            mock_searcher.read_document.return_value = "Test Jan6 document content"

            result = asyncio.run(server.read_jan6_document("test-doc-id"))

            self.assertEqual(result, "Test Jan6 document content")
            mock_searcher.read_document.assert_called_once_with("test-doc-id", "./downloads")

    def test_search_jan6_with_filters(self):
        """Test search_jan6 with filter parameters"""
        with patch('paper_search_mcp.server.jan6_searcher') as mock_searcher:
            mock_searcher.search.return_value = []

            # Test with all filter parameters
            asyncio.run(server.search_jan6(
                "hearing",
                max_results=5,
                document_type="testimony",
                date_filter="month",
                source_filter="official",
                collection="committee_materials"
            ))

            # Verify all parameters were passed correctly
            mock_searcher.search.assert_called_once()
            call_args = mock_searcher.search.call_args
            self.assertEqual(call_args[1]['query'], "hearing")
            self.assertEqual(call_args[1]['max_results'], 5)
            self.assertEqual(call_args[1]['document_type'], "testimony")
            self.assertEqual(call_args[1]['date_filter'], "month")
            self.assertEqual(call_args[1]['source_filter'], "official")
            self.assertEqual(call_args[1]['collection'], "committee_materials")

    def test_error_handling(self):
        """Test error handling in MCP tools"""
        with patch('paper_search_mcp.server.jan6_searcher') as mock_searcher:
            # Test search error handling
            mock_searcher.search.side_effect = Exception("Search failed")
            result = asyncio.run(server.search_jan6("test"))
            self.assertEqual(result, [])

            # Test download error handling
            mock_searcher.download_pdf.side_effect = Exception("Download failed")
            result = asyncio.run(server.download_jan6("test-id"))
            self.assertEqual(result, "")

            # Test read error handling
            mock_searcher.read_document.side_effect = Exception("Read failed")
            result = asyncio.run(server.read_jan6_document("test-id"))
            self.assertEqual(result, "")

    def test_default_parameters(self):
        """Test MCP tools with default parameters"""
        with patch('paper_search_mcp.server.jan6_searcher') as mock_searcher:
            mock_searcher.search.return_value = []

            # Test search with minimal parameters
            asyncio.run(server.search_jan6("test"))

            call_args = mock_searcher.search.call_args
            self.assertEqual(call_args[1]['max_results'], 10)  # Default value
            self.assertEqual(call_args[1]['collection'], "witness_testimony")  # Default value
            self.assertIsNone(call_args[1]['document_type'])  # Default None
            self.assertIsNone(call_args[1]['date_filter'])  # Default None


class TestJan6DataMapping(unittest.TestCase):
    """Test Jan6-specific data mapping and validation"""

    def test_paper_creation_with_jan6_data(self):
        """Test creating Paper objects with Jan6-specific data"""
        from datetime import datetime

        paper = Paper(
            paper_id="january-6th-committee-witness-testimony-20220707-jason-van-tatenhove",
            title="Jason Van Tatenhove - J6 Committee Witness Testimony Transcript",
            authors=["U.S. House Select Committee to Investigate January 6th"],
            abstract="January 6th Committee witness testimony transcript.",
            doi="",
            published_date=datetime(2022, 7, 7),
            pdf_url="https://archive.org/download/january-6th-committee-witness-testimony-20220707-jason-van-tatenhove/january-6th-committee-witness-testimony-20220707-jason-van-tatenhove.pdf",
            url="https://archive.org/details/january-6th-committee-witness-testimony-20220707-jason-van-tatenhove",
            source="jan6",
            categories=["january 6th committee witness testimony transcript"],
            extra={
                "document_type": "testimony",
                "archive_identifier": "january-6th-committee-witness-testimony-20220707-jason-van-tatenhove",
                "mediatype": "texts",
                "formats": ["Text PDF", "Additional Text PDF"],
                "downloads": 73,
                "archive_source": True
            }
        )

        # Test serialization
        paper_dict = paper.to_dict()
        self.assertEqual(paper_dict['source'], 'jan6')
        self.assertEqual(paper_dict['paper_id'], 'january-6th-committee-witness-testimony-20220707-jason-van-tatenhove')
        self.assertIn('U.S. House Select Committee', paper_dict['authors'])

    def test_jan6_vs_academic_paper_differences(self):
        """Test differences between Jan6 documents and academic papers"""
        jan6_paper = Paper(
            paper_id="test-jan6-doc",
            title="Test Jan6 Committee Document",
            authors=["U.S. House Select Committee to Investigate January 6th"],
            abstract="Committee document abstract",
            doi="",  # Jan6 documents don't have DOIs
            published_date=None,
            pdf_url="https://archive.org/download/test/test.pdf",
            url="https://archive.org/details/test",
            source="jan6",
            citations=0,  # Jan6 documents don't track citations
            extra={"document_type": "testimony", "archive_source": True}
        )

        # Verify Jan6-specific characteristics
        self.assertEqual(jan6_paper.source, "jan6")
        self.assertEqual(jan6_paper.doi, "")
        self.assertEqual(jan6_paper.citations, 0)
        self.assertIn("U.S. House Select Committee", jan6_paper.authors[0])
        self.assertEqual(jan6_paper.extra["document_type"], "testimony")
        self.assertTrue(jan6_paper.extra["archive_source"])

    def test_archive_identifier_mapping(self):
        """Test Internet Archive identifier mapping"""
        searcher = Jan6Searcher()

        # Test typical Jan6 committee document identifier
        test_doc = {
            'identifier': 'january-6th-committee-witness-testimony-20220707-jason-van-tatenhove',
            'title': 'Jason Van Tatenhove - J6 Committee Witness Testimony Transcript',
            'description': 'Committee witness testimony',
            'date': '2022-07-07T00:00:00Z',
            'subject': ['testimony'],
            'mediatype': 'texts',
            'format': ['Text PDF'],
            'downloads': 73
        }

        paper = searcher._create_paper_from_archive_doc(test_doc)

        self.assertIsNotNone(paper)
        self.assertEqual(paper.paper_id, test_doc['identifier'])
        self.assertEqual(paper.extra['archive_identifier'], test_doc['identifier'])
        self.assertTrue(paper.extra['archive_source'])


if __name__ == '__main__':
    unittest.main()