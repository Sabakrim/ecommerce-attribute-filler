import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import fitz  # PyMuPDF
import pdfplumber
from app.sku_matcher import is_exact_sku_token_match, normalize_sku

logger = logging.getLogger("AttributeFiller.PDFExtractor")

class PDFExtractionError(Exception):
    """Custom exception for PDF extraction errors."""
    pass

def extract_specs_from_pdf_table(pdf_path: Path, target_sku: str) -> Dict[str, str]:
    """
    Scans PDF pages using pdfplumber to find tables containing target_sku.
    If a table row matches target_sku, maps header columns to that row's cells.
    """
    specs: Dict[str, str] = {}
    norm_sku = normalize_sku(target_sku)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    headers = [str(h).strip() if h else f"Col_{i}" for i, h in enumerate(table[0])]
                    
                    sku_col_idx = -1
                    for idx, h in enumerate(headers):
                        if h.lower() in ["sku", "model", "item #", "part #", "code", "model number", "item number"]:
                            sku_col_idx = idx
                            break

                    for row in table[1:]:
                        if not row:
                            continue

                        row_str = " ".join([str(c) for c in row if c is not None])
                        
                        is_match = False
                        if sku_col_idx >= 0 and len(row) > sku_col_idx and row[sku_col_idx] is not None:
                            is_match = (normalize_sku(str(row[sku_col_idx])) == norm_sku)
                        else:
                            is_match = is_exact_sku_token_match(target_sku, row_str)

                        if is_match:
                            logger.info(f"Found matching table row for SKU '{target_sku}' on page {page_idx}")
                            for col_i, cell_val in enumerate(row):
                                if col_i < len(headers) and cell_val is not None:
                                    h_name = headers[col_i]
                                    val_str = str(cell_val).strip()
                                    if h_name.lower() not in ["sku", "model", "item #", "code"] and val_str:
                                        specs[h_name] = val_str
                            return specs
    except Exception as e:
        logger.warning(f"pdfplumber table extraction note: {e}")

    return specs

def extract_specs_from_pdf_text(pdf_path: Path, target_sku: str) -> Dict[str, str]:
    """
    Scans PDF text page by page using PyMuPDF (fitz), finds section strictly belonging to target_sku,
    and parses key-value lines without taking values from neighboring SKUs.
    """
    specs: Dict[str, str] = {}
    norm_sku = normalize_sku(target_sku)

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        raise PDFExtractionError(f"Failed to open PDF file: {str(e)}")

    sku_found_in_doc = False

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        if is_exact_sku_token_match(target_sku, text):
            sku_found_in_doc = True
            logger.info(f"Target SKU '{target_sku}' found on PDF page {page_num + 1}")

            # Split text into sections by double newline or SKU / Model markers
            sections = re.split(r'\n\s*\n|(?=(?:SKU|MODEL|ITEM)\s*[:=]\s*)', text, flags=re.I)
            
            # Select sections that explicitly match target SKU
            target_sections = [sec for sec in sections if is_exact_sku_token_match(target_sku, sec)]

            # Fallback block bounding if section splitting didn't isolate it
            if not target_sections:
                target_match = re.search(r'(?<![A-Z0-9\-_])' + re.escape(norm_sku) + r'(?![A-Z0-9\-_])', text.upper())
                if target_match:
                    start_pos = target_match.start()
                    next_sku_match = re.search(r'\b(?:SKU|MODEL|ITEM)\s*[:=]', text[start_pos + len(norm_sku):], re.I)
                    if next_sku_match:
                        end_pos = start_pos + len(norm_sku) + next_sku_match.start()
                        target_sections.append(text[start_pos:end_pos])
                    else:
                        target_sections.append(text[start_pos:])

            for sec in target_sections:
                lines = sec.splitlines()
                for line in lines:
                    line = line.strip()
                    m1 = re.match(r'^([A-Za-z0-9\s/\-\(\)\.]{2,40})\s*[:=]\s*(.+)$', line)
                    if m1:
                        k, v = m1.group(1).strip(), m1.group(2).strip()
                        if k.upper() != norm_sku and len(v) < 200:
                            if k not in specs:
                                specs[k] = v
                        continue

                    m2 = re.match(r'^([A-Za-z0-9\s/\-\(\)\.]{2,40})\s*\.{2,}\s*(.+)$', line)
                    if m2:
                        k, v = m2.group(1).strip(), m2.group(2).strip()
                        if k.upper() != norm_sku and len(v) < 200:
                            if k not in specs:
                                specs[k] = v

    doc.close()

    if not sku_found_in_doc:
        raise PDFExtractionError(f"Requested SKU '{target_sku}' was not found in the uploaded PDF document.")

    return specs

def extract_specs_from_pdf(pdf_path: Path, target_sku: str) -> Dict[str, str]:
    """
    Main entry point for PDF extraction.
    Combines table row extraction and text specification extraction.
    """
    table_specs = extract_specs_from_pdf_table(pdf_path, target_sku)
    text_specs = extract_specs_from_pdf_text(pdf_path, target_sku)

    combined = {}
    combined.update(text_specs)
    combined.update(table_specs)

    if not combined:
        raise PDFExtractionError(f"Found SKU '{target_sku}' in PDF, but no specification key-value pairs could be extracted.")

    logger.info(f"Extracted {len(combined)} specs from PDF for SKU '{target_sku}'")
    return combined
