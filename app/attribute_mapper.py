import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from rapidfuzz import fuzz

logger = logging.getLogger("AttributeFiller.AttributeMapper")

COMMON_SYNONYMS: Dict[str, List[str]] = {
    "capacity": ["volume", "tank capacity", "product capacity", "holding capacity", "liquid capacity", "boiler capacity", "storage capacity", "water capacity", "gross capacity", "net capacity", "size"],
    "material": ["construction", "made from", "body material", "material type", "fabric", "primary material"],
    "height": ["overall height", "product height", "height (in.)", "height (in)", "height (cm)", "h", "ht"],
    "diameter": ["overall diameter", "product diameter", "dia.", "dia", "diameter (in.)", "diameter (cm)"],
    "width": ["overall width", "product width", "width (in.)", "width (in)", "width (cm)", "w"],
    "length": ["overall length", "product length", "length (in.)", "length (cm)", "l"],
    "depth": ["overall depth", "product depth", "depth (in.)", "depth (cm)", "d"],
    "color": ["colour", "finish", "body color", "color/finish", "shade", "hue"],
    "type": ["product type", "category", "style", "item type", "appliance type"],
    "plug type": ["electrical plug type", "power plug type", "plug style", "plug", "socket type", "power cord plug"],
    "inlet size": ["water inlet size", "water inlet", "inlet pipe size", "inlet diameter", "inlet connection"],
    "outlet size": ["water outlet size", "water outlet", "outlet pipe size", "outlet diameter", "outlet connection"],
    "voltage": ["operating voltage", "power supply", "voltage (v)", "voltage rating", "volts", "input voltage"],
    "power": ["wattage", "power rating", "power output", "watts", "power consumption", "motor power"],
    "temperature range": ["temp range", "temperature rating", "temp control", "operating temperature"],
    "weight": ["item weight", "product weight", "net weight", "shipping weight"],
    "refrigeration type": ["cooling type", "defrost type", "refrigerator type"],
    "door type": ["number of doors", "door design", "door style"],
    "groups": ["number of groups", "group count", "espresso groups"]
}

QUALIFYING_PREFIXES = {
    "water", "tank", "product", "overall", "item", "body", "primary", "operating",
    "rated", "input", "supply", "electrical", "power", "net", "gross", "shipping",
    "total", "unit", "main", "liquid", "boiler", "storage", "commercial"
}

def normalize_label(label: str) -> str:
    cleaned = re.sub(r'[^\w\s]', ' ', label.lower())
    return re.sub(r'\s+', ' ', cleaned).strip()

def strip_qualifying_prefixes(label: str) -> str:
    words = normalize_label(label).split()
    filtered = [w for w in words if w not in QUALIFYING_PREFIXES]
    return " ".join(filtered) if filtered else normalize_label(label)

def parse_dimensions_string(dim_str: str) -> Dict[str, str]:
    results: Dict[str, str] = {}
    if not dim_str:
        return results

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
    def map_attributes(self, target_headers: List[str], extracted_specs: Dict[str, str]) -> Dict[str, Tuple[str, float]]:
        raise NotImplementedError

class RuleBasedMapper(BaseAttributeMapper):
    def __init__(self, min_confidence: float = 70.0):
        self.min_confidence = min_confidence

    def map_attributes(self, target_headers: List[str], extracted_specs: Dict[str, str]) -> Dict[str, Tuple[str, float]]:
        mapped_results: Dict[str, Tuple[str, float]] = {}
        if not target_headers or not extracted_specs:
            return mapped_results

        normalized_specs = {normalize_label(k): (k, v) for k, v in extracted_specs.items() if v and str(v).strip()}
        
        dimension_vals = {}
        for norm_k, (orig_k, orig_v) in normalized_specs.items():
            if norm_k in ["dimensions", "size", "overall dimensions", "product dimensions"]:
                parsed_dims = parse_dimensions_string(str(orig_v))
                if parsed_dims:
                    dimension_vals.update(parsed_dims)

        for header in target_headers:
            header_str = str(header).strip()
            norm_header = normalize_label(header_str)
            stripped_header = strip_qualifying_prefixes(header_str)
            if not norm_header:
                continue

            matched_val = None

            if norm_header in dimension_vals:
                mapped_results[header_str] = (dimension_vals[norm_header], 100.0)
                continue

            if norm_header in normalized_specs:
                _, matched_val = normalized_specs[norm_header]
                mapped_results[header_str] = (matched_val, 100.0)
                continue

            synonyms = COMMON_SYNONYMS.get(norm_header, [])
            found_synonym = False
            for syn in synonyms:
                norm_syn = normalize_label(syn)
                if norm_syn in normalized_specs:
                    _, matched_val = normalized_specs[norm_syn]
                    found_synonym = True
                    break
            
            if found_synonym:
                mapped_results[header_str] = (matched_val, 95.0)
                continue

            prefix_match_found = False
            for norm_spec_key, (orig_k, orig_v) in normalized_specs.items():
                stripped_spec = strip_qualifying_prefixes(orig_k)
                if stripped_spec == norm_header or stripped_spec == stripped_header or norm_header in norm_spec_key:
                    mapped_results[header_str] = (orig_v, 90.0)
                    logger.info(f"Contextual match '{header_str}' <- '{orig_k}' (value: '{orig_v}')")
                    prefix_match_found = True
                    break
            
            if prefix_match_found:
                continue

            best_match_key = None
            best_score = 0.0

            for norm_spec_key in normalized_specs.keys():
                score = fuzz.token_set_ratio(norm_header, norm_spec_key)
                if score > best_score:
                    best_score = score
                    best_match_key = norm_spec_key

            if best_score >= self.min_confidence and best_match_key:
                _, matched_val = normalized_specs[best_match_key]
                mapped_results[header_str] = (matched_val, best_score)

        return mapped_results

class LocalAIMapper(BaseAttributeMapper):
    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def map_attributes(self, target_headers: List[str], extracted_specs: Dict[str, str]) -> Dict[str, Tuple[str, float]]:
        fallback = RuleBasedMapper()
        return fallback.map_attributes(target_headers, extracted_specs)
