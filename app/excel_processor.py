import openpyxl
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from app.sku_matcher import normalize_sku

logger = logging.getLogger("AttributeFiller.ExcelProcessor")

SKU_HEADER_ALIASES = {"sku", "item sku", "product sku", "sku #", "sku number", "item #", "code", "product code", "model", "model #"}

class ExcelProcessingError(Exception):
    """Custom exception for Excel processing errors."""
    pass

def find_header_and_sku_column(sheet: openpyxl.worksheet.worksheet.Worksheet) -> Tuple[int, int, List[Tuple[int, str]]]:
    """
    Scans top 10 rows of worksheet to detect header row and SKU column index.
    Returns: (header_row_index, sku_column_index, list_of_(col_idx, header_name))
    """
    for row_idx in range(1, min(15, sheet.max_row + 1)):
        row_cells = [sheet.cell(row=row_idx, column=c) for c in range(1, sheet.max_column + 1)]
        row_values = [str(c.value).strip() if c.value is not None else "" for c in row_cells]
        
        # Check if any cell matches SKU aliases
        for col_idx, val in enumerate(row_values, start=1):
            if val.lower() in SKU_HEADER_ALIASES:
                # Build header list for all non-empty columns
                headers = []
                for c_i, h_val in enumerate(row_values, start=1):
                    if h_val:
                        headers.append((c_i, h_val))
                return row_idx, col_idx, headers

    # Fallback: assume row 1 is header row and column 1 is SKU column
    first_row_headers = []
    for c in range(1, sheet.max_column + 1):
        v = sheet.cell(row=1, column=c).value
        if v is not None and str(v).strip():
            first_row_headers.append((c, str(v).strip()))
            
    if first_row_headers:
        return 1, 1, first_row_headers

    raise ExcelProcessingError("Could not detect header row or SKU column in the uploaded Excel file.")

def process_excel_template(
    excel_path: Path,
    output_path: Path,
    target_sku: str,
    mapped_attributes: Dict[str, Tuple[str, float]],
    target_worksheet_name: Optional[str] = None,
    overwrite_existing: bool = False
) -> Dict[str, Any]:
    """
    Modifies target SKU row in the uploaded Excel template in-place preserving formatting.
    Fills blank attribute cells with mapped values.
    """
    norm_sku = normalize_sku(target_sku)
    if not norm_sku:
        raise ExcelProcessingError("Requested SKU cannot be empty.")

    try:
        wb = openpyxl.load_workbook(excel_path, data_only=False)
    except Exception as e:
        raise ExcelProcessingError(f"Failed to open Excel file: {str(e)}")

    sheet_names = wb.sheetnames
    if not sheet_names:
        raise ExcelProcessingError("Excel workbook contains no worksheets.")

    matching_worksheets = []

    # Search for worksheet containing target SKU
    for s_name in sheet_names:
        ws = wb[s_name]
        try:
            h_row, sku_col, headers = find_header_and_sku_column(ws)
        except Exception:
            continue

        # Find matching SKU rows in this worksheet
        sku_rows = []
        for r_idx in range(h_row + 1, ws.max_row + 1):
            val = ws.cell(row=r_idx, column=sku_col).value
            if val is not None and normalize_sku(str(val)) == norm_sku:
                sku_rows.append(r_idx)

        if sku_rows:
            matching_worksheets.append((s_name, ws, h_row, sku_col, headers, sku_rows))

    if not matching_worksheets:
        raise ExcelProcessingError(f"SKU '{target_sku}' was not found in any worksheet of the Excel file.")

    if len(matching_worksheets) > 1 and not target_worksheet_name:
        ws_list_str = ", ".join([m[0] for m in matching_worksheets])
        raise ExcelProcessingError(
            f"SKU '{target_sku}' was found in multiple worksheets ({ws_list_str}). "
            f"Please specify which worksheet to update."
        )

    # Pick worksheet
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

    # Verify single SKU row match (Requirement 17: Multiple SKU Matches handling)
    if len(sku_rows) > 1:
        raise ExcelProcessingError("Multiple rows were found for this SKU. Please provide a template with one matching SKU row.")

    target_row = sku_rows[0]

    # Map of header_name -> col_idx
    header_col_map = {h_name: c_idx for c_idx, h_name in headers}

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

        # Determine if we should fill cell
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
    logger.info(f"Successfully saved modified workbook to {output_path}")

    return {
        "worksheet_name": s_name,
        "target_row": target_row,
        "attributes_found": attributes_found,
        "attributes_left_blank": attributes_left_blank,
        "filled_attributes": filled_dict,
        "blank_attributes": blank_list
    }
