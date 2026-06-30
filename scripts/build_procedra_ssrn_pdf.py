from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/research/procedra_ssrn_working_paper_pdf_ready.md"
OUTPUT = ROOT / "docs/research/procedra_ssrn_working_paper.pdf"


def esc(text: str) -> str:
    text = text.strip().replace("`", "")
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    text = html.escape(text, quote=False)
    text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    text = text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    return text


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PaperTitle",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "meta": ParagraphStyle(
            "Meta",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8.8,
            leading=11.2,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=11,
            leading=13,
            alignment=TA_LEFT,
            spaceBefore=12,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "Heading3",
            parent=base["Heading3"],
            fontName="Times-Bold",
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=9,
            leading=11.8,
            alignment=TA_JUSTIFY,
            spaceAfter=5,
        ),
        "body_left": ParagraphStyle(
            "BodyLeft",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=9,
            leading=11.8,
            alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=7.3,
            leading=8.6,
            alignment=TA_LEFT,
            spaceAfter=3,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="Times-Bold",
            fontSize=7.4,
            leading=8.8,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Times-Bold",
            fontSize=6.5,
            leading=7.4,
            alignment=TA_LEFT,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=6.2,
            leading=7.2,
            alignment=TA_LEFT,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=8.8,
            leading=11,
            alignment=TA_LEFT,
            leftIndent=16,
            firstLineIndent=-10,
            spaceAfter=1.5,
        ),
    }


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Times-Roman", 7.5)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(inch, 0.45 * inch, "Procedra working paper")
    canvas.drawRightString(letter[0] - inch, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def make_markdown_table(lines: list[str], st: dict[str, ParagraphStyle]) -> Table:
    rows = [split_table_row(line) for line in lines if not re.match(r"^\s*\|?\s*:?-{3,}", line)]
    data = []
    for r, row in enumerate(rows):
        style = st["table_header"] if r == 0 else st["table_cell"]
        data.append([Paragraph(esc(cell), style) for cell in row])
    widths = [2.02 * inch, 1.45 * inch, 2.85 * inch]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=0)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CFCFCF")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]
        )
    )
    return table


def make_workflow_figure(st: dict[str, ParagraphStyle]) -> KeepTogether:
    rows = [
        ["Task, technical context, documents, public references, optional video context"],
        ["Source and context handling"],
        ["Structured request and prompt construction"],
        ["OpenAI-backed generation when configured or deterministic fallback"],
        ["JSON parsing, schema validation, quality-improvement and request-focus passes"],
        ["Rule-based quality evaluation"],
        ["Review-ready instruction draft"],
        ["Markdown/PDF/JSON output plus version history, workflow decisions, execution evidence, and audit trail"],
    ]
    table = Table(
        [[Paragraph(esc(row[0]), st["table_cell"])] for row in rows],
        colWidths=[5.95 * inch],
        hAlign="CENTER",
        splitByRow=0,
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8D8D8")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return KeepTogether(
        [
            Spacer(1, 4),
            Paragraph("Figure 1. Procedra source-supported drafting workflow", st["caption"]),
            table,
            Spacer(1, 8),
        ]
    )


def make_list(items: list[str], ordered: bool, st: dict[str, ParagraphStyle]) -> list[Paragraph]:
    rendered = []
    for index, item in enumerate(items, 1):
        marker = f"{index}." if ordered else "-"
        rendered.append(Paragraph(f"{marker} {esc(item)}", st["bullet"]))
    return rendered


def flush_pending(story, pending, st) -> None:
    kind = pending.get("kind")
    items = pending.get("items", [])
    if not kind or not items:
        pending.clear()
        return
    if kind in {"bullet", "ordered"}:
        story.append(KeepTogether([*make_list(items, kind == "ordered", st), Spacer(1, 4)]))
    elif kind == "table":
        story.append(KeepTogether([make_markdown_table(items, st), Spacer(1, 7)]))
    pending.clear()


def build_story():
    st = make_styles()
    story = []
    pending: dict[str, object] = {}
    in_mermaid = False

    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    for raw in lines:
        line = raw.rstrip()

        if line.startswith("```mermaid"):
            flush_pending(story, pending, st)
            in_mermaid = True
            continue
        if in_mermaid:
            if line.startswith("```"):
                story.append(make_workflow_figure(st))
                in_mermaid = False
            continue

        if not line:
            flush_pending(story, pending, st)
            continue

        if line.startswith("|"):
            if pending.get("kind") not in {None, "table"}:
                flush_pending(story, pending, st)
            pending.setdefault("kind", "table")
            pending.setdefault("items", []).append(line)
            continue

        bullet_match = re.match(r"^- (.+)$", line)
        ordered_match = re.match(r"^\d+\. (.+)$", line)
        if bullet_match or ordered_match:
            next_kind = "bullet" if bullet_match else "ordered"
            if pending.get("kind") not in {None, next_kind}:
                flush_pending(story, pending, st)
            pending.setdefault("kind", next_kind)
            pending.setdefault("items", []).append((bullet_match or ordered_match).group(1))
            continue

        flush_pending(story, pending, st)

        if line.startswith("# "):
            story.append(Paragraph(esc(line[2:]), st["title"]))
        elif line == "Author:":
            story.append(Paragraph("Author:", st["meta"]))
        elif line.startswith("## "):
            heading = line[3:]
            if heading in {
                "5.5 Claims requiring further validation",
                "7. Limitations",
                "8. Future Work",
                "AI-Assisted Writing Disclosure",
                "References",
                "Appendix A. Claim Register",
            }:
                story.append(PageBreak())
            story.append(Paragraph(esc(heading), st["h2"]))
        elif line.startswith("### "):
            heading = line[4:]
            if heading in {
                "5.1 Repository-confirmed evidence",
                "5.5 Claims requiring further validation",
            }:
                story.append(PageBreak())
            story.append(Paragraph(esc(heading), st["h3"]))
        elif line.startswith("["):
            story.append(Paragraph(esc(line), st["body_left"]))
        else:
            style = st["meta"] if line in {"Aleksander Shuvalov"} or line.startswith(("Affiliation:", "Email:", "Date written:")) else st["body"]
            story.append(Paragraph(esc(line), style))

    flush_pending(story, pending, st)
    return story


def main() -> None:
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=0.82 * inch,
        title="Procedra: A Source-Supported Software Artifact for Human-in-the-Loop Industrial AI",
        author="Aleksander Shuvalov",
    )
    doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
