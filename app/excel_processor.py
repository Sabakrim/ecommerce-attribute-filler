import openpyxl
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from app.sku_matcher import normalize_sku, is_sku_match, clean_sku_key

logger = logging.getLogger("AttributeFiller.ExcelProcessor")

SKU_HEADER_ALIASES = {
    "sku", "item sku", "product sku", "sku #", "sku number", "sku id", "sku code", "sku name",
    "item #", "item code", "item no", "item number", "part #", "part no", "part number", "part id",
    "code", "product code", "product id", "product no", "product number",
    "model", "model #", "model no", "model number", "mpn", "mfr part #",
    "article no", "article number", "supplier sku", "seller sku", "vendor sku", "style #", "style no", "id", "name", "product"
}

class ExcelProcessingError(Exception):
    """Custom exception for Excel processing errors."""
    pass

def find_header_and_sku_column(sheet: openpyxl.worksheet.worksheet.Worksheet) -> Tuple[int, int, List[Tuple[int, str]]]:
    for row_idx in range(1, min(35, sheet.max_row + 1)):
        row_cells = [sheet.cell(row=row_idx, column=c) for c in range(1, sheet.max_column + 1)]
        row_values = [str(c.value).strip() if c.value is not None else "" for c in row_cells]
        
        for col_idx, val in enumerate(row_values, start=1):
            if val.lower() in SKU_HEADER_ALIASES:
                headers = []
                for c_i, h_val in enumerate(row_values, start=1):
                    if h_val:
                        headers.append((c_i, h_val))
                return row_idx, col_idx, headers

    for r in range(1, min(15, sheet.max_row + 1)):
        headers = []
        for c in range(1, sheet.max_column + 1):
            v = sheet.cell(row=r, column=c).value
            if v is not None and str(v).strip():
                headers.append((c, str(v).strip()))
        if headers:
            return r, headers[0][0], headers

    raise ExcelProcessingError("Could not detect header row or SKU column in the uploaded Excel file.")

def process_excel_template(
    excel_path: Path,
    output_path: Path,
    target_sku: str,
    mapped_attributes: Dict[str, Tuple[str, float]],
    target_worksheet_name: Optional[str] = None,
    overwrite_existing: bool = False
) -> Dict[str, Any]:
    if not target_sku or not target_sku.strip():
        raise ExcelProcessingError("Requested SKU cannot be empty.")

    target_sku_clean = target_sku.strip()
    target_sku_alphanumeric = clean_sku_key(target_sku_clean)

    try:
        wb = openpyxl.load_workbook(excel_path, data_only=False)
        wb_evaluated = openpyxl.load_workbook(excel_path, data_only=True)
    except Exception as e:
        raise ExcelProcessingError(f"Failed to open Excel file. Please ensure it is a valid .xlsx file: {str(e)}")

    sheet_names = wb.sheetnames
    if not sheet_names:
        raise ExcelProcessingError("Excel workbook contains no worksheets.")

    matching_worksheets = []
    detected_headers_summary = {}

    for s_name in sheet_names:
        ws = wb[s_name]
        ws_eval = wb_evaluated[s_name]

        try:
            _, _, h_list = find_header_and_sku_column(ws)
            detected_headers_summary[s_name] = [h[1] for h in h_list[:8]]
        except Exception:
            detected_headers_summary[s_name] = ["Unable to auto-detect header row"]

        try:
            h_row, sku_col, headers = find_header_and_sku_column(ws)
            sku_rows = []
            for r_idx in range(h_row + 1, ws.max_row + 1):
                v1 = ws.cell(row=r_idx, column=sku_col).value
                v2 = ws_eval.cell(row=r_idx, column=sku_col).value
                
                if (is_sku_match(target_sku_clean, v1) or 
                    is_sku_match(target_sku_clean, v2) or 
                    (v1 and target_sku_alphanumeric in clean_sku_key(v1)) or 
                    (v2 and target_sku_alphanumeric in clean_sku_key(v2))):
                    sku_rows.append(r_idx)

            if sku_rows:
                matching_worksheets.append((s_name, ws, h_row, sku_col, headers, sku_rows))
                continue
        except Exception:
            pass

        found_cell = None
        for r_idx in range(1, ws.max_row + 1):
            for c_idx in range(1, ws.max_column + 1):
                v1 = ws.cell(row=r_idx, column=c_idx).value
                v2 = ws_eval.cell(row=r_idx, column=c_idx).value
                
                s1 = clean_sku_key(v1) if v1 is not None else ""
                s2 = clean_sku_key(v2) if v2 is not None else ""
                
                if (is_sku_match(target_sku_clean, v1) or 
                    is_sku_match(target_sku_clean, v2) or 
                    (s1 and target_sku_alphanumeric in s1) or 
                    (s2 and target_sku_alphanumeric in s2)):
                    found_cell = (r_idx, c_idx)
                    break
            if found_cell:
                break

        if found_cell:
            t_row, s_col = found_cell
            h_row = 1
            for search_r in range(t_row - 1, 0, -1):
                row_vals = [str(ws.cell(row=search_r, column=c).value or "").strip() for c in range(1, ws.max_column + 1)]
                if any(row_vals):
                    h_row = search_r
                    break

            headers = []
            for c in range(1, ws.max_column + 1):
                h_val = ws.cell(row=h_row, column=c).value
                if h_val is not None and str(h_val).strip():
                    headers.append((c, str(h_val).strip()))

            matching_worksheets.append((s_name, ws, h_row, s_col, headers, [t_row]))

    wb_evaluated.close()

    if not matching_worksheets:
        diag_info = "; ".join([f"Worksheet '{k}': headers {v}" for k, v in detected_headers_summary.items()])
        raise ExcelProcessingError(
            f"SKU '{target_sku}' was not found in any cell of the uploaded Excel file. "
            f"Detected structure -> {diag_info}. "
            f"Please verify that the SKU exists in an unmerged text cell of your Excel file."
        )

    if len(matching_worksheets) > 1 and not target_worksheet_name:
        ws_list_str = ", ".join([m[0] for m in matching_worksheets])
        raise ExcelProcessingError(
            f"SKU '{target_sku}' was found in multiple worksheets ({ws_list_str}). "
            f"Please specify which worksheet to update."
        )

    selected_ws_data = None
    if target_worksheet_name:
        for m in matching_worksheets:
            if m[0] == target_worksheet_name:
                selected_ws_data = m
                break
        if not selected_ws_data:
            raise ExcelProcessingError(f"Worksheet '{target_worksheet_name}' does not contain SKU '{target_sku}'.")
    else:
        selected_ws_data = matching_worksheets[0]

    s_name, ws, h_row, sku_col, headers, sku_rows = selected_ws_data

    if len(sku_rows) > 1:
        raise ExcelProcessingError("Multiple rows were found for this SKU. Please provide a template with one matching SKU row.")

    target_row = sku_rows[0]

    attributes_found = 0
    attributes_left_blank = 0
    filled_dict: Dict[str, str] = {}
    blank_list: List[str] = []

    for c_idx, h_name in headers:
        if c_idx == sku_col:
            continue

        cell = ws.cell(row=target_row, column=c_idx)
        existing_val = cell.value
        is_blank = existing_val is None or str(existing_val).strip() == ""

        if is_blank or overwrite_existing:
            if h_name in mapped_attributes:
                extracted_val, confidence = mapped_attributes[h_name]
                if extracted_val and str(extracted_val).strip():
                    cell.value = str(extracted_val).strip()
                    filled_dict[h_name] = str(extracted_val).strip()
                    attributes_found += 1
                else:
                    attributes_left_blank += 1
                    blank_list.append(h_name)
            else:
                attributes_left_blank += 1
                blank_list.append(h_name)
        else:
            logger.info(f"Preserving existing cell value '{existing_val}' for header '{h_name}'")

    wb.save(output_path)
    return {
        "worksheet_name": s_name,
        "target_row": target_row,
        "attributes_found": attributes_found,
        "attributes_left_blank": attributes_left_blank,
        "filled_attributes": filled_dict,
        "blank_attributes": blank_list
    }
