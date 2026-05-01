---
name: pdf
description: "Handle PDF generation, templating, and manipulation in Python. Using reportlab, weasyprint, or Jinja2 HTML-to-PDF."
---

# PDF Skill

## Overview
This skill covers generating, modifying, and debugging PDF documents in Python — whether using HTML-to-PDF conversion (WeasyPrint/wkhtmltopdf), templating (Jinja2), or direct PDF creation (ReportLab).

## When to Use
- When generating PDF reports for agents/PC specs
- When the PDF shows incorrect data (approval status, scores, etc.)
- When improving PDF formatting or layout
- When adding new fields to existing PDF reports

## This Project's PDF Approach
Based on the codebase, PDFs are generated from Jinja2 HTML templates rendered then converted to PDF. Common patterns:

### Pattern 1: HTML Template → PDF (most likely used here)
```python
from jinja2 import Environment, FileSystemLoader
import weasyprint  # or pdfkit

def generate_agent_pdf(agent: dict, output_path: str):
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('report.html')
    
    # Render the HTML with agent data
    html = template.render(
        agent=agent,
        approved=agent.get('is_approved', False),  # ← watch the field name!
        approval_reason=agent.get('approval_reason', ''),
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M')
    )
    
    # Convert to PDF
    weasyprint.HTML(string=html).write_pdf(output_path)
```

### Common Bug: Wrong Field Names
The most frequent PDF bug is passing the wrong field name to the template:
```python
# BUG: template expects `approved` but you pass `spec_approved`
template.render(spec_approved=True)  # ❌ - template gets None/False
template.render(approved=True)        # ✅ - correct field name

# Always add debug logging before PDF generation:
logger.debug(f"PDF data: approved={agent.get('is_approved')}, reason={agent.get('reason')}")
```

### Pattern 2: ReportLab (direct PDF creation)
```python
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def create_report(output_path: str, data: dict):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 80, f"Agent Report: {data['name']}")
    
    status = "APPROVED ✓" if data['approved'] else "NOT APPROVED ✗"
    color = (0, 0.6, 0) if data['approved'] else (0.8, 0, 0)
    c.setFillColorRGB(*color)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 120, status)
    
    c.save()
```

## Debugging PDF Issues

### Issue: Wrong approval status displayed
```python
# Add this BEFORE generating PDF to see what data is being passed
import json
logger.debug("PDF input data: " + json.dumps({
    "agent_id": agent_id,
    "is_approved": agent.get('is_approved'),
    "approved": agent.get('approved'),
    "spec_approved": agent.get('spec_approved'),
}, indent=2))
```

### Issue: Empty fields in PDF
- The template variable name doesn't match the data key passed to `template.render()`
- Check: `template.render(agent=agent)` — then in template use `{{ agent.field }}`
- Check: `template.render(field=value)` — then in template use `{{ field }}`

### Issue: PDF not updating after fix
- Hard-reload: delete cached `.pdf` files in output directory
- If using browser preview, force-refresh with Ctrl+Shift+R

## HTML Template for PDF (Best Practices)
```html
<!-- report.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; font-size: 11pt; }
        .approved { color: #166534; background: #dcfce7; padding: 8px 16px; }
        .rejected { color: #991b1b; background: #fee2e2; padding: 8px 16px; }
    </style>
</head>
<body>
    <h1>Agent Report: {{ agent.name }}</h1>
    
    {% if approved %}
    <div class="approved">✓ PC Specifications: APPROVED</div>
    {% else %}
    <div class="rejected">✗ PC Specifications: NOT APPROVED</div>
    <p>Reason: {{ approval_reason }}</p>
    {% endif %}
</body>
</html>
```

## Installation
```powershell
# WeasyPrint (HTML to PDF)
pip install weasyprint

# pdfkit (wkhtmltopdf wrapper - requires wkhtmltopdf installed)
pip install pdfkit

# ReportLab (programmatic PDF)
pip install reportlab
```
