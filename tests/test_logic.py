import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.processor import dict_to_ris
from src.extraction import extract_text_from_pdf

class TestRisGenerator(unittest.TestCase):
    
    def test_ris_formatting(self):
        data = {
            "TY": "JOUR",
            "TI": "Test Title",
            "AU": ["Doe, John", "Smith, Jane"],
            "PY": "2023",
            "JO": "Journal of Testing",
            "SP": "10",
            "EP": "20",
            "DO": "10.1234/test",
            "N1": "Some notes"
        }
        ris = dict_to_ris(data)
        
        expected_lines = [
            "TY  - JOUR",
            "TI  - Test Title",
            "AU  - Doe, John",
            "AU  - Smith, Jane",
            "PY  - 2023",
            "JO  - Journal of Testing",
            "SP  - 10",
            "EP  - 20",
            "DO  - 10.1234/test",
            "N1  - Some notes",
            "ER  - ",
            ""
        ]
        self.assertEqual(ris, "\n".join(expected_lines))

    @patch('src.extraction.pypdf.PdfReader')
    def test_extraction_logic_short_pdf(self, mock_reader_cls):
        # Mock a 3 page PDF
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock(), MagicMock()]
        mock_reader.pages[0].extract_text.return_value = "Page 1"
        mock_reader.pages[1].extract_text.return_value = "Page 2"
        mock_reader.pages[2].extract_text.return_value = "Page 3"
        
        mock_reader_cls.return_value = mock_reader
        
        # Request Head=2, Tail=4 (Should cover all 3)
        text = extract_text_from_pdf("dummy.pdf", head_pages=2, tail_pages=4)
        
        self.assertIn("--- Page 1 ---", text)
        self.assertIn("Page 1", text)
        self.assertIn("--- Page 3 ---", text)
        # Should not duplicate if ranges overlap
        self.assertEqual(text.count("--- Page 2 ---"), 1)

    @patch('src.extraction.pypdf.PdfReader')
    def test_extraction_logic_long_pdf(self, mock_reader_cls):
        # Mock a 10 page PDF
        mock_reader = MagicMock()
        pages = []
        for i in range(10):
            p = MagicMock()
            p.extract_text.return_value = f"Page Content {i+1}"
            pages.append(p)
        mock_reader.pages = pages
        mock_reader_cls.return_value = mock_reader
        
        # Head=2 (0,1), Tail=2 (8,9)
        text = extract_text_from_pdf("dummy.pdf", head_pages=2, tail_pages=2)
        
        self.assertIn("Page 1", text)
        self.assertIn("Page 2", text)
        self.assertNotIn("Page 5", text)
        self.assertIn("Page 9", text)
        self.assertIn("Page 10", text)

if __name__ == '__main__':
    unittest.main()
