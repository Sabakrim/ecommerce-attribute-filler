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
