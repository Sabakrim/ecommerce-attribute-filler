import re
import logging
from typing import Tuple, List, Optional, Any

logger = logging.getLogger("AttributeFiller.SKUMatcher")

def clean_sku_key(sku: Any) -> str:
    if sku is None:
        return ""
    s = str(sku).strip().upper()
    return re.sub(r'[^A-Z0-9]', '', s)

def normalize_sku(sku: Any) -> str:
    if sku is None:
        return ""
    s = str(sku).replace('\xa0', ' ').strip().upper()
    s = s.replace('–', '-').replace('—', '-')
    if re.match(r'^\d+\.0$', s):
        s = s[:-2]
    return s

def is_sku_match(target_sku: str, cell_value: Any) -> bool:
    if cell_value is None:
        return False
    val_str = str(cell_value).strip()
    if not val_str:
        return False

    norm_target = normalize_sku(target_sku)
    norm_val = normalize_sku(val_str)

    if norm_target and norm_target == norm_val:
        return True

    clean_target = clean_sku_key(target_sku)
    clean_val = clean_sku_key(val_str)

    if not clean_target or not clean_val:
        return False

    if clean_target == clean_val:
        return True

    if len(clean_target) >= 5 and clean_target in clean_val:
        return True

    return False

def is_exact_sku_token_match(target_sku: str, text: str) -> bool:
    target = normalize_sku(target_sku)
    if not target:
        return False
    text_norm = normalize_sku(text)
    pattern = r'(?<![A-Z0-9\-_])' + re.escape(target) + r'(?![A-Z0-9\-_])'
    if re.search(pattern, text_norm):
        return True
    return is_sku_match(target_sku, text)

def score_sku_relevance(target_sku: str, text: str) -> float:
    target = normalize_sku(target_sku)
    if not target or not text:
        return 0.0
    text_upper = normalize_sku(text)
    direct_patterns = [
        rf"SKU[:\s\-#]+{re.escape(target)}\b",
        rf"MODEL[:\s\-#]+{re.escape(target)}\b",
        rf"ITEM[:\s\-#]+{re.escape(target)}\b",
        rf"PART\s*(?:NO|NUMBER)?[:\s\-#]+{re.escape(target)}\b"
    ]
    for pat in direct_patterns:
        if re.search(pat, text_upper):
            return 1.0
    if is_exact_sku_token_match(target_sku, text):
        return 0.95
    return 0.0

def filter_sku_blocks(target_sku: str, blocks: List[str]) -> List[str]:
    matching_blocks = []
    for block in blocks:
        if score_sku_relevance(target_sku, block) > 0.0:
            matching_blocks.append(block)
    return matching_blocks
