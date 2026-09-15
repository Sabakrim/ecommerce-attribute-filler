import re
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger("AttributeFiller.SKUMatcher")

def normalize_sku(sku: str) -> str:
    """Normalize SKU string by stripping whitespace and uppercase."""
    return sku.strip().upper()

def is_exact_sku_token_match(target_sku: str, text: str) -> bool:
    """
    Verifies if target_sku appears in text as an isolated token or exact word match.
    Prevents false matches where target_sku (e.g. 'ABC123') is a substring of another SKU (e.g. 'ABC123A' or 'ABC123-B').
    """
    target = normalize_sku(target_sku)
    if not target:
        return False
    
    pattern = r'(?<![A-Z0-9\-_])' + re.escape(target) + r'(?![A-Z0-9\-_])'
    return bool(re.search(pattern, text.upper()))

def score_sku_relevance(target_sku: str, text: str) -> float:
    """
    Returns a score from 0.0 to 1.0 indicating how strongly text relates to target_sku.
    """
    target = normalize_sku(target_sku)
    if not target or not text:
        return 0.0
    
    text_upper = text.upper()
    
    # Check for direct SKU / Model prefix patterns
    direct_patterns = [
        rf"SKU[:\s\-#]+{re.escape(target)}\b",
        rf"MODEL[:\s\-#]+{re.escape(target)}\b",
        rf"ITEM[:\s\-#]+{re.escape(target)}\b",
        rf"PART\s*(?:NO|NUMBER)?[:\s\-#]+{re.escape(target)}\b"
    ]
    
    for pat in direct_patterns:
        if re.search(pat, text_upper):
            return 1.0
            
    if is_exact_sku_token_match(target, text):
        return 0.95
        
    return 0.0

def filter_sku_blocks(target_sku: str, blocks: List[str]) -> List[str]:
    """
    Given a list of text blocks/paragraphs/tables, returns only those blocks that match target_sku.
    """
    matching_blocks = []
    for block in blocks:
        if score_sku_relevance(target_sku, block) > 0.0:
            matching_blocks.append(block)
    return matching_blocks
