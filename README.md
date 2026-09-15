# E-commerce Attribute Filler

A lightweight, zero-paid-service web application designed to automatically populate e-commerce product attribute columns in existing Excel templates using product specifications extracted from a **Website URL** or **PDF catalog**.

---

## Key Features

- **ZERO Paid API / Model Requirement**: Operates 100% locally with free, open-source Python libraries (`openpyxl`, `PyMuPDF`, `pdfplumber`, `requests`, `BeautifulSoup4`, `RapidFuzz`). No OpenAI, Gemini, or Claude API keys needed.
- **100% Template-Driven**: No hardcoded category attributes. Reads header columns dynamically from any Excel template (Glassware, Refrigerators, Furniture, Electronics, etc.).
- **Excel Formatting Preservation**: Preserves cell fonts, borders, fills, column widths, row heights, formulas, merged cells, and unedited rows.
- **Strict No-Guessing Engine**: Only fills cells when high-confidence specification matches are found in the source. Ambiguous attributes remain blank.
- **Smart Data Sources**:
  - **Website URL**: Parses HTML tables, definition lists (`<dl>`), key-value blocks, and JSON-LD structured product data (`schema.org/Product`).
  - **PDF Document**: Extracts tables and key-value spec blocks while isolating data to the exact requested SKU to prevent neighboring SKU cross-contamination.
- **Render Free Web Service Ready**: Configured for instant cloud deployment with `0.0.0.0` binding and dynamic `$PORT` environment variable support.

---

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI routes, middleware & static files
│   ├── models.py              # Pydantic data schemas
│   ├── excel_processor.py     # openpyxl template parsing & formatting-preserving updates
│   ├── web_extractor.py       # Website scraper (HTML tables & JSON-LD parser)
│   ├── pdf_extractor.py       # PDF extractor (PyMuPDF & pdfplumber)
│   ├── sku_matcher.py         # SKU boundary isolation & token matcher
│   ├── attribute_mapper.py    # RapidFuzz fuzzy mapper, synonyms & dimension splitter
│   └── utils.py               # File validation & temporary cleanup
├── static/
│   ├── style.css              # Custom responsive dark-theme glassmorphism CSS
│   └── script.js              # Frontend interactive AJAX & progress steps logic
├── templates/
│   └── index.html             # Main single-card user interface
├── tests/
│   ├── generate_test_files.py # Helper script to create test templates & PDFs
│   ├── test_suite.py          # Automated runner for all 10 required test cases
│   ├── sample_template.xlsx   # Generated test Excel (Glass category)
│   ├── sample_refrig.xlsx     # Generated test Excel (Refrigerator category)
│   └── sample_product.pdf     # Generated multi-SKU sample PDF document
├── requirements.txt           # Dependency declaration
├── Render.yaml                # Render deployment configuration
├── Procfile                   # Process file for cloud hosts
├── README.md                  # System & deployment documentation
├── .env.example               # Environment settings template
└── .gitignore                 # Excludes temp files, venv, and outputs
```

---

## How to Run Locally

### Prerequisites
- Python 3.9+ installed on your system.

### Step 1: Clone or Navigate to Project Directory
```bash
cd "c:\Users\sujay\OneDrive\Desktop\Attribute APK"
```

### Step 2: Create Virtual Environment
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Free Open-Source Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Start Application Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 5: Open Application in Web Browser
Open your browser and navigate to:
[http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## How to Run Automated Tests

To execute the full test suite covering all 10 required test scenarios:

```bash
python tests/test_suite.py
```

### Executed Scenarios:
1. `test_01_excel_pdf_exact_sku`: Excel + PDF + exact SKU attribute population.
2. `test_02_excel_pdf_sku_not_found`: Non-existent SKU error validation.
3. `test_03_missing_attributes_remain_blank`: Verifies missing attributes remain blank.
4. `test_04_multi_row_isolation`: Verifies non-target rows remain untouched.
5. `test_05_preserve_existing_cell_values`: Verifies pre-filled cells are not overwritten by default.
6. `test_06_similar_sku_isolation`: Verifies target SKU (`ABC123`) is distinguished from similar SKUs (`ABC123A`, `ABC123-B`).
7. `test_07_website_extraction_mock`: Verifies JSON-LD and HTML table parsing.
8. `test_08_inaccessible_website`: Verifies clean error handling for inaccessible URLs.
9. `test_09_ambiguous_dimensions_no_guessing`: Enforces NO GUESSING rule on unlabelled dimensions (`10 x 5 x 8`).
10. `test_10_completely_different_category_template`: Verifies dynamic header reading on different categories (Refrigerators).

---

## GitHub Repository Setup

To push this repository to GitHub:

```bash
git init
git add .
git commit -m "Initial commit: E-commerce Attribute Filler application"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ecommerce-attribute-filler.git
git push -u origin main
```

---

## How to Deploy to Render Free Web Service

1. Create a free account at [Render.com](https://render.com).
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository.
4. Configure the service settings:
   - **Name**: `ecommerce-attribute-filler`
   - **Region**: Choose closest region
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free`
5. Add Environment Variables under **Advanced**:
   - `PORT`: `10000` (Render will automatically override this dynamically)
   - `MAX_EXCEL_MB`: `20`
   - `MAX_PDF_MB`: `50`
6. Click **Create Web Service**.

---

## Free Hosting & Technical Limitations

- **Temporary Storage**: Uploaded files and generated Excel output files are stored temporarily in memory/disk and automatically cleaned up per request. There is no permanent database or file storage required.
- **Free Instance Idle Sleep**: Free instances on Render or similar free hosts spin down after periods of inactivity. The initial request after sleeping may take 30–50 seconds (cold start).
- **Web Scraping Restrictions**: Certain websites protected by heavy anti-bot security (Cloudflare, CAPTCHA, JavaScript-only SPA rendering) may block automated requests. In such cases, the system returns a clear error message.

---

## Zero-Paid-Service Compliance Confirmation

This application has been audited and confirmed to contain **zero paid dependencies, zero cloud AI requirements, zero paid databases, and zero required subscriptions**.
