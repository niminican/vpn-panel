#!/usr/bin/env python3
"""Generate v2.0 PDF documents from markdown files."""
import re
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    Preformatted, KeepTogether,
)
from reportlab.lib import colors


def create_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('DocTitle', parent=styles['Title'], fontSize=28, spaceAfter=6*mm, textColor=HexColor('#1a365d'), alignment=TA_CENTER))
    styles.add(ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontSize=14, spaceAfter=12*mm, textColor=HexColor('#4a5568'), alignment=TA_CENTER))
    styles.add(ParagraphStyle('SectionH1', parent=styles['Heading1'], fontSize=20, spaceBefore=8*mm, spaceAfter=4*mm, textColor=HexColor('#1a365d')))
    styles.add(ParagraphStyle('SectionH2', parent=styles['Heading2'], fontSize=16, spaceBefore=6*mm, spaceAfter=3*mm, textColor=HexColor('#2d3748')))
    styles.add(ParagraphStyle('SectionH3', parent=styles['Heading3'], fontSize=13, spaceBefore=4*mm, spaceAfter=2*mm, textColor=HexColor('#4a5568')))
    styles.add(ParagraphStyle('BodyText2', parent=styles['Normal'], fontSize=10, spaceAfter=3*mm, leading=14))
    styles.add(ParagraphStyle('CodeBlock', fontName='Courier', fontSize=8, leading=10, spaceAfter=3*mm, backColor=HexColor('#f7fafc'), leftIndent=10, rightIndent=10))
    styles.add(ParagraphStyle('TableCell', parent=styles['Normal'], fontSize=9, leading=12))
    return styles


def md_to_flowables(md_text, styles):
    """Convert markdown to reportlab flowables."""
    elements = []
    lines = md_text.split('\n')
    i = 0
    in_code = False
    code_lines = []

    while i < len(lines):
        line = lines[i]

        # Code block
        if line.strip().startswith('```'):
            if in_code:
                code_text = '\n'.join(code_lines)
                elements.append(Preformatted(code_text, styles['CodeBlock']))
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Headers
        if stripped.startswith('# '):
            elements.append(Paragraph(stripped[2:], styles['DocTitle']))
        elif stripped.startswith('## '):
            elements.append(Paragraph(stripped[3:], styles['SectionH1']))
        elif stripped.startswith('### '):
            elements.append(Paragraph(stripped[4:], styles['SectionH2']))
        elif stripped.startswith('#### '):
            elements.append(Paragraph(stripped[5:], styles['SectionH3']))

        # Table
        elif stripped.startswith('|') and '|' in stripped[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = lines[i].strip()
                if not row.startswith('|--') and not row.startswith('| --'):
                    cells = [c.strip() for c in row.split('|')[1:-1]]
                    table_lines.append(cells)
                i += 1
            if table_lines:
                # Ensure all rows have same column count
                max_cols = max(len(r) for r in table_lines)
                for row in table_lines:
                    while len(row) < max_cols:
                        row.append('')
                table_data = [[Paragraph(c, styles['TableCell']) for c in row] for row in table_lines]
                t = Table(table_data, repeatRows=1)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#edf2f7')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#2d3748')),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                elements.append(t)
                elements.append(Spacer(1, 3*mm))
            continue

        # List items
        elif stripped.startswith('- ') or stripped.startswith('* '):
            text = stripped[2:]
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'`(.+?)`', r'<font face="Courier" size="9">\1</font>', text)
            elements.append(Paragraph(f"&bull; {text}", styles['BodyText2']))

        # Numbered list
        elif re.match(r'^\d+\. ', stripped):
            text = re.sub(r'^\d+\. ', '', stripped)
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'`(.+?)`', r'<font face="Courier" size="9">\1</font>', text)
            elements.append(Paragraph(text, styles['BodyText2']))

        # Normal paragraph
        elif stripped:
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', stripped)
            text = re.sub(r'`(.+?)`', r'<font face="Courier" size="9">\1</font>', text)
            elements.append(Paragraph(text, styles['BodyText2']))

        i += 1

    return elements


def generate_pdf(md_path, pdf_path, subtitle=""):
    styles = create_styles()
    md_text = Path(md_path).read_text()
    elements = md_to_flowables(md_text, styles)

    if subtitle:
        elements.insert(1, Paragraph(subtitle, styles['DocSubtitle']))

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                           topMargin=20*mm, bottomMargin=20*mm,
                           leftMargin=20*mm, rightMargin=20*mm)
    doc.build(elements)
    print(f"Generated: {pdf_path}")


if __name__ == "__main__":
    docs_dir = Path(__file__).parent

    generate_pdf(
        docs_dir / "architecture-v2.md",
        docs_dir / "MultiPanel-Architecture-v2.0.pdf",
        "System Architecture Documentation"
    )
    generate_pdf(
        docs_dir / "install-guide-v2.md",
        docs_dir / "MultiPanel-Install-Guide-v2.0.pdf",
        "Installation & Configuration Guide"
    )
    generate_pdf(
        docs_dir / "user-guide-v2.md",
        docs_dir / "MultiPanel-User-Guide-v2.0.pdf",
        "Administrator User Guide"
    )
    print("\nAll PDFs generated successfully!")
