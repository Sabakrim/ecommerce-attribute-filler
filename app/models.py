from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class AttributeMappingResult(BaseModel):
    excel_header: str
    extracted_value: str
    source_label: Optional[str] = None
    confidence: float = 1.0

class FillResultResponse(BaseModel):
    success: bool
    sku: str
    worksheet_name: Optional[str] = None
    target_row: Optional[int] = None
    attributes_found: int = 0
    attributes_left_blank: int = 0
    filled_attributes: Dict[str, str] = Field(default_factory=dict)
    blank_attributes: List[str] = Field(default_factory=list)
    download_url: Optional[str] = None
    download_filename: Optional[str] = None
    message: str = ""

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[str] = None
