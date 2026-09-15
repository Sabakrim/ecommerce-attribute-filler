import json
import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from app.sku_matcher import is_exact_sku_token_match, score_sku_relevance

logger = logging.getLogger("AttributeFiller.WebExtractor")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

class WebExtractionError(Exception):
    """Custom exception for web scraping and extraction errors."""
    pass

def extract_json_ld_specs(soup: BeautifulSoup) -> Dict[str, str]:
    """Extracts specs from schema.org JSON-LD scripts on the page."""
    specs: Dict[str, str] = {}
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in ["Product", "IndividualProduct", "ProductModel"]:
                    if "name" in item: specs["Product Name"] = str(item["name"])
                    if "category" in item: specs["Type"] = str(item["category"])
                    if "brand" in item:
                        brand = item["brand"]
                        specs["Brand"] = brand.get("name", str(brand)) if isinstance(brand, dict) else str(brand)
                    if "color" in item: specs["Color"] = str(item["color"])
                    if "material" in item: specs["Material"] = str(item["material"])
                    if "depth" in item: specs["Depth"] = str(item["depth"])
                    if "height" in item: specs["Height"] = str(item["height"])
                    if "width" in item: specs["Width"] = str(item["width"])
                    if "weight" in item: specs["Weight"] = str(item["weight"])
                    
                    # Parse additionalProperty array
                    add_props = item.get("additionalProperty", [])
                    if isinstance(add_props, list):
                        for prop in add_props:
                            if isinstance(prop, dict) and "name" in prop and "value" in prop:
                                specs[str(prop["name"]).strip()] = str(prop["value"]).strip()
        except Exception as e:
            logger.debug(f"JSON-LD parsing error: {e}")
    return specs

def extract_tables_specs(soup: BeautifulSoup) -> Dict[str, str]:
    """Extracts specs from HTML tables."""
    specs: Dict[str, str] = {}
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all(["th", "td"])
            if len(cols) == 2:
                k = cols[0].get_text(strip=True)
                v = cols[1].get_text(strip=True)
                if k and v and len(k) < 80:
                    specs[k] = v
    return specs

def extract_dl_specs(soup: BeautifulSoup) -> Dict[str, str]:
    """Extracts specs from definition lists (<dl>)."""
    specs: Dict[str, str] = {}
    dls = soup.find_all("dl")
    for dl in dls:
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            k = dt.get_text(strip=True)
            v = dd.get_text(strip=True)
            if k and v and len(k) < 80:
                specs[k] = v
    return specs

def extract_key_value_divs(soup: BeautifulSoup) -> Dict[str, str]:
    """Extracts key-value pairs from styled spec div/span lists."""
    specs: Dict[str, str] = {}
    # Find text matching pattern 'Key: Value' or 'Key - Value'
    text_content = soup.get_text(separator="\n")
    for line in text_content.splitlines():
        line = line.strip()
        match = re.match(r'^([A-Za-z0-9\s/\-\(\)\.]{2,40})\s*[:=]\s*(.+)$', line)
        if match:
            k, v = match.group(1).strip(), match.group(2).strip()
            if k.lower() not in ["http", "https", "javascript"] and len(v) < 200:
                specs[k] = v
    return specs

def extract_specs_from_url(url: str, target_sku: str) -> Dict[str, str]:
    """
    Downloads URL content, verifies SKU presence, and extracts all specification key-value pairs.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise WebExtractionError(f"Failed to access URL '{url}': {str(e)}")

    page_html = response.text
    soup = BeautifulSoup(page_html, "html.parser")
    page_text = soup.get_text()

    # SKU Verification (Requirement 9)
    if not is_exact_sku_token_match(target_sku, page_text):
        # Also check meta tags or scripts
        meta_skus = soup.find_all("meta", content=re.compile(re.escape(target_sku), re.I))
        if not meta_skus:
            logger.warning(f"SKU '{target_sku}' not found on website page text.")
            raise WebExtractionError(f"Requested SKU '{target_sku}' was not found on the website page: {url}")

    extracted_specs: Dict[str, str] = {}

    # 1. JSON-LD structured data
    json_ld_specs = extract_json_ld_specs(soup)
    extracted_specs.update(json_ld_specs)

    # 2. Specification tables
    table_specs = extract_tables_specs(soup)
    extracted_specs.update(table_specs)

    # 3. Definition lists
    dl_specs = extract_dl_specs(soup)
    extracted_specs.update(dl_specs)

    # 4. Key-Value divs/spans
    kv_specs = extract_key_value_divs(soup)
    for k, v in kv_specs.items():
        if k not in extracted_specs:
            extracted_specs[k] = v

    if not extracted_specs:
        raise WebExtractionError(f"Accessed URL successfully, but no structured product specifications were found on the page.")

    logger.info(f"Extracted {len(extracted_specs)} specs from website {url}")
    return extracted_specs
