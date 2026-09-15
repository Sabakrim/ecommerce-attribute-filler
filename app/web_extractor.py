import json
import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from app.sku_matcher import is_exact_sku_token_match

logger = logging.getLogger("AttributeFiller.WebExtractor")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

class WebExtractionError(Exception):
    pass

def extract_json_ld_and_js_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    scripts = soup.find_all("script")
    for script in scripts:
        if not script.string:
            continue
        if script.get("type") == "application/ld+json":
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        for field in ["name", "category", "color", "material", "depth", "height", "width", "weight", "model", "sku", "mpn", "type", "capacity", "voltage", "power"]:
                            if field in item and item[field]:
                                specs[field.replace('_', ' ').title()] = str(item[field]).strip()
                        if "brand" in item:
                            b = item["brand"]
                            specs["Brand"] = b.get("name", str(b)) if isinstance(b, dict) else str(b)
                        add_props = item.get("additionalProperty", [])
                        if isinstance(add_props, list):
                            for prop in add_props:
                                if isinstance(prop, dict) and "name" in prop and "value" in prop:
                                    k, v = str(prop["name"]).strip(), str(prop["value"]).strip()
                                    if k and v: specs[k] = v
            except Exception:
                pass

        js_matches = re.findall(r'"([A-Za-z0-9\s_\-\(\)]{2,40})"\s*:\s*"([^"\n]{1,200})"', script.string)
        for k, v in js_matches:
            k_clean = k.strip()
            v_clean = v.strip()
            if k_clean and v_clean and not k_clean.startswith("http") and k_clean.lower() not in ["url", "src", "type", "id", "class"]:
                if k_clean not in specs:
                    specs[k_clean] = v_clean

    return specs

extract_json_ld_specs = extract_json_ld_and_js_specs

def extract_meta_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    meta_tags = soup.find_all("meta")
    for meta in meta_tags:
        key = meta.get("name") or meta.get("property") or meta.get("itemprop")
        val = meta.get("content")
        if key and val:
            key_clean = key.replace('og:', '').replace('product:', '').replace('twitter:', '').replace('_', ' ').strip().title()
            val_clean = str(val).strip()
            if key_clean and val_clean and len(key_clean) < 60 and len(val_clean) < 300:
                specs[key_clean] = val_clean
    return specs

def extract_tables_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all(["th", "td"])
            if len(cols) == 2:
                k = cols[0].get_text(strip=True)
                v = cols[1].get_text(strip=True)
                if k and v and len(k) < 80 and len(v) < 300:
                    specs[k] = v
            elif len(cols) == 4:
                k1, v1 = cols[0].get_text(strip=True), cols[1].get_text(strip=True)
                k2, v2 = cols[2].get_text(strip=True), cols[3].get_text(strip=True)
                if k1 and v1 and len(k1) < 80: specs[k1] = v1
                if k2 and v2 and len(k2) < 80: specs[k2] = v2
    return specs

def extract_block_and_sibling_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    
    for el in soup.find_all(["li", "p", "div", "span"]):
        strong = el.find(["strong", "b", "span", "th", "h4", "h5", "dt"])
        if strong:
            k = strong.get_text(strip=True).rstrip(":=- ")
            full_text = el.get_text(strip=True)
            if full_text.startswith(strong.get_text(strip=True)):
                v = full_text[len(strong.get_text(strip=True)):].strip(" :=-")
                if k and v and 2 <= len(k) < 80 and len(v) < 300:
                    specs[k] = v
                    continue

        text = el.get_text(strip=True)
        m = re.match(r'^([A-Za-z0-9\s/\-\(\)\.]{2,50})\s*[:=]\s*(.+)$', text)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            if k.lower() not in ["http", "https", "javascript", "note", "warning"] and len(v) < 300:
                specs[k] = v

    divs = soup.find_all(["div", "span", "p"])
    for i in range(len(divs) - 1):
        k_text = divs[i].get_text(strip=True).rstrip(":")
        v_text = divs[i+1].get_text(strip=True)
        if 2 <= len(k_text) < 40 and 1 <= len(v_text) < 200:
            if any(term in k_text.lower() for term in ["capacity", "type", "size", "material", "voltage", "power", "color", "width", "height", "depth", "plug"]):
                if k_text not in specs:
                    specs[k_text] = v_text

    return specs

def extract_specs_from_url(url: str, target_sku: str) -> Dict[str, str]:
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

    if not is_exact_sku_token_match(target_sku, page_text):
        logger.warning(f"SKU '{target_sku}' not found in webpage text, extracting all specs from URL: {url}")

    extracted_specs: Dict[str, str] = {}

    meta_specs = extract_meta_specs(soup)
    extracted_specs.update(meta_specs)

    json_ld_specs = extract_json_ld_and_js_specs(soup)
    extracted_specs.update(json_ld_specs)

    table_specs = extract_tables_specs(soup)
    extracted_specs.update(table_specs)

    block_specs = extract_block_and_sibling_specs(soup)
    for k, v in block_specs.items():
        if k not in extracted_specs:
            extracted_specs[k] = v

    if not extracted_specs:
        for line in page_text.splitlines():
            line = line.strip()
            match = re.match(r'^([A-Za-z0-9\s/\-\(\)\.]{2,40})\s*[:=]\s*(.+)$', line)
            if match:
                k, v = match.group(1).strip(), match.group(2).strip()
                if k.lower() not in ["http", "https", "javascript"] and len(v) < 200:
                    extracted_specs[k] = v

    if not extracted_specs:
        raise WebExtractionError(f"Accessed URL successfully, but no structured product specifications could be extracted from the page HTML.")

    logger.info(f"Extracted {len(extracted_specs)} specs from website {url}")
    return extracted_specs
