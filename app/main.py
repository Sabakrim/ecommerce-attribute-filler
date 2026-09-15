import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models import FillResultResponse, ErrorResponse
from app.utils import (
    save_temp_upload, cleanup_file, validate_file_size, 
    MAX_EXCEL_BYTES, MAX_PDF_BYTES, OUTPUT_DIR, sanitize_filename
)
from app.excel_processor import (
    process_excel_template, find_header_and_sku_column, create_standalone_specs_excel,
    ExcelProcessingError, openpyxl
)
from app.web_extractor import extract_specs_from_url, WebExtractionError
from app.pdf_extractor import extract_specs_from_pdf, PDFExtractionError
from app.attribute_mapper import RuleBasedMapper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AttributeFiller.Main")

app = FastAPI(
    title="E-commerce Attribute Filler",
    description="Automated tool for extracting product attributes from Web URLs or PDFs into Excel.",
    version="1.0.0"
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    return FileResponse(str(index_file))

@app.post("/api/fill-attributes", response_model=FillResultResponse)
async def api_fill_attributes(
    sku: str = Form(...),
    source_type: str = Form(...),
    excel_file: Optional[UploadFile] = File(None),
    website_url: Optional[str] = Form(None),
    pdf_file: Optional[UploadFile] = File(None),
    worksheet_name: Optional[str] = Form(None),
    overwrite_existing: bool = Form(False)
):
    temp_excel_path: Optional[Path] = None
    temp_pdf_path: Optional[Path] = None

    try:
        sku_clean = sku.strip()
        if not sku_clean:
            raise HTTPException(status_code=400, detail="SKU field cannot be empty.")

        extracted_specs = {}

        if source_type == "url":
            if not website_url or not website_url.strip():
                raise HTTPException(status_code=400, detail="Website URL is required when source type is set to Website.")
            logger.info(f"Extracting specs from website: {website_url} for SKU: {sku_clean}")
            extracted_specs = extract_specs_from_url(website_url.strip(), sku_clean)

        elif source_type == "pdf":
            if not pdf_file or not pdf_file.filename:
                raise HTTPException(status_code=400, detail="PDF file upload is required when source type is set to PDF.")
            if not pdf_file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Uploaded source file must be a PDF (.pdf) file.")

            pdf_bytes = await pdf_file.read()
            validate_file_size(pdf_bytes, MAX_PDF_BYTES, "PDF")
            temp_pdf_path = save_temp_upload(pdf_bytes, pdf_file.filename)
            logger.info(f"Extracting specs from PDF: {pdf_file.filename} for SKU: {sku_clean}")
            extracted_specs = extract_specs_from_pdf(temp_pdf_path, sku_clean)
        else:
            raise HTTPException(status_code=400, detail="Invalid source type selected. Must be 'url' or 'pdf'.")

        safe_sku = sanitize_filename(sku_clean)
        output_filename = f"{safe_sku}_specs.xlsx"
        output_filepath = OUTPUT_DIR / output_filename

        if excel_file and excel_file.filename and excel_file.filename.endswith(".xlsx"):
            excel_bytes = await excel_file.read()
            validate_file_size(excel_bytes, MAX_EXCEL_BYTES, "Excel")
            temp_excel_path = save_temp_upload(excel_bytes, excel_file.filename)

            try:
                wb = openpyxl.load_workbook(temp_excel_path, data_only=True)
                ws = wb[worksheet_name] if worksheet_name and worksheet_name in wb.sheetnames else wb.active
                _, _, header_tuples = find_header_and_sku_column(ws)
                target_headers = [h_name for _, h_name in header_tuples]
                wb.close()
            except Exception:
                target_headers = list(extracted_specs.keys())

            mapper = RuleBasedMapper(min_confidence=70.0)
            mapped_attributes = mapper.map_attributes(target_headers, extracted_specs)

            fill_res = process_excel_template(
                excel_path=temp_excel_path,
                output_path=output_filepath,
                target_sku=sku_clean,
                mapped_attributes=mapped_attributes,
                extracted_specs=extracted_specs,
                target_worksheet_name=worksheet_name,
                overwrite_existing=overwrite_existing
            )
            found_count = fill_res["attributes_found"] if fill_res["attributes_found"] > 0 else len(extracted_specs)
            filled_attrs = fill_res["filled_attributes"] if fill_res["filled_attributes"] else extracted_specs
        else:
            create_standalone_specs_excel(output_filepath, sku_clean, extracted_specs)
            found_count = len(extracted_specs)
            filled_attrs = extracted_specs

        download_url = f"/api/download/{output_filename}"

        return FillResultResponse(
            success=True,
            sku=sku_clean,
            worksheet_name="Extracted_Specs",
            target_row=1,
            attributes_found=found_count,
            attributes_left_blank=0,
            filled_attributes=filled_attrs,
            blank_attributes=[],
            extracted_specs=extracted_specs,
            download_url=download_url,
            download_filename=output_filename,
            message="Attributes extracted and formatted successfully."
        )

    except (ExcelProcessingError, WebExtractionError, PDFExtractionError, ValueError) as e:
        logger.warning(f"Processing error: {str(e)}")
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(success=False, error=str(e)).dict()
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=ErrorResponse(success=False, error=e.detail).dict()
        )
    except Exception as e:
        logger.error(f"Unexpected server error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(success=False, error=f"Internal Server Error: {str(e)}").dict()
        )
    finally:
        if temp_excel_path: cleanup_file(temp_excel_path)
        if temp_pdf_path: cleanup_file(temp_pdf_path)

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    safe_name = sanitize_filename(filename)
    file_path = OUTPUT_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Requested file was not found or has expired.")
    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
