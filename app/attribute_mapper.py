import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from rapidfuzz import fuzz

logger = logging.getLogger("AttributeFiller.AttributeMapper")

COMMON_SYNONYMS: Dict[str, List[str]] = {
    "capacity": ["volume", "product capacity", "holding capacity", "liquid capacity", "boiler capacity", "storage capacity", "size"],
    "material": ["construction", "made from", "body material", "material type", "fabric", "primary material"],
    "height": ["overall height", "product height", "height (in.)", "height (in)", "height (cm)", "h", "ht"],
    "diameter": ["overall diameter", "product diameter", "dia.", "dia", "diameter (in.)", "diameter (cm)"],
    "width": ["overall width", "product width", "width (in.)", "width (in)", "width (cm)", "w"],
    "length": ["overall length", "product length", "length (in.)", "length (cm)", "l"],
    "depth": ["overall depth", "product depth", "depth (in.)", "depth (cm)", "d"],
    "color": ["colour", "finish", "body color", "color/finish", "shade", "hue"],
    "type": ["product type", "category", "style", "item type", "appliance type"],
    "voltage": ["operating voltage", "power supply", "voltage (v)", "voltage rating", "volts"],
    "power": ["wattage", "power rating", "power output", "watts", "power consumption"],
    "temperature range": ["temp range", "temperature rating", "temp control", "operating temperature"],
    "weight": ["item weight", "product weight", "net weight", "shipping weight"],
    "refrigeration type": ["cooling type", "defrost type", "refrigerator type"],
    "door type": ["number of doors", "door design", "door style"],
    "groups": ["number of groups", "group count", "espresso groups"]
}

def normalize_label(label: str) -> str:
    """Normalize label string for matching."""
    cleaned = re.sub(r'[^\w\s]', ' ', label.lower())
    return re.sub(r'\s+', ' ', cleaned).strip()

def parse_dimensions_string(dim_str: str) -> Dict[str, str]:
    """
    Parses a dimension string like '10" L x 5" W x 8" H' or 'L: 10 in, W: 5 in, H: 8 in'.
    Returns a dict with keys 'length', 'width', 'height', 'depth'.
    If dimensions are ambiguous (e.g. '10 x 5 x 8' without L/W/H labels), returns empty dict to enforce NO GUESSING rule!
    """
    results: Dict[str, str] = {}
    if not dim_str:
        return results

    # Check for explicit labels in dimension string
    # Patterns like: 10" L x 5" W x 8" H  or  L: 10", W: 5", H: 8"
    l_match = re.search(r'([\d\.]+(?:\s*(?:["\']|in|inch|inches|cm|mm))?)\s*(?:\(?L\)?|Length)\b|\b(?:L|Length)\s*[:=]\s*([\d\.]+(?:\s*(?:["\']|in|inch|inches|cm|mm))?)', dim_str, re.I)
    w_match = re.search(r'([\d\.]+(?:\s*(?:["\']|in|inch|inches|cm|mm))?)\s*(?:\(?W\)?|Width)\b|\b(?:W|Width)\s*[:=]\s*([\d\.]+(?:\s*(?:["\']|in|inch|inches|cm|mm))?)', dim_str, re.I)
    h_match = re.search(r'([\d\.]+(?:\s*(?:["\']|in|inch|inches|cm|mm))?)\s*(?:\(?H\)?|Height)\b|\b(?:H|Height)\s*[:=]\s*([\d\.]+(?:\s*(?:["\']|in|inch|inches|cm|mm))?)', dim_str, re.I)
    d_match = re.search(r'([\d\.]+(?:\s*(?:["\']|in|inch|inches|cm|mm))?)\s*(?:\(?D\)?|Depth)\b|\b(?:D|Depth)\s*[:=]\s*([\d\.]+(?:\s*(?:["\']|in|inch|inches|cm|mm))?)', dim_str, re.I)

    if l_match:
        val = l_match.group(1) or l_match.group(2)
        if val: results['length'] = val.strip()
    if w_match:
        val = w_match.group(1) or w_match.group(2)
        if val: results['width'] = val.strip()
    if h_match:
        val = h_match.group(1) or h_match.group(2)
        if val: results['height'] = val.strip()
    if d_match:
        val = d_match.group(1) or d_match.group(2)
        if val: results['depth'] = val.strip()

    return results

class BaseAttributeMapper:
    """Base interface for attribute mapping engines."""
    def map_attributes(
        self, 
        target_headers: List[str], 
        extracted_specs: Dict[str, str]
    ) -> Dict[str, Tuple[str, float]]:
        """
        Maps extracted specifications to target Excel headers.
        Returns Dict[excel_header, (extracted_value, confidence_score)]
        """
        raise NotImplementedError

class RuleBasedMapper(BaseAttributeMapper):
    """
    Local rule-based + RapidFuzz mapper with strict confidence thresholds and NO GUESSING rules.
    Zero-paid API requirement.
    """
    def __init__(self, min_confidence: float = 80.0):
        self.min_confidence = min_confidence

    def map_attributes(
        self, 
        target_headers: List[str], 
        extracted_specs: Dict[str, str]
    ) -> Dict[str, Tuple[str, float]]:
        
        mapped_results: Dict[str, Tuple[str, float]] = {}
        if not target_headers or not extracted_specs:
            return mapped_results

        # Prepare normalized maps
        normalized_specs = {normalize_label(k): (k, v) for k, v in extracted_specs.items() if v and str(v).strip()}
        
        # Check for dimension splitting
        dimension_vals = {}
        for norm_k, (orig_k, orig_v) in normalized_specs.items():
            if norm_k in ["dimensions", "size", "overall dimensions", "product dimensions"]:
                parsed_dims = parse_dimensions_string(str(orig_v))
                if parsed_dims:
                    dimension_vals.update(parsed_dims)

        for header in target_headers:
            header_str = str(header).strip()
            norm_header = normalize_label(header_str)
            if not norm_header:
                continue

            matched_val = None
            confidence = 0.0

            # 1. Check if parsed from dimensions first
            if norm_header in dimension_vals:
                matched_val = dimension_vals[norm_header]
                confidence = 100.0
                mapped_results[header_str] = (matched_val, confidence)
                continue

            # 2. Exact normalized match
            if norm_header in normalized_specs:
                _, matched_val = normalized_specs[norm_header]
                confidence = 100.0
                mapped_results[header_str] = (matched_val, confidence)
                continue

            # 3. Known Synonym matching
            synonyms = COMMON_SYNONYMS.get(norm_header, [])
            found_synonym = False
            for syn in synonyms:
                norm_syn = normalize_label(syn)
                if norm_syn in normalized_specs:
                    _, matched_val = normalized_specs[norm_syn]
                    confidence = 95.0
                    found_synonym = True
                    break
            
            if found_synonym:
                mapped_results[header_str] = (matched_val, confidence)
                continue

            # 4. Fuzzy Matching with RapidFuzz
            best_match_key = None
            best_score = 0.0

            for norm_spec_key in normalized_specs.keys():
                # Token set ratio handles word ordering differences
                score = fuzz.token_set_ratio(norm_header, norm_spec_key)
                if score > best_score:
                    best_score = score
                    best_match_key = norm_spec_key

            if best_score >= self.min_confidence and best_match_key:
                _, matched_val = normalized_specs[best_match_key]
                mapped_results[header_str] = (matched_val, best_score)
                logger.info(f"Fuzzy match '{header_str}' -> '{best_match_key}' (score: {best_score:.1f})")
            else:
                logger.info(f"Header '{header_str}' left blank (best match '{best_match_key}' score: {best_score:.1f} < threshold)")

        return mapped_results

class LocalAIMapper(BaseAttributeMapper):
    """
    Placeholder/Hook for optional future Local AI models (e.g. Ollama).
    NOT active by default, ensuring zero-paid-service & zero-dependency compliance.
    """
    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def map_attributes(
        self, 
        target_headers: List[str], 
        extracted_specs: Dict[str, str]
    ) -> Dict[str, Tuple[str, float]]:
        # Fallback to RuleBasedMapper if Local AI service is not running
        fallback = RuleBasedMapper()
        return fallback.map_attributes(target_headers, extracted_specs)
