import pypdf
import os

def extract_text_from_pdf(pdf_path: str, head_pages: int = 2, tail_pages: int = 4) -> str:
    """
    Extracts text from the first N and last M pages of a PDF.
    If the PDF has fewer pages than N+M, extracts all text.
    """
    text_content = []
    
    try:
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        if total_pages == 0:
            return ""

        # Determine which pages to extract
        pages_to_extract = set()
        
        # Head pages
        for i in range(min(head_pages, total_pages)):
            pages_to_extract.add(i)
            
        # Tail pages
        for i in range(max(0, total_pages - tail_pages), total_pages):
            pages_to_extract.add(i)
            
        # Sort indices to keep order
        sorted_indices = sorted(list(pages_to_extract))
        
        for i in sorted_indices:
            try:
                page = reader.pages[i]
                text = page.extract_text()
                if text:
                    text_content.append(f"--- Page {i+1} ---")
                    text_content.append(text)
            except Exception as e:
                text_content.append(f"--- Page {i+1} (Extraction Failed) ---")
                
        return "\n".join(text_content)

    except Exception as e:
        # In a real app, we might want to log this better
        print(f"Error reading {pdf_path}: {e}")
        return ""
