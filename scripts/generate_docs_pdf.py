#!/usr/bin/env python3
"""Generate UpMyRank Technical Documentation PDF"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import os, tempfile

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                  TableStyle, Image as RLImage, HRFlowable, PageBreak,
                                  KeepTogether)
from reportlab.pdfgen import canvas as rl_canvas

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
TMPDIR = tempfile.mkdtemp()
OUTPUT = '/Users/ishansrivastava/Desktop/upmyrank/docs/upmyrank_technical_docs.pdf'

NAVY   = '#1E3A5F'
BLUE   = '#3B82F6'
GREEN  = '#10B981'
AMBER  = '#F59E0B'
RED    = '#EF4444'
PURPLE = '#8B5CF6'
LIGHT_BG = '#F8FAFC'
BORDER   = '#E2E8F0'
BODY     = '#1E293B'
META     = '#64748B'

# ─────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────
styles = getSampleStyleSheet()

def add_style(name, **kwargs):
    if name in styles:
        return
    styles.add(ParagraphStyle(name, **kwargs))

add_style('H1', fontName='Helvetica-Bold', fontSize=20, textColor=colors.HexColor(NAVY),
          spaceBefore=24, spaceAfter=8)
add_style('H2', fontName='Helvetica-Bold', fontSize=14, textColor=colors.HexColor(NAVY),
          spaceBefore=18, spaceAfter=6)
add_style('H3', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor(BLUE),
          spaceBefore=12, spaceAfter=4)
add_style('Body', fontName='Helvetica', fontSize=10, textColor=colors.HexColor(BODY),
          leading=15, spaceAfter=8, alignment=TA_JUSTIFY)
add_style('BodyLeft', fontName='Helvetica', fontSize=10, textColor=colors.HexColor(BODY),
          leading=15, spaceAfter=6, alignment=TA_LEFT)
add_style('Code', fontName='Courier', fontSize=8.5, textColor=colors.HexColor('#1E293B'),
          backColor=colors.HexColor('#F1F5F9'), leftIndent=12, rightIndent=12,
          spaceBefore=4, spaceAfter=4, borderPadding=6)
add_style('Caption', fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor(META),
          alignment=TA_CENTER, spaceBefore=3)
add_style('Bullet', fontName='Helvetica', fontSize=10, textColor=colors.HexColor(BODY),
          leading=14, leftIndent=18, spaceAfter=4, bulletIndent=8)
add_style('SmallMeta', fontName='Helvetica', fontSize=8, textColor=colors.HexColor(META),
          leading=11, spaceAfter=2)
add_style('CoverTitle', fontName='Helvetica-Bold', fontSize=36, textColor=colors.white,
          alignment=TA_CENTER)
add_style('TableCell', fontName='Helvetica', fontSize=9, textColor=colors.HexColor(BODY),
          leading=12, leftIndent=4)
add_style('TableCellBold', fontName='Helvetica-Bold', fontSize=9,
          textColor=colors.HexColor(BODY), leading=12, leftIndent=4)
add_style('RuleNum', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor(RED),
          leading=14)

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def section_header(title, story):
    story.append(HRFlowable(width='100%', thickness=3, color=colors.HexColor(BLUE),
                             spaceAfter=4, spaceBefore=16))
    story.append(Paragraph(title, styles['H1']))
    story.append(Spacer(1, 6))


def make_table(headers, rows, col_widths=None, accent=NAVY):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths)
    row_colors = []
    for i in range(1, len(data)):
        bg = colors.HexColor(LIGHT_BG) if i % 2 == 1 else colors.white
        row_colors.append(('BACKGROUND', (0, i), (-1, i), bg))
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(accent)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor(BORDER)),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('WORDWRAP', (0, 0), (-1, -1), True),
    ] + row_colors))
    return t


def bullet(text):
    return Paragraph(f'• {text}', styles['Bullet'])


def save_fig(name, fig):
    path = os.path.join(TMPDIR, f'{name}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def img(path, width=6.0 * inch, max_height=None):
    """Create an RLImage that preserves aspect ratio and fits within page height."""
    from PIL import Image as PILImage
    try:
        with PILImage.open(path) as pil_im:
            orig_w, orig_h = pil_im.size
        aspect = orig_h / orig_w
        height = width * aspect
        # Never exceed max_height (default: 5.5 inches for safety)
        limit = max_height or (5.5 * inch)
        if height > limit:
            height = limit
            width = height / aspect
        im = RLImage(path, width=width, height=height)
    except Exception:
        im = RLImage(path, width=width)
    im.hAlign = 'CENTER'
    return im


# ─────────────────────────────────────────
# COVER PAGE (canvas callback)
# ─────────────────────────────────────────
def build_cover(c, doc):
    w, h = doc.pagesize
    # Dark navy top stripe (55% of page)
    c.setFillColor(colors.HexColor(NAVY))
    c.rect(0, h * 0.45, w, h * 0.55, fill=1, stroke=0)
    # Accent bar
    c.setFillColor(colors.HexColor(BLUE))
    c.rect(0, h * 0.445, w, 6, fill=1, stroke=0)
    # Title
    c.setFont('Helvetica-Bold', 42)
    c.setFillColor(colors.white)
    c.drawCentredString(w / 2, h * 0.73, 'UpMyRank')
    # Subtitle
    c.setFont('Helvetica', 17)
    c.setFillColor(colors.HexColor('#93C5FD'))
    c.drawCentredString(w / 2, h * 0.67, 'Complete Technical Documentation')
    c.setFont('Helvetica', 13)
    c.drawCentredString(w / 2, h * 0.63, 'AI-Powered JEE/NEET Tutoring Platform')
    # Tag line
    c.setFont('Helvetica', 11)
    c.setFillColor(colors.HexColor(BODY))
    c.drawCentredString(w / 2, h * 0.39, 'Architecture · Codebase · Design Philosophy · Build Journey')
    # Version line
    c.setFont('Helvetica', 9)
    c.setFillColor(colors.HexColor(META))
    c.drawCentredString(w / 2, h * 0.33, 'April 14, 2026  ·  Version 1.0  ·  Internal Engineering Reference')
    # Bottom bar
    c.setFillColor(colors.HexColor(NAVY))
    c.rect(0, 0, w, 50, fill=1, stroke=0)
    c.setFont('Helvetica', 8)
    c.setFillColor(colors.HexColor('#64748B'))
    c.drawCentredString(w / 2, 20, 'CONFIDENTIAL — Internal Use Only')


# ─────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────
def footer(c, doc):
    c.saveState()
    c.setFont('Helvetica', 8)
    c.setFillColor(colors.HexColor(META))
    c.drawString(72, 30, 'UpMyRank — Technical Documentation')
    c.drawRightString(letter[0] - 72, 30, f'Page {doc.page}')
    c.setStrokeColor(colors.HexColor(BORDER))
    c.setLineWidth(0.5)
    c.line(72, 42, letter[0] - 72, 42)
    c.restoreState()


# ─────────────────────────────────────────
# FLOW DIAGRAMS (matplotlib)
# ─────────────────────────────────────────
def make_startup_flow():
    steps = [
        ('FastAPI Lifespan Start', GREEN, 'oval'),
        ('Init asyncpg DB Pool', BLUE, 'rect'),
        ('Warm EmbeddingService', BLUE, 'rect'),
        ('Init Retriever', BLUE, 'rect'),
        ('Init OpenAI AsyncClient', BLUE, 'rect'),
        ('Init VerificationPipeline', BLUE, 'rect'),
        ('Init SocraticEngine', NAVY, 'rect'),
        ('Server Ready → yield', GREEN, 'oval'),
    ]
    fig, ax = plt.subplots(figsize=(5, 8))
    ax.set_xlim(0, 4)
    ax.set_ylim(-0.5, len(steps) * 1.1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    for i, (label, color, shape) in enumerate(steps):
        y = (len(steps) - 1 - i) * 1.05
        if shape == 'oval':
            el = mpatches.Ellipse((2, y + 0.25), 3.0, 0.42, facecolor=color, edgecolor='white', linewidth=1.5)
            ax.add_patch(el)
        else:
            rect = FancyBboxPatch((0.5, y + 0.05), 3.0, 0.38, boxstyle='round,pad=0.05',
                                   facecolor=color, edgecolor='white', linewidth=1.2)
            ax.add_patch(rect)
        ax.text(2, y + 0.25, label, ha='center', va='center', fontsize=8.5,
                color='white', fontweight='bold')
        if i < len(steps) - 1:
            ax.annotate('', xy=(2, y + 0.05), xytext=(2, y - 0.42),
                        arrowprops=dict(arrowstyle='->', color=META, lw=1.4))
    return save_fig('startup_flow', fig)


def make_socratic_flow():
    nodes = [
        (2, 10.5, 'Student Submits Question', BLUE, 'oval'),
        (2, 9.2, 'Intent Classification\n(gpt-4o-mini)', BLUE, 'rect'),
        (0.5, 7.8, 'Conversational?', AMBER, 'diamond'),
        (0.5, 6.5, 'Explanation\nRequest?', AMBER, 'diamond'),
        (2, 5.2, 'In Scope?', AMBER, 'diamond'),
        (2, 3.9, 'hint_level >= 3?', RED, 'diamond'),
        (2, 2.7, 'Run Agentic RAG', BLUE, 'rect'),
        (2, 1.8, 'Build System Prompt', BLUE, 'rect'),
        (2, 0.9, 'Check Misconceptions', AMBER, 'rect'),
        (2, 0.0, 'Stream via gpt-4.1-mini', NAVY, 'rect'),
    ]
    side_nodes = [
        (4.5, 7.8, 'Conversational\nReply', GREEN, 'oval'),
        (4.5, 6.5, 'Direct\nExplanation', GREEN, 'oval'),
        (4.5, 5.2, 'Polite\nRejection', RED, 'oval'),
        (4.5, 3.9, 'FORCED_ATTEMPT\nContext Starvation', RED, 'oval'),
    ]
    fig, ax = plt.subplots(figsize=(7, 12))
    ax.set_xlim(-0.5, 6.5)
    ax.set_ylim(-0.8, 11.5)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    def draw_node(x, y, label, color, shape):
        if shape == 'oval':
            el = mpatches.Ellipse((x, y), 2.6, 0.52, facecolor=color, edgecolor='white', linewidth=1.2)
            ax.add_patch(el)
        elif shape == 'diamond':
            dx, dy = 1.2, 0.3
            diamond = plt.Polygon([(x, y+dy),(x+dx, y),(x, y-dy),(x-dx, y)], closed=True,
                                   facecolor=color, edgecolor='white', linewidth=1.2)
            ax.add_patch(diamond)
        else:
            rect = FancyBboxPatch((x-1.3, y-0.23), 2.6, 0.46, boxstyle='round,pad=0.04',
                                   facecolor=color, edgecolor='white', linewidth=1.2)
            ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=7.5, color='white', fontweight='bold',
                multialignment='center')

    for (x, y, label, color, shape) in nodes:
        draw_node(x, y, label, color, shape)
    for (x, y, label, color, shape) in side_nodes:
        draw_node(x, y, label, color, shape)

    # Main vertical arrows
    arrow_pairs = [
        (2, 10.24, 2, 9.44),
        (2, 8.96, 2, 8.1),
        (2, 7.5, 2, 6.8),
        (2, 6.2, 2, 5.46),
        (2, 4.94, 2, 4.16),
        (2, 3.64, 2, 2.93),
        (2, 2.47, 2, 2.03),
        (2, 1.57, 2, 1.13),
        (2, 0.67, 2, 0.23),
    ]
    for (x1, y1, x2, y2) in arrow_pairs:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color=META, lw=1.2))

    # Side arrows
    ax.annotate('', xy=(3.2, 7.8), xytext=(1.7, 7.8),
                arrowprops=dict(arrowstyle='->', color=AMBER, lw=1.2))
    ax.annotate('', xy=(3.2, 6.5), xytext=(1.7, 6.5),
                arrowprops=dict(arrowstyle='->', color=AMBER, lw=1.2))
    ax.annotate('', xy=(3.2, 5.2), xytext=(3.2, 5.2),
                arrowprops=dict(arrowstyle='->', color=AMBER, lw=1.2))
    ax.annotate('', xy=(3.2, 5.2), xytext=(3.2, 5.2),
                arrowprops=dict(arrowstyle='->', color=AMBER, lw=1.2))

    # Label side branches
    ax.text(3.5, 5.5, 'No', fontsize=7, color=AMBER)
    ax.text(3.5, 6.8, 'Yes', fontsize=7, color=AMBER)
    ax.text(3.5, 8.1, 'Yes', fontsize=7, color=AMBER)
    ax.text(3.5, 4.2, 'Yes', fontsize=7, color=RED)

    # Draw side arrows properly
    for (nx, ny, _, _, _), (sx, sy, _, _, _) in zip(
            [nodes[2], nodes[3], nodes[4], nodes[5]],
            side_nodes):
        ax.annotate('', xy=(sx - 1.3, sy),
                    xytext=(nx + 1.2, ny),
                    arrowprops=dict(arrowstyle='->', color=META, lw=1.1))

    ax.text(2, -0.7, 'Judge Eval Queued (async)', ha='center', fontsize=7.5,
            color=GREEN, style='italic')
    return save_fig('socratic_flow', fig)


def make_rag_flow():
    steps = [
        (3, 9.5, 'User Question + Subject', BLUE, 'oval'),
        (3, 8.3, 'Pre-compute Embedding ONCE\n(text-embedding-3-small)', AMBER, 'rect'),
        (3, 7.1, 'LLM Tool Selection\n(gpt-4o-mini)', BLUE, 'rect'),
        (3, 5.8, 'Level 3? Nuclear Gate', RED, 'diamond'),
        (3, 4.6, 'Parallel asyncio.gather()', GREEN, 'rect'),
    ]
    parallel = [
        (1.0, 3.4, 'search_ncert', BLUE),
        (3.0, 3.4, 'search_jee_problems', BLUE),
        (5.0, 3.4, 'search_concepts', BLUE),
    ]
    fig, ax = plt.subplots(figsize=(7, 11))
    ax.set_xlim(-0.5, 7)
    ax.set_ylim(-0.5, 10.5)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    def draw_node(x, y, label, color, shape):
        if shape == 'oval':
            el = mpatches.Ellipse((x, y), 4.0, 0.52, facecolor=color, edgecolor='white', linewidth=1.2)
            ax.add_patch(el)
        elif shape == 'diamond':
            dx, dy = 1.5, 0.35
            diamond = plt.Polygon([(x, y+dy),(x+dx, y),(x, y-dy),(x-dx, y)], closed=True,
                                   facecolor=color, edgecolor='white', linewidth=1.2)
            ax.add_patch(diamond)
        else:
            rect = FancyBboxPatch((x-2.0, y-0.26), 4.0, 0.52, boxstyle='round,pad=0.04',
                                   facecolor=color, edgecolor='white', linewidth=1.2)
            ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=8, color='white', fontweight='bold',
                multialignment='center')

    for (x, y, label, color, shape) in steps:
        draw_node(x, y, label, color, shape)

    # Parallel nodes
    for (x, y, label, color) in parallel:
        rect = FancyBboxPatch((x-1.1, y-0.24), 2.2, 0.48, boxstyle='round,pad=0.04',
                               facecolor=color, edgecolor='white', linewidth=1.2)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=7.5, color='white', fontweight='bold')

    # Rerank
    rerank_y = 2.2
    rect = FancyBboxPatch((1.0, rerank_y-0.24), 4.0, 0.48, boxstyle='round,pad=0.04',
                           facecolor=NAVY, edgecolor='white', linewidth=1.2)
    ax.add_patch(rect)
    ax.text(3.0, rerank_y, 'rerank_and_select', ha='center', va='center', fontsize=8,
            color='white', fontweight='bold')

    # Context output
    ctx_y = 1.0
    el = mpatches.Ellipse((3, ctx_y), 4.0, 0.48, facecolor=GREEN, edgecolor='white', linewidth=1.2)
    ax.add_patch(el)
    ax.text(3, ctx_y, 'Assemble context_text', ha='center', va='center', fontsize=8,
            color='white', fontweight='bold')

    # Empty context branch
    el2 = mpatches.Ellipse((6.2, 5.8), 1.6, 0.44, facecolor=RED, edgecolor='white', linewidth=1.2)
    ax.add_patch(el2)
    ax.text(6.2, 5.8, 'Empty\nContext', ha='center', va='center', fontsize=7.5, color='white', fontweight='bold')

    # Arrows (main vertical)
    arrow_ys = [(9.24, 8.56), (8.04, 7.36), (6.84, 6.15), (5.45, 4.86)]
    for (y1, y2) in arrow_ys:
        ax.annotate('', xy=(3, y2), xytext=(3, y1),
                    arrowprops=dict(arrowstyle='->', color=META, lw=1.2))

    # From gather to parallel
    for x in [1.0, 3.0, 5.0]:
        ax.annotate('', xy=(x, 3.64), xytext=(3, 4.34),
                    arrowprops=dict(arrowstyle='->', color=META, lw=1.0))
    # From parallel to rerank
    for x in [1.0, 3.0, 5.0]:
        ax.annotate('', xy=(3.0, rerank_y + 0.24), xytext=(x, 3.16),
                    arrowprops=dict(arrowstyle='->', color=META, lw=1.0))
    # Rerank to context
    ax.annotate('', xy=(3, ctx_y + 0.24), xytext=(3, rerank_y - 0.24),
                arrowprops=dict(arrowstyle='->', color=META, lw=1.2))
    # Level 3 branch
    ax.annotate('', xy=(5.4, 5.8), xytext=(4.5, 5.8),
                arrowprops=dict(arrowstyle='->', color=RED, lw=1.2))
    ax.text(4.7, 6.0, 'Yes', fontsize=7.5, color=RED)

    return save_fig('rag_flow', fig)


def make_hint_ladder():
    levels = [
        (0, 'Level 0', 'Socratic Question', BLUE, '1.0'),
        (1, 'Level 1', 'Conceptual Bridge', PURPLE, '0.85'),
        (2, 'Level 2', 'Formula/Method Guide', AMBER, '0.70'),
        (3, 'Level 3', 'FORCED ATTEMPT', RED, '0.55'),
        (4, 'Level 4', 'Full Solution', NAVY, '0.40'),
    ]
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, 5.5)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    for (level, lname, desc, color, alpha_str) in levels:
        y = 4.8 - level
        width = 9.0 - level * 0.8
        xstart = (10 - width) / 2
        rect = FancyBboxPatch((xstart, y - 0.28), width, 0.56,
                               boxstyle='round,pad=0.06',
                               facecolor=color, edgecolor='white', linewidth=1.5,
                               alpha=float(alpha_str))
        ax.add_patch(rect)
        ax.text(5, y, f'{lname}: {desc}', ha='center', va='center',
                fontsize=9.5, color='white', fontweight='bold')

    ax.text(5, -0.3, 'Hint depth increases → more scaffolding revealed', ha='center',
            fontsize=8, color=META, style='italic')
    return save_fig('hint_ladder', fig)


def make_memory_layers():
    layers = [
        ('Hot Context', 'Redis', '48h TTL', GREEN, 'Last 2 session summaries\nupdate_hot_context()'),
        ('Compressed Profile', 'Postgres\nstudent_memory', 'Forever', BLUE, 'Rolling 120-word profile +\npersona_profile JSON'),
        ('Concept Mastery', 'Postgres\nconcept_mastery', 'Forever', NAVY, 'EMA mastery score +\nerror_fingerprint + forgetting_rate'),
    ]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.3, 3.8)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    for i, (name, store, ttl, color, desc) in enumerate(layers):
        y = 2.9 - i
        rect = FancyBboxPatch((0.1, y - 0.28), 9.8, 0.76, boxstyle='round,pad=0.08',
                               facecolor=color, edgecolor='white', linewidth=1.5, alpha=0.88)
        ax.add_patch(rect)
        ax.text(1.0, y + 0.18, name, fontsize=9, color='white', fontweight='bold', va='center')
        ax.text(1.0, y - 0.1, f'{store} · {ttl}', fontsize=7.5, color='#D1FAE5' if color == GREEN else '#BFDBFE', va='center')
        ax.text(5.8, y + 0.04, desc, fontsize=8, color='white', va='center', ha='center', multialignment='center')

    ax.text(5, -0.15, 'Layers stack: each session reads all three, writes to appropriate layer',
            ha='center', fontsize=7.5, color=META, style='italic')
    return save_fig('memory_layers', fig)


def make_ptb_layers():
    layers = [
        ('Customization Layer\n(Global Rules)', NAVY,
         'TUTOR_SYSTEM_PROMPT · CUSTOMIZATION_PROMPT\nAlways applied — independent of student'),
        ('Personalization Layer\n(Student Model)', BLUE,
         'PERSONALIZATION_PROMPT · persona_profile\nAdapts tone, scaffolding, style per student'),
        ('Golden Dataset\n(Truth Control)', GREEN,
         '50 golden triplets · Judge LLM\nMeasures quality, prevents pedagogical drift'),
    ]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.3, 4.2)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    for i, (name, color, desc) in enumerate(layers):
        y = 3.4 - i * 1.25
        rect = FancyBboxPatch((0.2, y - 0.34), 9.6, 0.92, boxstyle='round,pad=0.08',
                               facecolor=color, edgecolor='white', linewidth=1.8)
        ax.add_patch(rect)
        ax.text(2.0, y + 0.2, name, fontsize=10, color='white', fontweight='bold', va='center',
                multialignment='center')
        ax.text(6.0, y + 0.04, desc, fontsize=8.5, color='white', va='center', ha='center',
                multialignment='center')
        ax.text(0.55, y - 0.15, f'Layer {3-i}', fontsize=7.5, color='white', alpha=0.7)

    ax.text(5, -0.18, 'LLM is a composer — the system architecture is the product',
            ha='center', fontsize=8, color=META, style='italic')
    return save_fig('ptb_layers', fig)


def make_e2e_flow():
    steps = [
        '1. Student types question → ChatInput',
        '2. POST /doubt/ask/stream (SSE endpoint)',
        '3. Intent classified: SOCRATIC (gpt-4o-mini)',
        '4. Agentic RAG: embed once → parallel tools → hybrid RRF → top chunks',
        '5. build_context_bundle(): Redis hot + Postgres profile + top 5 weak concepts',
        '6. select_pedagogy() → PedagogyConfig (scaffolding, style, depth)',
        '7. check_for_misconception() vs 30-entry library',
        '8. build_system_prompt(): TUTOR + CUSTOMIZATION + PERSONALIZATION + context',
        '9. gpt-4.1-mini streams token-by-token via SSE',
        '10. LaTeX sanitizer on each chunk → frontend KaTeX render',
        '11. Student resolves → _genome_update_task (EMA mastery update)',
        '12. /session/end → summarize_session() (blocking) → update_hot_context()',
        '13. maybe_compress_profile() (background) + judge eval (background)',
    ]
    fig, ax = plt.subplots(figsize=(7, 9.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.4, len(steps) * 0.75 + 0.4)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    colors_map = [BLUE, BLUE, BLUE, BLUE, GREEN, PURPLE, AMBER, NAVY, NAVY, AMBER, GREEN, BLUE, GREEN]

    for i, (step, color) in enumerate(zip(steps, colors_map)):
        y = (len(steps) - 1 - i) * 0.72
        rect = FancyBboxPatch((0.1, y), 9.8, 0.55, boxstyle='round,pad=0.05',
                               facecolor=color, edgecolor='white', linewidth=1.0, alpha=0.88)
        ax.add_patch(rect)
        ax.text(5.0, y + 0.275, step, ha='center', va='center', fontsize=7.8,
                color='white', fontweight='bold')

    return save_fig('e2e_flow', fig)


# ─────────────────────────────────────────
# SECTION BUILDERS
# ─────────────────────────────────────────
def build_section1(story):
    section_header('1. What Is UpMyRank?', story)
    story.append(Paragraph(
        'UpMyRank is an AI-powered tutoring platform for Indian students preparing for JEE (engineering) '
        'and NEET (medicine) entrance exams. It covers Physics, Chemistry, and Maths at NCERT Class 11 and '
        'Class 12 level. The platform serves students preparing for the most competitive undergraduate '
        'entrance exams in India — approximately 1.5 million students attempt JEE each year.',
        styles['Body']))
    story.append(Paragraph('<b>Core Thesis</b>', styles['H3']))
    story.append(Paragraph(
        'The problem with AI tutoring is not intelligence — it is pedagogy. Most AI tools simply give '
        'students the answer. UpMyRank refuses to do this. Instead, every response is generated through a '
        'Socratic engine that forces the student to think before receiving the next level of assistance. '
        'The system tracks what the student knows, how quickly they forget, and where their misconceptions '
        'lie — then adapts the teaching style accordingly.',
        styles['Body']))
    story.append(Spacer(1, 8))
    headers = ['Principle', 'What It Means', 'Why It Matters']
    rows = [
        ['Pedagogy-first AI',
         'Every response deliberately withholds the answer until the student demonstrates effort',
         'Desirable difficulty is intentional — not a bug'],
        ['Adaptive Memory',
         'Per-student Knowledge Genome tracks mastery via EMA, forgetting curve, and error fingerprints',
         'Student model is the product'],
        ['Measurable Quality',
         '4-dimension LLM judge evaluates every session against golden dataset',
         'Teach better, not just answer faster'],
    ]
    t = make_table(headers, rows, col_widths=[1.5*inch, 2.8*inch, 2.2*inch])
    story.append(t)


def build_section2(story):
    section_header('2. The PTB Educational AI Framework', story)
    story.append(Paragraph(
        'PTB (Python Tutor Bot) is the educational AI framework underlying UpMyRank. It provides a '
        'structured three-layer architecture that separates global rules from per-student adaptation '
        'and from quality measurement. The key insight is that the LLM is not the intelligence — '
        'the architecture is.',
        styles['Body']))
    ptb_path = make_ptb_layers()
    story.append(img(ptb_path, 6.0 * inch))
    story.append(Paragraph('Figure: PTB three-layer architecture', styles['Caption']))
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Layer Details</b>', styles['H3']))
    layers = [
        ('<b>Layer 1 — Customization (Global Rules):</b> TUTOR_SYSTEM_PROMPT + CUSTOMIZATION_PROMPT. '
         'Defines what the AI always does, regardless of which student it is talking to. This is the '
         'global pedagogy contract: always Socratic, never give the answer directly, always cite NCERT.'),
        ('<b>Layer 2 — Personalization (Student Model):</b> PERSONALIZATION_PROMPT + persona_profile. '
         'Adapts tone, scaffolding depth, preferred teaching style, and hint depth based on the '
         'individual student\'s onboarding profile and session history.'),
        ('<b>Layer 3 — Golden Dataset (Truth Control):</b> 50 golden triplets + Judge LLM (gpt-4o-mini '
         'at temperature=0). Measures pedagogical quality on every session and fires pre-deploy '
         'regression gates. Prevents quality drift over time.'),
    ]
    for l in layers:
        story.append(Paragraph(l, styles['BodyLeft']))
        story.append(Spacer(1, 4))
    story.append(Paragraph('<b>Core Philosophy</b>', styles['H3']))
    bullets = [
        'The LLM is a composer, not the source of knowledge. The system architecture is the product.',
        'Optimize for learning gain, not user satisfaction. Desirable difficulty is intentional.',
        'Policy Engine first — always determine HOW to teach before generating a response.',
        'Misconceptions ≠ knowledge gaps. Wrong thinking requires different treatment than wrong answers.',
        'Measure pedagogy, not just accuracy. Judge LLM scores Socratic quality on every response.',
    ]
    for b in bullets:
        story.append(bullet(b))


def build_section3(story):
    section_header('3. The Build Journey — 10 Phases', story)
    story.append(Paragraph(
        'UpMyRank was built in 10 sequential phases, each adding a distinct architectural layer. '
        'The sequence reflects a deliberate strategy: get the Socratic loop right first, '
        'then add memory, then add evaluation, then add personalization.',
        styles['Body']))
    headers = ['Phase', 'What Was Built', 'Key Files']
    rows = [
        ['Phase 0\nFoundation',
         'FastAPI app, asyncpg pool, Supabase Postgres, Docker Redis, base schema',
         'app/main.py\napp/db/database.py\nscripts/setup_db.sql'],
        ['Phase 1\nSocratic Engine',
         'Hint ladder (levels 0–4), intent classification, forced-attempt gate, LaTeX sanitizer',
         'app/services/doubt/engine.py\napp/services/doubt/prompts.py'],
        ['Phase 2\nKnowledge Genome',
         'Per-concept EMA mastery tracking, doubt_blocks, session lifecycle',
         'app/api/doubt.py\napp/api/session.py'],
        ['Phase 3\nAgentic RAG',
         '4-tool agentic retriever, hybrid RRF search, pgvector HNSW index',
         'app/services/rag/agent.py\napp/services/rag/tools.py\napp/services/rag/retriever.py'],
        ['Phase 4\nStudent Memory',
         '3-layer memory (Redis + Postgres + concept mastery), session summarizer',
         'app/services/memory/context.py\napp/services/memory/summarizer.py'],
        ['Phase 5\nPolicy Engine',
         'scaffolding_level inference, PedagogyConfig, subject-specific style overrides',
         'app/services/policy/engine.py'],
        ['Phase 6\nMisconception\nDetection',
         '30-entry library, 1.5× mastery penalty, misconception_detected column',
         'app/services/doubt/misconceptions.py'],
        ['Phase 7\nEval + Judge',
         '4-dimension LLM judge, judge_evaluations table, regression gate, eval dashboard',
         'app/services/eval/judge.py\nscripts/regression_gate.py'],
        ['Phase 8\nOnboarding\n+ Persona',
         '4-step UI onboarding, GPT-4.1-mini persona builder, persona evolution every 5 sessions',
         'app/api/onboarding.py\nfrontend/web/app/onboarding/page.tsx'],
        ['Phase 9\nPerformance',
         'Pre-computed embeddings, parallel tool dispatch, pg_trgm GIN indexes, concept seeding',
         'app/services/rag/agent.py\nscripts/migrate_v14_perf_indexes.sql'],
    ]
    t = make_table(headers, rows, col_widths=[1.1*inch, 2.9*inch, 2.5*inch])
    story.append(t)


def build_section4(story):
    section_header('4. Technology Stack', story)
    story.append(Paragraph(
        'Every technology choice is driven by the educational AI requirements: async-first for '
        'streaming, vector similarity for RAG, EMA for mastery tracking, and no ORM '
        'to keep raw query control for complex pgvector operations.',
        styles['Body']))
    headers = ['Layer', 'Technology', 'Notes']
    rows = [
        ['Backend', 'FastAPI (Python 3.11), asyncpg, Pydantic v2', 'Async-first, no ORM'],
        ['Primary LLM', 'gpt-4.1-mini', 'Socratic responses, hints, solutions, persona builder'],
        ['Classification LLM', 'gpt-4o-mini', 'Intent classification, summarization, memory compression, judge'],
        ['Vision LLM', 'gpt-4o', 'Image extraction only — never used for text generation'],
        ['Vector DB', 'pgvector 0.8.2 on Postgres 16', 'HNSW index, 1536-dim embeddings, cosine distance'],
        ['Embeddings', 'text-embedding-3-small', 'All tables uniform, 1536 dimensions'],
        ['Cache', 'Redis (redis.asyncio)', 'Hot context 48h TTL, semantic cache cosine 0.92'],
        ['Token counting', 'tiktoken cl100k_base', 'Prompt token budgets'],
        ['Frontend', 'Next.js 14, TypeScript, Tailwind, Framer Motion', 'SSR + client components, SSE streaming'],
        ['Package manager', 'Poetry (.venv in-project)', 'Python 3.11.14 from Miniconda'],
        ['Config', 'pydantic-settings, .env', 'DATABASE_URL, OPENAI_API_KEY, REDIS_URL'],
        ['Backend hosting', 'Render.com', 'Auto-deploy from main branch'],
        ['Frontend hosting', 'Vercel', 'Edge CDN, Next.js native'],
        ['DB hosting', 'Supabase (Postgres + RLS)', 'aws-0-us-west-2.pooler.supabase.com'],
    ]
    t = make_table(headers, rows, col_widths=[1.5*inch, 2.3*inch, 2.7*inch])
    story.append(t)


def build_section5(story):
    section_header('5. Backend Architecture', story)
    story.append(Paragraph('<b>Application Startup Sequence</b>', styles['H3']))
    story.append(Paragraph(
        'FastAPI uses a lifespan context manager to initialize all shared services in a '
        'guaranteed order. Every service is stored on app.state so it is accessible to '
        'all route handlers without global singletons.',
        styles['Body']))
    path = make_startup_flow()
    story.append(img(path, 4.0 * inch))
    story.append(Paragraph('Figure: Lifespan startup — services initialized in dependency order', styles['Caption']))
    story.append(Spacer(1, 12))
    story.append(Paragraph('<b>API Routers</b>', styles['H3']))
    headers = ['Router', 'Prefix', 'Key Endpoints']
    rows = [
        ['health', '/health', 'GET /'],
        ['auth', '/auth', 'POST /login, /signup, /refresh'],
        ['onboarding', '/onboarding', 'POST /submit, GET /status'],
        ['admin', '/admin', 'GET /metrics, GET /is_admin, GET /judge-metrics'],
        ['doubt', '/doubt', 'POST /ask/stream, POST /verify'],
        ['feedback', '/feedback', 'POST /response'],
        ['session', '/session', 'POST /start, /end, /resume'],
        ['student', '/student', 'GET /{id}'],
        ['mock', '/mock', 'POST /start, GET /submit'],
        ['taxonomy', '/taxonomy', 'GET /chapters'],
    ]
    t = make_table(headers, rows, col_widths=[1.2*inch, 1.5*inch, 3.8*inch])
    story.append(t)


def build_section6(story):
    section_header('6. The Socratic Engine', story)
    story.append(Paragraph(
        'The Socratic Engine is the heart of UpMyRank. Every student question passes through '
        'this pipeline, which decides what kind of response the student should receive — '
        'and deliberately withholds information until the student demonstrates effort.',
        styles['Body']))
    path = make_socratic_flow()
    story.append(img(path, 5.5 * inch))
    story.append(Paragraph('Figure: Full question-processing pipeline in the Socratic Engine', styles['Caption']))
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Intent Types</b>', styles['H3']))
    headers = ['Intent', 'Trigger', 'Response Path']
    rows = [
        ['CONVERSATIONAL', '"yes", "ok", "thanks", short affirmatives',
         'CONVERSATIONAL_RESPONSE — no session started'],
        ['EXPLANATION', '"explain X", "what is X"',
         'EXPLANATION_PROMPT — direct structured explanation, bypasses Socratic'],
        ['OUT_OF_SCOPE', 'non-Physics/Chem/Maths topics',
         'Polite rejection with subject scope reminder'],
        ['SOCRATIC', 'First question on a concept',
         'Hint Level 0: Socratic question only — no formula, no clue'],
        ['CONTINUATION', 'Follow-up in existing session',
         'get_hint() → escalate hint level based on student progress'],
    ]
    t = make_table(headers, rows, col_widths=[1.4*inch, 2.2*inch, 2.9*inch])
    story.append(t)


def build_section7(story):
    section_header('7. The Hint Ladder', story)
    story.append(Paragraph(
        'The hint ladder is the core of the Socratic method. It has 5 levels (0–4). '
        'The student starts at Level 0 and advances only when they demonstrate genuine effort. '
        'Level 3 is structurally enforced — it is not just a stricter instruction but a '
        'different system prompt with all RAG context removed.',
        styles['Body']))
    path = make_hint_ladder()
    story.append(img(path, 6.0 * inch))
    story.append(Paragraph('Figure: Hint ladder — each level reveals more scaffolding', styles['Caption']))
    story.append(Spacer(1, 10))
    headers = ['Level', 'Name', 'What the AI Does', 'What the Student Must Do']
    rows = [
        ['0', 'Socratic Question',
         'Asks a probing question to activate prior knowledge. No formulas. No clues.',
         'Think. Form a hypothesis. Write something.'],
        ['1', 'Conceptual Bridge',
         'Connects the question to a related concept the student already knows. Still no formula.',
         'Show understanding of the bridge concept.'],
        ['2', 'Formula/Method Guide',
         'Reveals the relevant formula or method structure. No substitution.',
         'Attempt substitution and derive the answer.'],
        ['3', 'FORCED ATTEMPT',
         'Context starved. Prompt swapped. AI: "You have everything — attempt it now."',
         'Write a full attempt. No escape hatch.'],
        ['4', 'Full Solution',
         'Step-by-step worked solution only after genuine attempt documented.',
         'Review and compare against your attempt.'],
    ]
    t = make_table(headers, rows, col_widths=[0.5*inch, 1.2*inch, 2.5*inch, 2.3*inch])
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        '<b>Level 3 Implementation Note:</b> Level 3 is not enforced through instructions alone — '
        'the system prompt is completely swapped to SYSTEM_PROMPT_FORCED_ATTEMPT, all RAG context '
        'is cleared before the LLM call, and intent classification is skipped. This structural '
        'enforcement is necessary because LLMs can ignore instructional constraints under pressure. '
        'Context starvation makes it structurally impossible to give the answer.',
        styles['BodyLeft']))


def build_section8(story):
    section_header('8. Agentic RAG System', story)
    story.append(Paragraph(
        'The Agentic RAG system uses an LLM-driven tool selection loop to retrieve the most '
        'relevant context for each question. Rather than always searching all sources, the agent '
        'decides which combination of tools to use based on the question and subject.',
        styles['Body']))
    path = make_rag_flow()
    story.append(img(path, 5.5 * inch))
    story.append(Paragraph('Figure: Agentic RAG retrieval pipeline', styles['Caption']))
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>The 4 Tools</b>', styles['H3']))
    headers = ['Tool', 'Purpose', 'Search Method']
    rows = [
        ['search_ncert',
         'Find NCERT textbook passages relevant to the question',
         'Hybrid RRF: pgvector cosine + pg_trgm ILIKE, fused with Reciprocal Rank Fusion (k=60)'],
        ['search_jee_problems',
         'Find similar JEE Previous Year Questions',
         'Vector similarity on 1536-dim embeddings, HNSW index'],
        ['search_concepts',
         'Look up concept definitions in the taxonomy',
         'pg_trgm GIN index on subtopic/description'],
        ['rerank_and_select',
         'Select the best chunks from all retrieved results',
         'LLM-guided reranking using precomputed embedding similarity'],
    ]
    t = make_table(headers, rows, col_widths=[1.5*inch, 2.0*inch, 3.0*inch])
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>Hybrid RRF Formula</b>', styles['H3']))
    story.append(Paragraph(
        'Each candidate gets: rrf_score = 1/(k + vector_rank) + 1/(k + text_rank) where k=60. '
        'Vector rank from pgvector cosine distance. Text rank from ILIKE pg_trgm GIN match. '
        'Final top-K selected by descending rrf_score. The RRF fusion approach means neither '
        'pure vector nor pure keyword dominates — exact formula name matches are boosted by '
        'text rank while semantic relevance is captured by vector rank.',
        styles['Body']))
    story.append(Paragraph('<b>Performance Optimizations</b>', styles['H3']))
    headers2 = ['Optimization', 'Before', 'After', 'Improvement']
    rows2 = [
        ['Embedding calls per query',
         '3 separate API calls (~300-700ms each)',
         '1 pre-computed, shared across all tools',
         '~60-70% latency reduction'],
        ['Tool dispatch',
         'Sequential (tool1 → tool2 → tool3)',
         'Parallel asyncio.gather()',
         '~50% reduction for multi-tool steps'],
        ['ILIKE search',
         'Full table scan on 14,384+ rows',
         'pg_trgm GIN index',
         'O(n) → O(log n)'],
        ['Combined P95 latency',
         '~12,677ms',
         'Target <2,000ms',
         '~84% improvement'],
    ]
    t2 = make_table(headers2, rows2, col_widths=[2.0*inch, 1.8*inch, 1.8*inch, 1.0*inch])
    story.append(t2)


def build_section9(story):
    section_header('9. Database Schema', story)
    story.append(Paragraph(
        'The database runs on Postgres 16 hosted on Supabase with pgvector 0.8.2 for '
        'vector similarity search. All 14 tables have Row Level Security (RLS) enabled. '
        'Schema evolves through numbered migration files — never ad-hoc ALTER TABLE.',
        styles['Body']))

    tables_data = [
        {
            'name': 'students',
            'desc': 'One row per registered student. Source of truth for identity, onboarding state, and exam target.',
            'cols': [
                ['id', 'UUID PK', 'Supabase auth.users FK'],
                ['email', 'TEXT UNIQUE', 'Login identifier'],
                ['name', 'TEXT', 'Display name'],
                ['exam_type', 'TEXT', "'JEE' or 'NEET'"],
                ['class_level', 'TEXT', "'11th', '12th', 'dropper'"],
                ['physics_prev_marks', 'SMALLINT', '0-100, from onboarding'],
                ['study_hours_per_day', 'SMALLINT', 'From onboarding'],
                ['exam_date', 'DATE', 'Target exam date'],
                ['onboarding_completed', 'BOOLEAN', 'Gate for app access'],
                ['created_at', 'TIMESTAMPTZ', 'Auto'],
            ]
        },
        {
            'name': 'study_sessions',
            'desc': 'One row per study session. Contains the GPT-compressed summary and topics covered.',
            'cols': [
                ['study_session_id', 'UUID PK', ''],
                ['student_id', 'UUID FK', '→ students.id'],
                ['started_at', 'TIMESTAMPTZ', 'Session start'],
                ['ended_at', 'TIMESTAMPTZ', 'NULL if active'],
                ['doubt_count', 'INT', 'Running count'],
                ['session_summary', 'TEXT', 'GPT-4o-mini compressed summary'],
                ['topics_covered', 'TEXT[]', 'All topics addressed this session'],
            ]
        },
        {
            'name': 'doubt_blocks',
            'desc': 'One row per question asked. Tracks hint progression, misconception detection, and resolution.',
            'cols': [
                ['doubt_block_id', 'UUID PK', ''],
                ['study_session_id', 'UUID FK', ''],
                ['doubt_session_id', 'UUID FK', '→ doubt_sessions.id'],
                ['topic', 'TEXT', 'Question topic string'],
                ['subject', 'TEXT', "'Physics', 'Chemistry', 'Maths'"],
                ['hint_level', 'SMALLINT', '0-4, current depth'],
                ['solved', 'BOOLEAN', 'Student marked resolved'],
                ['misconception_detected', 'BOOLEAN', 'From misconception library check'],
                ['misconception_id', 'TEXT', 'Matched misconception key'],
            ]
        },
        {
            'name': 'knowledge_chunks',
            'desc': '15,069 NCERT passage chunks. Physics (10,505) + Chemistry (3,138) + Maths (1,426).',
            'cols': [
                ['id', 'UUID PK', ''],
                ['content', 'TEXT', 'NCERT passage text (350-token chunks)'],
                ['subject', 'TEXT', "'Physics', 'Chemistry', 'Maths'"],
                ['chapter', 'TEXT', 'Chapter name'],
                ['class_level', 'TEXT', "'11' or '12'"],
                ['chunk_index', 'INT', 'Position within chapter'],
                ['embedding', 'vector(1536)', 'text-embedding-3-small'],
            ]
        },
        {
            'name': 'concept_mastery',
            'desc': 'Per-student per-concept mastery. The Knowledge Genome. Sole writer: _genome_update_task.',
            'cols': [
                ['student_id', 'UUID FK', ''],
                ['concept_id', 'TEXT FK', '→ concepts.id'],
                ['mastery_score', 'FLOAT', 'EMA, 0.0–1.0'],
                ['error_fingerprint', 'JSONB', '{error_type: strength 0.0–1.0}'],
                ['forgetting_rate', 'FLOAT', 'Ebbinghaus decay, 0.1–0.9'],
                ['last_practiced', 'TIMESTAMPTZ', ''],
                ['PRIMARY KEY', '(student_id, concept_id)', ''],
            ]
        },
        {
            'name': 'student_memory',
            'desc': 'Rolling compressed profile + full persona JSON. Evolves every 5 sessions.',
            'cols': [
                ['student_id', 'UUID PK FK', ''],
                ['compressed_profile', 'TEXT', 'GPT-4o-mini rolling profile, ≤120 words'],
                ['persona_profile', 'JSONB', 'Full persona dict (scaffolding_level, style, etc.)'],
                ['persona_profile_updated_at', 'TIMESTAMPTZ', 'Staleness tracking'],
                ['forgetting_rates', 'JSONB', '{concept_id: rate} mirror for fast reads'],
                ['sessions_since_compress', 'INT', 'Trigger: compress every 5 sessions'],
            ]
        },
        {
            'name': 'session_events',
            'desc': 'Per-turn telemetry. Captures scaffolding scores, retrieval quality, and latency.',
            'cols': [
                ['id', 'UUID PK', ''],
                ['doubt_block_id', 'UUID FK', ''],
                ['event_type', 'TEXT', "'hint_requested', 'solved', etc."],
                ['scaffolding_score', 'SMALLINT', '0-2 from Judge LLM'],
                ['retrieval_similarity', 'FLOAT', 'Top chunk cosine similarity'],
                ['response_latency_ms', 'INT', 'End-to-end response time'],
                ['hint_was_useful', 'BOOLEAN', 'Feedback signal'],
            ]
        },
        {
            'name': 'judge_evaluations',
            'desc': '4-dimension judge scores. Populated async after session end.',
            'cols': [
                ['id', 'UUID PK', ''],
                ['pedagogical_score', 'SMALLINT', '0-2 (weight 0.40)'],
                ['factual_score', 'SMALLINT', '0-1 (weight 0.30)'],
                ['context_relevance_score', 'SMALLINT', '0-1 (weight 0.15)'],
                ['hint_appropriateness_score', 'SMALLINT', '0-1 (weight 0.15)'],
                ['overall_score', 'FLOAT', 'Weighted composite 0.0–1.0'],
                ['rationale_json', 'JSONB', 'Per-dimension rationale text'],
            ]
        },
        {
            'name': 'jee_problems',
            'desc': '20 verified JEE PYQs with embeddings for similarity search.',
            'cols': [
                ['id', 'UUID PK', ''],
                ['question', 'TEXT', 'Problem text'],
                ['answer', 'TEXT', 'Correct answer'],
                ['subject', 'TEXT', 'Subject tag'],
                ['year', 'INT', 'JEE year'],
                ['difficulty', 'TEXT', 'easy/medium/hard'],
                ['embedding', 'vector(1536)', 'For similarity search via HNSW'],
            ]
        },
    ]

    for td in tables_data:
        story.append(Paragraph(f'<b>Table: {td["name"]}</b>', styles['H3']))
        story.append(Paragraph(td['desc'], styles['BodyLeft']))
        headers = ['Column', 'Type', 'Notes']
        t = make_table(headers, td['cols'], col_widths=[1.8*inch, 1.6*inch, 3.1*inch])
        story.append(t)
        story.append(Spacer(1, 8))

    story.append(Paragraph('<b>Migration Timeline</b>', styles['H3']))
    headers = ['Migration File', 'What It Added']
    rows = [
        ['setup_db.sql', 'Base schema: students, study_sessions, doubt_blocks, doubt_sessions, knowledge_chunks, concepts, concept_mastery, session_events'],
        ['migrate_v4_memory.sql', 'student_memory table (compressed_profile, persona_profile, forgetting_rates)'],
        ['migrate_v5_persona.sql', 'persona_profile JSONB column on student_memory'],
        ['migrate_v6_misconceptions.sql', 'misconception_detected, misconception_id on doubt_blocks + session_events'],
        ['migrate_v7_eval.sql', 'scaffolding_score, retrieval_similarity, response_latency_ms, hint_was_useful on session_events'],
        ['migrate_v8_onboarding.sql', 'onboarding_completed, class_level, physics_prev_marks, study_hours_per_day, exam_date on students'],
        ['migrate_v9_persona_staleness.sql', 'persona_profile_updated_at on student_memory'],
        ['migrate_v10_rls.sql', 'RLS enabled on all 10 public tables, 10 policies'],
        ['migrate_v11_jee_problems.sql', 'jee_problems table, HNSW index, match_jee_problems() RPC'],
        ['migrate_v12_feedback.sql', 'response_feedback, judge_evaluations, session_metrics tables'],
        ['migrate_v13_subjects.sql', 'chemistry_prev_marks, maths_prev_marks, priority_subject, learning_preference on students'],
        ['migrate_v14_perf_indexes.sql', 'pg_trgm GIN indexes on content/subtopic, btree indexes on subject/chunk_index'],
    ]
    t = make_table(headers, rows, col_widths=[2.4*inch, 4.1*inch])
    story.append(t)


def build_section10(story):
    section_header('10. 3-Layer Student Memory', story)
    story.append(Paragraph(
        'The student memory system uses three layers with different speeds and lifetimes. '
        'Together they give the AI full context without overwhelming token budgets: '
        'hot recent summaries from Redis, compressed profile from Postgres, and '
        'per-concept mastery scores.',
        styles['Body']))
    path = make_memory_layers()
    story.append(img(path, 6.0 * inch))
    story.append(Paragraph('Figure: 3-layer memory architecture', styles['Caption']))
    story.append(Spacer(1, 10))
    headers = ['Layer', 'Storage', 'TTL', 'Written By', 'Read By']
    rows = [
        ['Hot Context', 'Redis', '48 hours',
         'update_hot_context() on session end',
         'build_context_bundle()'],
        ['Compressed Profile', 'Postgres\nstudent_memory', 'Forever',
         'maybe_compress_profile()\nevery 5 sessions',
         'build_context_bundle()'],
        ['Concept Mastery', 'Postgres\nconcept_mastery', 'Forever',
         '_genome_update_task\nin doubt.py (sole writer)',
         'build_context_bundle()\n→ top 5 weakest concepts'],
    ]
    t = make_table(headers, rows, col_widths=[1.2*inch, 1.3*inch, 0.8*inch, 2.0*inch, 1.8*inch])
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>persona_profile JSON Structure</b>', styles['H3']))
    story.append(Paragraph(
        'The persona_profile is a JSONB column on student_memory. It is built during onboarding '
        'and partially rewritten every 5 sessions by maybe_compress_profile(). Structured keys '
        'are preserved via dict merge — only persona_summary is ever fully overwritten.',
        styles['Body']))
    code_text = (
        '{\n'
        '  "scaffolding_level": "HIGH | MEDIUM | LOW",\n'
        '  "preferred_style": "analogy | formula | example | visual",\n'
        '  "common_misconceptions": ["string", ...],\n'
        '  "allowed_hint_depth": 3,\n'
        '  "interaction_depth_score": 0.0,\n'
        '  "learning_velocity": 0.0,\n'
        '  "persona_summary": "3-4 sentence student description"\n'
        '}'
    )
    story.append(Paragraph(code_text.replace('\n', '<br/>').replace(' ', '&nbsp;'), styles['Code']))
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>Persona Evolution (Every 5 Sessions)</b>', styles['H3']))
    pe_bullets = [
        'Onboarding builds the initial persona_profile from survey answers via GPT-4.1-mini',
        'Every 5 sessions: maybe_compress_profile() fires as background task from /session/end',
        'Uses last 10 session summaries + top 10 concept mastery scores as input',
        'Two GPT-4o-mini calls: (1) update compressed_profile paragraph, (2) rewrite persona_summary',
        'Preserves all structured keys (scaffolding_level, preferred_style, etc.) via dict merge — never fully overwrites',
        'persona_profile_updated_at tracks freshness; format_context_for_prompt() adds staleness warning if >15 sessions old',
    ]
    for b in pe_bullets:
        story.append(bullet(b))


def build_section11(story):
    section_header('11. Policy Engine', story)
    story.append(Paragraph(
        'The Policy Engine is a separate architectural layer that runs before every LLM call. '
        'It produces a PedagogyConfig dataclass that determines HOW to teach — '
        'independent of WHAT to teach. Separating these concerns is the key architectural decision '
        'that makes pedagogy deterministic and auditable.',
        styles['Body']))
    story.append(Paragraph('<b>Scaffolding Level Inference</b>', styles['H3']))
    headers = ['avg_mastery Range', 'scaffolding_level', 'Teaching Style']
    rows = [
        ['< 0.4', 'HIGH', 'Explicit, step-by-step, analogies, check-ins after each concept'],
        ['0.4 – 0.7', 'MEDIUM', 'Formula-focused, neutral tone, moderate pacing'],
        ['> 0.7', 'LOW', 'Application problems, high density, direct tone, minimal scaffolding'],
    ]
    t = make_table(headers, rows, col_widths=[1.5*inch, 1.5*inch, 3.5*inch])
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Subject-Specific Overrides</b>', styles['H3']))
    headers2 = ['Subject', 'HIGH', 'MEDIUM', 'LOW', 'Special Rules']
    rows2 = [
        ['Physics', 'conceptual', 'formula', 'application', 'None'],
        ['Chemistry', 'conceptual', 'formula', 'application',
         'HIGH: use_analogies=False\n(equations are the intuition vehicle)'],
        ['Maths', 'conceptual', 'application', 'application',
         'max_concepts -= 1\n(each step needs verification)'],
    ]
    t2 = make_table(headers2, rows2, col_widths=[0.9*inch, 1.0*inch, 1.0*inch, 1.0*inch, 2.6*inch])
    story.append(t2)
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>hint_level Overrides</b>', styles['H3']))
    story.append(bullet('hint_level == 0: always socratic_style = "conceptual" — regardless of scaffolding_level'))
    story.append(bullet('hint_level >= 3: check_in_required = False — forced attempt means no mid-response pacing'))


def build_section12(story):
    section_header('12. Misconception Detection', story)
    story.append(Paragraph(
        'Misconceptions are qualitatively different from knowledge gaps. A student who has never '
        'learned a concept needs teaching. A student with an active misconception needs correction — '
        'often counter-intuitive correction that directly confronts the wrong model. UpMyRank '
        'maintains a 30-entry library and applies a 1.5× mastery penalty when a match is found.',
        styles['Body']))
    headers = ['Field', 'Value']
    rows = [
        ['Library size', '30 entries covering Physics, Chemistry, and Maths'],
        ['Check function', 'check_for_misconception(response, topic, subject) → Misconception|None'],
        ['Penalty', '1.5× mastery penalty applied to affected concept via EMA'],
        ['Storage', 'misconception_detected=TRUE, misconception_id stored on doubt_block'],
        ['Trigger', 'Runs on every AI response before returning to the student'],
    ]
    t = make_table(headers, rows, col_widths=[2.0*inch, 4.5*inch])
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Example Misconceptions</b>', styles['H3']))
    headers2 = ['Subject', 'Misconception', 'Correct Model']
    rows2 = [
        ['Physics (Mechanics)', 'Heavier objects fall faster under gravity',
         'All objects fall at the same rate in absence of air resistance (Galileo)'],
        ['Physics (Electricity)', 'Current is "used up" as it flows through a circuit',
         'Current is conserved; voltage drops across components, not current'],
        ['Chemistry (Acids)', 'Acids always contain oxygen',
         'HCl, HBr, HF contain no oxygen — acidity is defined by H+ donation'],
        ['Chemistry (Bonds)', 'Ionic bonds are stronger than covalent bonds',
         'Depends on the specific compounds; many covalent bonds are stronger'],
        ['Maths (Calculus)', 'Derivatives only measure the slope of straight lines',
         'Derivatives measure instantaneous rate of change — applicable to any differentiable function'],
        ['Maths (Probability)', 'P(A and B) = P(A) × P(B) always',
         'This only holds when A and B are independent; joint probability requires P(A|B)'],
    ]
    t2 = make_table(headers2, rows2, col_widths=[1.4*inch, 2.0*inch, 3.1*inch])
    story.append(t2)


def build_section13(story):
    section_header('13. Judge Evaluation System', story)
    story.append(Paragraph(
        'Every session is scored by a 4-dimension LLM judge (gpt-4o-mini at temperature=0). '
        'The judge fires asynchronously after session end via asyncio.create_task() — it never '
        'blocks the user-facing response. Results power the admin dashboard and the pre-deploy '
        'regression gate.',
        styles['Body']))
    story.append(Paragraph('<b>4-Dimension Scoring Formula</b>', styles['H3']))
    headers = ['Dimension', 'Scale', 'Weight', 'What It Measures']
    rows = [
        ['Pedagogical', '0-2', '0.40 (40%)', 'Socratic quality — did AI withhold answer appropriately?'],
        ['Factual', '0-1', '0.30 (30%)', 'Factual accuracy of the response content'],
        ['Context Relevance', '0-1', '0.15 (15%)', 'Did AI use the RAG context that was provided?'],
        ['Hint Appropriateness', '0-1', '0.15 (15%)', 'Right level of scaffolding for student\'s current state?'],
        ['Overall (composite)', '0.0–1.0', '—', '0.4×(ped/2) + 0.3×fact + 0.15×ctx + 0.15×hint'],
    ]
    t = make_table(headers, rows, col_widths=[1.5*inch, 0.6*inch, 1.0*inch, 3.4*inch])
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Judge Pipeline</b>', styles['H3']))
    pipeline = [
        'Judge fires async from POST /session/end via asyncio.create_task() — never blocks user response',
        'Uses gpt-4o-mini at temperature=0 for deterministic, reproducible scoring',
        'Input: question (truncated to 4000 chars) + AI response (truncated to 4000 chars)',
        'Output: {pedagogical_score, factual_score, context_relevance_score, hint_appropriateness_score, overall_score, rationale_json}',
        'Results stored in judge_evaluations table with FK to both study_session and doubt_session',
        'Admin dashboard aggregates: adherence rate, avg scores, per-topic breakdown, drifting topics (score < 1.5)',
        'Regression gate (scripts/regression_gate.py): exit code 1 if overall_score < 0.6 on golden dataset — blocks deploy',
        'Pedagogy drift report (scripts/pedagogy_drift_report.py): weekly, flags topics with avg score < 1.5',
    ]
    for p in pipeline:
        story.append(bullet(p))
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>Admin Dashboard Metrics</b>', styles['H3']))
    headers2 = ['Metric', 'Endpoint', 'Description']
    rows2 = [
        ['Socratic Adherence Rate', 'GET /admin/metrics', 'Fraction of sessions scoring pedagogical ≥ 1 (out of 2)'],
        ['Avg Retrieval Similarity', 'GET /admin/metrics', 'Mean cosine similarity of top chunk across all sessions'],
        ['Latency P95', 'GET /admin/metrics', '95th percentile response latency in milliseconds'],
        ['Per-Topic Breakdown', 'GET /admin/metrics', 'Average overall score per topic — sorted ascending to surface weak topics'],
        ['Judge Score Trend', 'GET /admin/judge-metrics', 'Time series of overall_score over last N days'],
    ]
    t2 = make_table(headers2, rows2, col_widths=[1.8*inch, 1.5*inch, 3.2*inch])
    story.append(t2)


def build_section14(story):
    section_header('14. Onboarding Flow', story)
    story.append(Paragraph(
        'New students complete a 4-step onboarding flow before accessing the platform. '
        'This is the moment the system\'s first impressions of the student are formed — '
        'the resulting persona_profile drives all subsequent pedagogy decisions until '
        'the session evidence overrides it.',
        styles['Body']))
    headers = ['Step', 'What\'s Collected', 'How It\'s Used']
    rows = [
        ['1: Academic Background',
         'class_level, physics_prev_marks, chemistry_prev_marks, maths_prev_marks',
         'Initial scaffolding_level inference per subject'],
        ['2: Topic Assessment',
         'easy_topics[], hard_topics[] — Physics (16 topics), Chemistry (10), Maths (10) = 36 total',
         'Seeded into concept_mastery with initial mastery scores (easy=0.7, hard=0.2)'],
        ['3: Study Plan',
         'study_hours_per_day, exam_type, exam_date, priority_subject, learning_preference',
         'Study intensity + preferred teaching style (formula/analogy/example/visual)'],
        ['4: Persona Summary',
         '— (display only)',
         'Shows generated persona card (3-4 sentences describing student model)'],
    ]
    t = make_table(headers, rows, col_widths=[1.3*inch, 2.2*inch, 3.0*inch])
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Persona Builder</b>', styles['H3']))
    pb_bullets = [
        'GPT-4.1-mini processes all survey answers and produces the persona_profile JSON',
        'persona_summary: 3-4 sentences covering ability level per subject, hint preference, emotional pattern, teaching style',
        'scaffolding_level derived from weakest-subject marks (lowest of physics/chemistry/maths)',
        'preferred_style: set directly from learning_preference input — explicit student input is authoritative',
        'common_misconceptions: seeded from hard_topics[] based on subject misconception library',
        'allowed_hint_depth: defaults to 3 for first-time students; policy engine can override',
    ]
    for b in pb_bullets:
        story.append(bullet(b))


def build_section15(story):
    section_header('15. Frontend Architecture', story)
    story.append(Paragraph(
        'The frontend is a Next.js 14 application with TypeScript, Tailwind CSS, and Framer Motion. '
        'It uses no Redux — state is managed with local useState and context. '
        'API calls use a custom fetchWithRetry() with exponential backoff and automatic '
        'token refresh on 401 errors.',
        styles['Body']))
    story.append(Paragraph('<b>Pages</b>', styles['H3']))
    headers = ['Page', 'Route', 'Purpose']
    rows = [
        ['Home', '/', 'Dashboard: persona greeting, 3 subject mastery cards, exam countdown, continue session link'],
        ['Auth Login', '/auth/login', 'Supabase auth + onboarding status check → redirects to /onboarding if not done'],
        ['Auth Signup', '/auth/signup', 'Always redirects new signups to /onboarding'],
        ['Onboarding', '/onboarding', '4-step glassmorphic flow: marks → topics → study plan → persona summary card'],
        ['Doubt', '/doubt', 'Main chat UI with SSE streaming, topic lock, subject badge, confidence meter'],
        ['Practice', '/practice', 'Topic-based practice (planned)'],
        ['Mock', '/mock', 'Full mock exam simulation with timer and MCQ interface'],
        ['Progress', '/progress', 'Knowledge Genome mastery visualization per concept'],
        ['Settings', '/settings', '4-tab settings: Profile / My Analytics / System Analytics / Preferences'],
        ['Admin', '/admin', 'System eval dashboard — admin-gated via ADMIN_STUDENT_ID env var'],
    ]
    t = make_table(headers, rows, col_widths=[1.2*inch, 1.3*inch, 4.0*inch])
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Key Components</b>', styles['H3']))
    headers2 = ['Component', 'Purpose']
    rows2 = [
        ['ChatMessage.tsx', 'Renders AI/student messages with LaTeX via KaTeX, badge display, thumbs up/down feedback buttons'],
        ['ChatInput.tsx', 'Input + ConfidenceMeter with AnimatePresence swap; base64 image upload via FileReader (no Supabase storage)'],
        ['Sidebar.tsx', '280px desktop nav; student identity card (avatar + name + exam); TopicTree; Learning Profile section; Framer Motion mobile panel'],
        ['TopicTree.tsx', 'Subject tabs (Phy/Che/Mat); chapter accordion with mastery bar; topic row with Doubt/Practice/Mock icons; /taxonomy + genome concurrent fetch'],
        ['QuickDoubtFAB.tsx', '56px FAB globally mounted; bottom-sheet textarea; navigates to /doubt?q=question; hidden on /doubt /auth /onboarding'],
    ]
    t2 = make_table(headers2, rows2, col_widths=[1.8*inch, 4.7*inch])
    story.append(t2)
    story.append(Spacer(1, 8))
    story.append(Paragraph('<b>SSE Streaming</b>', styles['H3']))
    story.append(Paragraph(
        'The doubt page uses EventSource-equivalent fetch with ReadableStream. Every token is '
        'yielded as {"token": "...", "done": false}. The final event is {"done": true} which '
        'closes the stream. A keepalive {"done": false, "thinking": true} is sent immediately '
        'on continuation requests to prevent Render\'s 30-second proxy timeout from '
        'killing the connection before the LLM call completes.',
        styles['Body']))
    story.append(Paragraph('<b>API Client: fetchWithRetry()</b>', styles['H3']))
    story.append(bullet('Retry delays: 5s / 15s / 30s (covers Render cold start of ~20s)'))
    story.append(bullet('Automatic 401 handling: calls tryRefresh() to get new access token, retries original request'))
    story.append(bullet('If refresh fails: redirect to /auth/login'))
    story.append(bullet('pingBackend(): called on mount of login/signup/onboarding pages to warm Render cold start'))


def build_section16(story):
    section_header('16. Hard Invariants — The Rules', story)
    story.append(Paragraph(
        'These 9 rules are hard invariants. Violating them creates silent bugs — the kind that '
        'corrupt data over time without throwing visible errors. They must never be broken.',
        styles['Body']))
    headers = ['#', 'Rule', 'Why It Matters']
    rows = [
        ['1', '_genome_update_task is the sole mastery writer',
         'A second EMA path creates split-brain mastery — student model becomes inconsistent across sessions'],
        ['2', 'summarize_session() is always awaited on /session/end',
         'Fire-and-forget breaks the blocking requirement; session must end with summary written for next-session context'],
        ['3', 'Redis errors must never propagate',
         'Cache is optional infrastructure — a Redis crash must never take down user-facing flows'],
        ['4', 'Level 3 = context starvation, not just instructions',
         'LLM can ignore instructions under pressure. Structural removal is the only reliable enforcement'],
        ['5', 'gpt-4o is for vision only, never text',
         'Cost and latency reasons; gpt-4.1-mini delivers equivalent Socratic quality for text generation'],
        ['6', 'LaTeX sanitizer runs on every LLM response',
         'Malformed LaTeX breaks the frontend KaTeX renderer for ALL users — never send raw LLM output to client'],
        ['7', 'DB migrations are files in scripts/',
         'Ad-hoc ALTER TABLE creates irreproducible schema state across environments — always use run_migration.sh'],
        ['8', 'Admin gate is ADMIN_STUDENT_ID env var compare',
         'No Supabase RLS role changes needed; simple, auditable, easy to revoke'],
        ['9', 'Persona evolution preserves structured keys',
         'Only persona_summary is rewritten; scaffolding_level and other keys survive via dict merge — never fully overwrite'],
    ]
    t = make_table(headers, rows, col_widths=[0.3*inch, 2.2*inch, 4.0*inch], accent=RED)
    story.append(t)


def build_section17(story):
    section_header('17. Architecture Decisions', story)
    story.append(Paragraph(
        'Every major architectural decision was driven by pedagogical requirements, not convenience. '
        'This section documents what was chosen, what was rejected, and why.',
        styles['Body']))
    headers = ['Decision', 'Chosen', 'Rejected', 'Reason']
    rows = [
        ['Retrieval strategy', 'Agentic RAG (LLM tool selection, MAX_STEPS=3)',
         'Simple vector search',
         'Static retrieval misses subject context; agent routes correctly between NCERT, JEE PYQs, and concepts'],
        ['Search fusion', 'Hybrid RRF (pgvector + pg_trgm, k=60)',
         'Pure vector or pure keyword',
         'Vector alone misses exact formula names; keyword alone misses semantics. RRF fusion handles both'],
        ['Mastery tracking', 'EMA per concept (Exponential Moving Average)',
         'Binary correct/incorrect',
         'EMA captures learning trajectory and forgetting — not just the last result'],
        ['Error fingerprint', 'JSONB {error_type: 0.0-1.0} with decay/reinforce',
         'Simple error list',
         'Strength-based model allows targeted remediation and tracks which errors are fading vs. persisting'],
        ['Pedagogy layer', 'Separate Policy Engine, runs before LLM',
         'Inline prompt instructions',
         'Separation allows deterministic pedagogy decisions that can be audited independent of LLM'],
        ['Level 3 enforcement', 'Structural context removal',
         'Stronger instructions',
         'Instructions alone cannot reliably prevent LLM from giving the answer — architecture must enforce it'],
        ['Session summarizer', 'await summarize_session() (blocking)',
         'asyncio.create_task()',
         'Summary must be written before session ends for next-session context injection to work'],
        ['Persona evolution', 'maybe_compress_profile() every 5 sessions',
         'Real-time update each session',
         'Real-time GPT call per session too expensive; 5-session batching amortizes cost with sufficient freshness'],
        ['Database auth', 'Supabase RLS on all 10 tables',
         'Backend-only auth',
         'Defense in depth; student_id from auth.uid() prevents horizontal data leakage at DB layer'],
        ['Embedding strategy', 'Single embed_single() at start of AgenticRetriever.run()',
         'Embed per-tool call',
         'Eliminates 2 of 3 OpenAI API calls per retrieval; ~60% latency reduction for multi-tool queries'],
        ['Image handling', 'base64 via FileReader.readAsDataURL()',
         'Supabase Storage upload',
         'No Supabase env vars needed on Vercel; simpler, no storage costs, no CORS configuration'],
    ]
    t = make_table(headers, rows, col_widths=[1.3*inch, 1.3*inch, 1.3*inch, 2.6*inch])
    story.append(t)


def build_section18(story):
    section_header('18. End-to-End Data Flow', story)
    story.append(Paragraph(
        'The complete journey of a single student question — from keypress to genome update. '
        'This is the critical path through every layer of the system.',
        styles['Body']))
    path = make_e2e_flow()
    story.append(img(path, 6.0 * inch))
    story.append(Paragraph('Figure: Complete end-to-end data flow for a student question', styles['Caption']))
    story.append(Spacer(1, 10))
    story.append(Paragraph('<b>Step-by-Step Walkthrough</b>', styles['H3']))
    steps = [
        '<b>1. Input:</b> Student types question in doubt/page.tsx ChatInput. Subject and topic may be pre-set from TopicTree navigation.',
        '<b>2. API Call:</b> POST /doubt/ask/stream fires. Body: {question, subject, study_session_id, doubt_session_id, hint_level}.',
        '<b>3. Intent:</b> gpt-4o-mini classifies as SOCRATIC (or CONTINUATION, EXPLANATION, CONVERSATIONAL, OUT_OF_SCOPE).',
        '<b>4. RAG:</b> AgenticRetriever.run(): embed once → gpt-4o-mini tool selection → parallel asyncio.gather() → hybrid RRF → top chunks.',
        '<b>5. Context:</b> build_context_bundle() pulls: Redis hot context (last 2 summaries) + Postgres compressed_profile + top 5 weakest concepts.',
        '<b>6. Policy:</b> select_pedagogy(persona_profile, topic, hint_level) returns PedagogyConfig: scaffolding_level, socratic_style, max_concepts, check_in_required.',
        '<b>7. Misconception:</b> check_for_misconception(response, topic, subject) checks against 30-entry library. Match → 1.5× penalty flag.',
        '<b>8. Prompt:</b> build_system_prompt() assembles full prompt: TUTOR_SYSTEM_PROMPT + CUSTOMIZATION_PROMPT + PERSONALIZATION_PROMPT + student context block.',
        '<b>9. Streaming:</b> gpt-4.1-mini streams response token-by-token as SSE events {"token": "...", "done": false}.',
        '<b>10. Sanitize:</b> _sanitize_latex() runs on each chunk before sending to client. Frontend renders with KaTeX.',
        '<b>11. Resolve:</b> Student clicks "Got it" → POST /doubt/hint with student_resolved=true → _genome_update_task fires EMA mastery update.',
        '<b>12. Session End:</b> POST /session/end → await summarize_session() (blocking) → update_hot_context() (Redis) → asyncio.create_task(maybe_compress_profile()) (background) → asyncio.create_task(judge_eval) (background).',
    ]
    for s in steps:
        story.append(Paragraph(s, styles['BodyLeft']))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 12))
    story.append(Paragraph('<b>Knowledge Base Summary</b>', styles['H3']))
    headers = ['Metric', 'Value']
    rows = [
        ['Total knowledge chunks', '15,069'],
        ['Physics chunks', '10,505 (Class 11 + 12, all chapters)'],
        ['Chemistry chunks', '3,138 (Class 11 + 12, ingested from KadamParth HuggingFace dataset)'],
        ['Maths chunks', '1,426 (Class 11 + 12, ingested from NCERT PDFs via pdfplumber)'],
        ['JEE PYQs', '20 verified seed problems (Physics + Chemistry + Maths)'],
        ['Total concept nodes', '199 (Physics: 84, Chemistry: 62, Maths: 53)'],
        ['Embedding model', 'text-embedding-3-small, 1536 dimensions, uniform across all tables'],
        ['Embedding index', 'HNSW (pgvector 0.8.2), cosine distance metric'],
        ['Text search index', 'pg_trgm GIN on content + subtopic columns'],
        ['Chunk size', '~350 tokens with 50-token overlap'],
    ]
    t = make_table(headers, rows, col_widths=[2.5*inch, 4.0*inch])
    story.append(t)


# ─────────────────────────────────────────
# TABLE OF CONTENTS
# ─────────────────────────────────────────
def build_toc(story):
    story.append(HRFlowable(width='100%', thickness=3, color=colors.HexColor(BLUE),
                             spaceAfter=4, spaceBefore=16))
    story.append(Paragraph('Table of Contents', styles['H1']))
    story.append(Spacer(1, 10))
    sections = [
        ('1', 'What Is UpMyRank?', 'Platform overview, core thesis, key principles'),
        ('2', 'The PTB Educational AI Framework', 'Three-layer architecture, philosophy'),
        ('3', 'The Build Journey — 10 Phases', 'Phase-by-phase development timeline'),
        ('4', 'Technology Stack', 'Full stack: backend, LLM, DB, frontend, hosting'),
        ('5', 'Backend Architecture', 'Startup sequence, API routers'),
        ('6', 'The Socratic Engine', 'Question processing pipeline, intent types'),
        ('7', 'The Hint Ladder', 'Levels 0–4, Level 3 nuclear gate'),
        ('8', 'Agentic RAG System', '4 tools, hybrid RRF, performance optimizations'),
        ('9', 'Database Schema', '14 tables, migration timeline'),
        ('10', '3-Layer Student Memory', 'Redis + Postgres + concept mastery, persona evolution'),
        ('11', 'Policy Engine', 'Scaffolding inference, subject overrides'),
        ('12', 'Misconception Detection', '30-entry library, 1.5× penalty'),
        ('13', 'Judge Evaluation System', '4-dimension scoring, admin dashboard, regression gate'),
        ('14', 'Onboarding Flow', '4-step flow, persona builder'),
        ('15', 'Frontend Architecture', 'Pages, components, SSE streaming'),
        ('16', 'Hard Invariants — The Rules', '9 rules that must never be violated'),
        ('17', 'Architecture Decisions', 'What was chosen, what was rejected, why'),
        ('18', 'End-to-End Data Flow', 'Complete journey of a student question'),
    ]
    rows = [[f'§{num}', title, desc] for num, title, desc in sections]
    t = make_table(['§', 'Section', 'Summary'], rows, col_widths=[0.4*inch, 2.2*inch, 3.9*inch])
    story.append(t)
    story.append(PageBreak())


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.75 * inch,
        title='UpMyRank Technical Documentation',
        author='UpMyRank Engineering',
        subject='Architecture and Codebase Reference',
    )

    story = []

    # ── Cover page (blank placeholder — canvas draws over it) ──
    # Use a KeepTogether with multiple small spacers to fill the first page
    story.append(Spacer(1, 1 * inch))
    story.append(Spacer(1, 1 * inch))
    story.append(Spacer(1, 1 * inch))
    story.append(Spacer(1, 1 * inch))
    story.append(Spacer(1, 1 * inch))
    story.append(Spacer(1, 1 * inch))
    story.append(PageBreak())

    # ── Table of Contents ──
    build_toc(story)

    # ── Sections ──
    build_section1(story)
    story.append(PageBreak())

    build_section2(story)
    story.append(PageBreak())

    build_section3(story)
    story.append(PageBreak())

    build_section4(story)
    story.append(PageBreak())

    build_section5(story)
    story.append(PageBreak())

    build_section6(story)
    story.append(PageBreak())

    build_section7(story)
    story.append(PageBreak())

    build_section8(story)
    story.append(PageBreak())

    build_section9(story)
    story.append(PageBreak())

    build_section10(story)
    story.append(PageBreak())

    build_section11(story)
    story.append(PageBreak())

    build_section12(story)
    story.append(PageBreak())

    build_section13(story)
    story.append(PageBreak())

    build_section14(story)
    story.append(PageBreak())

    build_section15(story)
    story.append(PageBreak())

    build_section16(story)
    story.append(PageBreak())

    build_section17(story)
    story.append(PageBreak())

    build_section18(story)

    # ── Build with footer on all pages except cover ──
    def on_page(c, d):
        if d.page == 1:
            build_cover(c, d)
        else:
            footer(c, d)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f'PDF generated: {OUTPUT}')
    import os as _os
    size = _os.path.getsize(OUTPUT)
    print(f'File size: {size:,} bytes ({size/1024/1024:.2f} MB)')


if __name__ == '__main__':
    main()
