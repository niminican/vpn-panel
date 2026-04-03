#!/usr/bin/env python3
"""Generate PDF documents from markdown files for VPN Panel."""

import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white, gray
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    HRFlowable, KeepTogether, ListFlowable, ListItem, Preformatted
)
from reportlab.lib import colors


def create_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='DocTitle',
        parent=styles['Title'],
        fontSize=28,
        spaceAfter=6*mm,
        textColor=HexColor('#1a365d'),
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name='DocSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12*mm,
        textColor=HexColor('#4a5568'),
        alignment=TA_CENTER,
    ))

    styles.add(ParagraphStyle(
        name='H1',
        parent=styles['Heading1'],
        fontSize=20,
        spaceBefore=10*mm,
        spaceAfter=4*mm,
        textColor=HexColor('#1a365d'),
        borderWidth=0,
        borderPadding=0,
        borderColor=HexColor('#3182ce'),
    ))

    styles.add(ParagraphStyle(
        name='H2',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=7*mm,
        spaceAfter=3*mm,
        textColor=HexColor('#2c5282'),
    ))

    styles.add(ParagraphStyle(
        name='H3',
        parent=styles['Heading3'],
        fontSize=13,
        spaceBefore=5*mm,
        spaceAfter=2*mm,
        textColor=HexColor('#2b6cb0'),
    ))

    styles.add(ParagraphStyle(
        name='H4',
        parent=styles['Heading4'],
        fontSize=11,
        spaceBefore=4*mm,
        spaceAfter=2*mm,
        textColor=HexColor('#3182ce'),
    ))

    styles.add(ParagraphStyle(
        name='BodyText2',
        parent=styles['Normal'],
        fontSize=10,
        leading=15,
        spaceAfter=3*mm,
        alignment=TA_JUSTIFY,
    ))

    styles.add(ParagraphStyle(
        name='BulletItem',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=8*mm,
        spaceAfter=1.5*mm,
        bulletIndent=3*mm,
    ))

    styles.add(ParagraphStyle(
        name='CodeBlock',
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        leftIndent=5*mm,
        rightIndent=5*mm,
        spaceBefore=2*mm,
        spaceAfter=2*mm,
        backColor=HexColor('#f7fafc'),
        borderWidth=0.5,
        borderColor=HexColor('#e2e8f0'),
        borderPadding=6,
        textColor=HexColor('#2d3748'),
    ))

    styles.add(ParagraphStyle(
        name='NoteText',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        leftIndent=5*mm,
        rightIndent=5*mm,
        spaceBefore=2*mm,
        spaceAfter=3*mm,
        backColor=HexColor('#ebf8ff'),
        borderWidth=0.5,
        borderColor=HexColor('#3182ce'),
        borderPadding=6,
        textColor=HexColor('#2c5282'),
    ))

    styles.add(ParagraphStyle(
        name='TableCell',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=HexColor('#2d3748'),
    ))

    styles.add(ParagraphStyle(
        name='TableHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=white,
    ))

    styles.add(ParagraphStyle(
        name='Footer',
        fontName='Helvetica',
        fontSize=8,
        textColor=HexColor('#a0aec0'),
        alignment=TA_CENTER,
    ))

    return styles


def escape_html(text):
    """Escape HTML special chars for reportlab Paragraph."""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def process_inline(text):
    """Process inline markdown: bold, italic, code, links."""
    # Code spans first (before other processing)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" size="9" color="#c53030">\1</font>', text)
    # Bold + italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    # Links
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'<u>\1</u>', text)
    return text


def parse_markdown_table(lines):
    """Parse markdown table lines into header and rows."""
    if len(lines) < 2:
        return None, None
    header = [cell.strip() for cell in lines[0].strip('|').split('|')]
    rows = []
    for line in lines[2:]:  # Skip separator
        if '|' in line:
            row = [cell.strip() for cell in line.strip('|').split('|')]
            rows.append(row)
    return header, rows


def build_table(header, rows, styles):
    """Build a reportlab Table from parsed markdown table data."""
    table_data = []
    # Header
    header_cells = [Paragraph(process_inline(h), styles['TableHeader']) for h in header]
    table_data.append(header_cells)
    # Rows
    for row in rows:
        row_cells = [Paragraph(process_inline(cell), styles['TableCell']) for cell in row]
        table_data.append(row_cells)

    num_cols = len(header)
    col_width = (170*mm) / num_cols

    t = Table(table_data, colWidths=[col_width]*num_cols)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2b6cb0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#f7fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def md_to_flowables(md_text, styles):
    """Convert markdown text to a list of reportlab flowables."""
    flowables = []
    lines = md_text.split('\n')
    i = 0
    in_code_block = False
    code_lines = []

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                code_text = escape_html('\n'.join(code_lines))
                flowables.append(Preformatted(code_text, styles['CodeBlock']))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Horizontal rules
        if stripped == '---' or stripped == '***':
            flowables.append(Spacer(1, 3*mm))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#e2e8f0')))
            flowables.append(Spacer(1, 3*mm))
            i += 1
            continue

        # Headers
        if stripped.startswith('####'):
            text = process_inline(stripped.lstrip('#').strip())
            flowables.append(Paragraph(text, styles['H4']))
            i += 1
            continue
        if stripped.startswith('###'):
            text = process_inline(stripped.lstrip('#').strip())
            flowables.append(Paragraph(text, styles['H3']))
            i += 1
            continue
        if stripped.startswith('##'):
            text = process_inline(stripped.lstrip('#').strip())
            flowables.append(Paragraph(text, styles['H2']))
            i += 1
            continue
        if stripped.startswith('# '):
            text = process_inline(stripped.lstrip('#').strip())
            flowables.append(Paragraph(text, styles['H1']))
            i += 1
            continue

        # Tables
        if '|' in stripped and i + 1 < len(lines) and re.match(r'^\s*\|[\s\-:|]+\|', lines[i+1].strip()):
            table_lines = []
            while i < len(lines) and '|' in lines[i]:
                table_lines.append(lines[i])
                i += 1
            header, rows = parse_markdown_table(table_lines)
            if header and rows:
                flowables.append(Spacer(1, 2*mm))
                flowables.append(build_table(header, rows, styles))
                flowables.append(Spacer(1, 2*mm))
            continue

        # Note/Important
        if stripped.startswith('**Note**:') or stripped.startswith('**Important**:'):
            text = process_inline(stripped)
            flowables.append(Paragraph(text, styles['NoteText']))
            i += 1
            continue

        # Bullet points
        if stripped.startswith('- ') or stripped.startswith('* '):
            text = process_inline(stripped[2:])
            flowables.append(Paragraph(f"<bullet>&bull;</bullet> {text}", styles['BulletItem']))
            i += 1
            continue

        # Numbered list
        m = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if m:
            num = m.group(1)
            text = process_inline(m.group(2))
            flowables.append(Paragraph(f"<bullet>{num}.</bullet> {text}", styles['BulletItem']))
            i += 1
            continue

        # Sub-bullet (indented)
        if line.startswith('  - ') or line.startswith('   - '):
            text = process_inline(stripped[2:])
            sub_style = ParagraphStyle(
                'SubBullet', parent=styles['BulletItem'],
                leftIndent=14*mm, bulletIndent=9*mm
            )
            flowables.append(Paragraph(f"<bullet>-</bullet> {text}", sub_style))
            i += 1
            continue

        # Italicized line (like *Super Admin only*)
        if stripped.startswith('*') and stripped.endswith('*') and not stripped.startswith('**'):
            text = stripped.strip('*')
            flowables.append(Paragraph(f"<i>{text}</i>", styles['BodyText2']))
            i += 1
            continue

        # Regular paragraph
        text = process_inline(stripped)
        flowables.append(Paragraph(text, styles['BodyText2']))
        i += 1

    return flowables


def add_page_number(canvas, doc):
    """Add page number footer."""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(HexColor('#a0aec0'))
    canvas.drawCentredString(A4[0]/2, 15*mm, f"Page {doc.page}")
    canvas.restoreState()


def add_cover_footer(canvas, doc):
    """Cover page - no page number."""
    pass


def generate_user_guide_pdf():
    """Generate the User Guide PDF."""
    output_path = "/Users/nimini/Projects/VPN Panel/docs/VPN-Panel-User-Guide-v1.2.0.pdf"
    styles = create_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=25*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
    )

    story = []

    # Cover page
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("VPN Panel", styles['DocTitle']))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("User Guide", ParagraphStyle(
        'CoverSubtitle', parent=styles['DocTitle'], fontSize=22, textColor=HexColor('#3182ce')
    )))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="60%", thickness=2, color=HexColor('#3182ce')))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("Version 1.2.0", styles['DocSubtitle']))
    story.append(Paragraph("April 2026", styles['DocSubtitle']))
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph(
        "Complete guide for installation, configuration, and administration of VPN Panel - "
        "a web-based WireGuard VPN management system with multi-admin RBAC, "
        "bandwidth control, and comprehensive monitoring.",
        ParagraphStyle('CoverDesc', parent=styles['BodyText2'], fontSize=11, alignment=TA_CENTER,
                       textColor=HexColor('#4a5568'))
    ))
    story.append(PageBreak())

    # Read and convert markdown
    with open("/Users/nimini/Projects/VPN Panel/docs/user-guide.md", "r") as f:
        md_content = f.read()

    # Skip the first "# VPN Panel - User Guide" heading (we have our own cover)
    md_content = re.sub(r'^# VPN Panel - User Guide\s*\n', '', md_content)

    # Convert to flowables
    flowables = md_to_flowables(md_content, styles)
    story.extend(flowables)

    doc.build(story, onFirstPage=add_cover_footer, onLaterPages=add_page_number)
    print(f"User Guide PDF generated: {output_path}")
    return output_path


def generate_changelog_pdf():
    """Generate the Changelog PDF."""
    output_path = "/Users/nimini/Projects/VPN Panel/docs/VPN-Panel-Changelog-v1.2.0.pdf"
    styles = create_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=25*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
    )

    story = []

    # Cover page
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("VPN Panel", styles['DocTitle']))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Changelog", ParagraphStyle(
        'CoverSubtitle', parent=styles['DocTitle'], fontSize=22, textColor=HexColor('#3182ce')
    )))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="60%", thickness=2, color=HexColor('#3182ce')))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("Version History: 1.0.0 - 1.2.0", styles['DocSubtitle']))
    story.append(Paragraph("April 2026", styles['DocSubtitle']))
    story.append(PageBreak())

    # Read and convert markdown
    with open("/Users/nimini/Projects/VPN Panel/CHANGELOG.md", "r") as f:
        md_content = f.read()

    # Skip the first "# Changelog" heading
    md_content = re.sub(r'^# Changelog\s*\n', '', md_content)

    flowables = md_to_flowables(md_content, styles)
    story.extend(flowables)

    doc.build(story, onFirstPage=add_cover_footer, onLaterPages=add_page_number)
    print(f"Changelog PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    p1 = generate_user_guide_pdf()
    p2 = generate_changelog_pdf()
    print(f"\nDone! PDFs saved to:")
    print(f"  1. {p1}")
    print(f"  2. {p2}")
