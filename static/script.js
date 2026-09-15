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
            excelFileName.textContent = `Selected: ${e.target.files[0].name}`;
            excelDropZone.style.borderColor = 'var(--accent-emerald)';
        }
    });

    pdfFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            pdfFileName.textContent = `Selected: ${e.target.files[0].name}`;
            pdfDropZone.style.borderColor = 'var(--accent-emerald)';
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!excelFileInput.files || excelFileInput.files.length === 0) {
            showError('Please upload an Excel template (.xlsx) file.');
            return;
        }

        const skuInput = document.getElementById('sku').value.trim();
        if (!skuInput) {
            showError('Please enter a SKU.');
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
            document.getElementById('step-4'),
            document.getElementById('step-5'),
            document.getElementById('step-6')
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
        }, 600);

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
                showError(data.error || 'Failed to process request.');
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
        document.getElementById('res-blank-count').textContent = data.attributes_left_blank;
        
        const downloadLink = document.getElementById('download-link');
        downloadLink.href = data.download_url;
        downloadLink.setAttribute('download', data.download_filename);

        const tbody = document.getElementById('summary-tbody');
        tbody.innerHTML = '';
        
        const filledKeys = Object.keys(data.filled_attributes);
        if (filledKeys.length === 0) {
            const rawKeys = Object.keys(data.extracted_specs || {});
            if (rawKeys.length > 0) {
                rawKeys.forEach(k => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="font-weight: 500; color: #cbd5e1;">[Extracted Source Spec] ${k}</td>
                        <td style="color: #f59e0b; font-weight: 500;">${data.extracted_specs[k]}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td colspan="2" style="text-align:center; color: var(--text-muted);">No specification key-value pairs could be extracted from the source.</td>`;
                tbody.appendChild(tr);
            }
        } else {
            filledKeys.forEach(header => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-weight: 500; color: #f1f5f9;">${header}</td>
                    <td style="color: var(--accent-emerald); font-weight: 600;">${data.filled_attributes[header]}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        resultCard.classList.remove('hidden');
    }

    errorCloseBtn.addEventListener('click', () => {
        errorCard.classList.add('hidden');
        form.classList.remove('hidden');
    });

    resetBtn.addEventListener('click', () => {
        resultCard.classList.add('hidden');
        form.reset();
        excelFileName.textContent = 'Click or drag & drop your Excel template (.xlsx)';
        excelDropZone.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        pdfFileName.textContent = 'Click or drag & drop product specification PDF';
        pdfDropZone.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        form.classList.remove('hidden');
    });
});
