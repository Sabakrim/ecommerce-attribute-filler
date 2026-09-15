document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('filler-form');
    const submitBtn = document.getElementById('submit-btn');
    const statusCard = document.getElementById('status-card');
    const resultCard = document.getElementById('result-card');
    const errorCard = document.getElementById('error-card');
    const errorMessage = document.getElementById('error-message');
    const errorCloseBtn = document.getElementById('error-close-btn');
    const resetBtn = document.getElementById('reset-btn');

    const labelSourceUrl = document.getElementById('label-source-url');
    const labelSourcePdf = document.getElementById('label-source-pdf');
    const urlContainer = document.getElementById('url-input-container');
    const pdfContainer = document.getElementById('pdf-input-container');
    const websiteUrlInput = document.getElementById('website_url');
    const pdfFileInput = document.getElementById('pdf_file');

    const excelFileInput = document.getElementById('excel_file');
    const excelDropZone = document.getElementById('excel-drop-zone');
    const excelFileName = document.getElementById('excel-file-name');

    const pdfDropZone = document.getElementById('pdf-drop-zone');
    const pdfFileName = document.getElementById('pdf-file-name');

    const radioInputs = document.querySelectorAll('input[name="source_type"]');
    radioInputs.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'url') {
                labelSourceUrl.classList.add('active');
                labelSourcePdf.classList.remove('active');
                urlContainer.classList.remove('hidden');
                pdfContainer.classList.add('hidden');
                websiteUrlInput.required = true;
                pdfFileInput.required = false;
            } else {
                labelSourcePdf.classList.add('active');
                labelSourceUrl.classList.remove('active');
                pdfContainer.classList.remove('hidden');
                urlContainer.classList.add('hidden');
                websiteUrlInput.required = false;
                pdfFileInput.required = true;
            }
        });
    });

    excelFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            excelFileName.textContent = `Selected Template: ${e.target.files[0].name}`;
            excelDropZone.style.borderColor = 'var(--accent-emerald)';
        }
    });

    pdfFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            pdfFileName.textContent = `Selected PDF: ${e.target.files[0].name}`;
            pdfDropZone.style.borderColor = 'var(--accent-emerald)';
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const skuInput = document.getElementById('sku').value.trim();
        if (!skuInput) {
            showError('Please enter a SKU or Model code.');
            return;
        }

        const sourceType = document.querySelector('input[name="source_type"]:checked').value;
        if (sourceType === 'url') {
            const urlVal = websiteUrlInput.value.trim();
            if (!urlVal) {
                showError('Please enter a Website URL.');
                return;
            }
        } else if (sourceType === 'pdf') {
            if (!pdfFileInput.files || pdfFileInput.files.length === 0) {
                showError('Please upload a PDF file.');
                return;
            }
        }

        errorCard.classList.add('hidden');
        resultCard.classList.add('hidden');
        form.classList.add('hidden');
        statusCard.classList.remove('hidden');

        const steps = [
            document.getElementById('step-1'),
            document.getElementById('step-2'),
            document.getElementById('step-3'),
            document.getElementById('step-4')
        ];

        steps.forEach((s, idx) => {
            s.classList.remove('active', 'done');
            if (idx === 0) s.classList.add('active');
        });

        let stepIdx = 0;
        const stepInterval = setInterval(() => {
            if (stepIdx < steps.length - 1) {
                steps[stepIdx].classList.remove('active');
                steps[stepIdx].classList.add('done');
                stepIdx++;
                steps[stepIdx].classList.add('active');
            }
        }, 500);

        try {
            const formData = new FormData(form);

            if (sourceType === 'url') {
                let urlVal = websiteUrlInput.value.trim();
                if (!urlVal.startsWith('http://') && !urlVal.startsWith('https://')) {
                    urlVal = 'https://' + urlVal;
                }
                formData.set('website_url', urlVal);
            }

            const response = await fetch('/api/fill-attributes', {
                method: 'POST',
                body: formData
            });

            clearInterval(stepInterval);

            const data = await response.json();

            if (!response.ok || !data.success) {
                showError(data.error || 'Failed to extract specifications.');
                return;
            }

            showResult(data);

        } catch (err) {
            clearInterval(stepInterval);
            showError(`Network or server error: ${err.message}`);
        }
    });

    function showError(msg) {
        statusCard.classList.add('hidden');
        errorMessage.textContent = msg;
        errorCard.classList.remove('hidden');
    }

    function showResult(data) {
        statusCard.classList.add('hidden');
        
        document.getElementById('res-sku').textContent = data.sku;
        document.getElementById('res-found-count').textContent = data.attributes_found;
        
        const downloadLink = document.getElementById('download-link');
        downloadLink.href = data.download_url;
        downloadLink.setAttribute('download', data.download_filename);

        const tbody = document.getElementById('summary-tbody');
        tbody.innerHTML = '';
        
        const attrsToDisplay = (Object.keys(data.filled_attributes).length > 0) ? data.filled_attributes : data.extracted_specs;
        const keys = Object.keys(attrsToDisplay || {});

        if (keys.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td colspan="2" style="text-align:center; color: var(--text-muted);">No specification key-value pairs could be extracted from the source.</td>`;
            tbody.appendChild(tr);
        } else {
            keys.forEach(k => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #f1f5f9;">${k}</td>
                    <td style="color: var(--accent-emerald); font-weight: 600;">${attrsToDisplay[k]}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        resultCard.classList.remove('hidden');
    }

    const copyBtn = document.getElementById('copy-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const tbody = document.getElementById('summary-tbody');
            let copyText = "Attribute Name\tAttribute Value\n";
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(r => {
                const cols = r.querySelectorAll('td');
                if (cols.length === 2) {
                    copyText += `${cols[0].textContent.trim()}\t${cols[1].textContent.trim()}\n`;
                }
            });
            navigator.clipboard.writeText(copyText).then(() => {
                copyBtn.innerHTML = '<span>Copied to Clipboard!</span>';
                setTimeout(() => {
                    copyBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg><span>Copy All Attributes to Clipboard</span>';
                }, 2000);
            }).catch(err => {
                alert('Copy failed: ' + err);
            });
        });
    }

    errorCloseBtn.addEventListener('click', () => {
        errorCard.classList.add('hidden');
        form.classList.remove('hidden');
    });

    resetBtn.addEventListener('click', () => {
        resultCard.classList.add('hidden');
        form.reset();
        excelFileName.textContent = 'Drag & drop template file here if you want to auto-fill an existing Excel';
        excelDropZone.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        pdfFileName.textContent = 'Click or drag & drop product specification PDF';
        pdfDropZone.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        form.classList.remove('hidden');
    });
});
