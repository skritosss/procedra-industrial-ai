from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.generation import pdf_theme
from app.generation.industry_profiles import profile_label
from app.schemas.instruction import InstructionResponse, StepFrameLink


SERVICE_NAME = "Procedra"
DRAFT_NOTICE = "AI-черновик. Не заменяет утверждённую инструкцию предприятия."
CONTENT_WIDTH = 178 * mm
STEP_NUMBER_WIDTH = 12 * mm
SCORE_COLUMN_WIDTH = 34 * mm
BRAND_WORDMARK_PNG = Path(__file__).resolve().parents[1] / "static" / "assets" / "brand" / "procedra-wordmark-monochrome.png"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial.ttf",
]


def render_instruction_pdf(payload: InstructionResponse) -> bytes:
    buffer = BytesIO()
    font_name, bold_font_name = _register_fonts()
    styles = _styles(font_name, bold_font_name)
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=payload.instruction.title,
        author=SERVICE_NAME,
    )
    story = _build_story(payload, styles)
    document.build(
        story,
        onFirstPage=lambda canvas, doc: _decorate_page(canvas, doc, font_name),
        onLaterPages=lambda canvas, doc: _decorate_page(canvas, doc, font_name),
    )
    return buffer.getvalue()


def _register_fonts() -> tuple[str, str]:
    regular = next((Path(path) for path in FONT_CANDIDATES if Path(path).exists() and "Bold" not in path), None)
    bold = next((Path(path) for path in FONT_CANDIDATES if Path(path).exists() and "Bold" in path), None)
    if regular:
        pdfmetrics.registerFont(TTFont("InstructionSans", str(regular)))
        if bold:
            pdfmetrics.registerFont(TTFont("InstructionSans-Bold", str(bold)))
            return "InstructionSans", "InstructionSans-Bold"
        return "InstructionSans", "InstructionSans"
    return "Helvetica", "Helvetica-Bold"


def _styles(font_name: str, bold_font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "InstructionTitle",
            parent=base["Title"],
            fontName=bold_font_name,
            fontSize=19,
            leading=23,
            alignment=0,
            textColor=pdf_theme.INK,
            spaceAfter=6,
        ),
        "lede": ParagraphStyle(
            "InstructionLede",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=13.5,
            textColor=pdf_theme.MUTED,
            spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "InstructionHeading",
            parent=base["Heading2"],
            fontName=bold_font_name,
            fontSize=11,
            leading=14,
            textColor=pdf_theme.INK,
            spaceBefore=2,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "InstructionBody",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=13,
            textColor=pdf_theme.INK,
            spaceAfter=3,
        ),
        "bullet": ParagraphStyle(
            "InstructionBullet",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=9.5,
            leading=13,
            textColor=pdf_theme.INK,
            leftIndent=8,
            bulletIndent=0,
            spaceAfter=2,
        ),
        "step": ParagraphStyle(
            "InstructionStep",
            parent=base["BodyText"],
            fontName=bold_font_name,
            fontSize=10.5,
            leading=14,
            textColor=pdf_theme.INK,
            spaceAfter=3,
        ),
        "step_number": ParagraphStyle(
            "InstructionStepNumber",
            parent=base["BodyText"],
            fontName=bold_font_name,
            fontSize=9.5,
            leading=14,
            textColor=pdf_theme.MUTED,
        ),
        "term": ParagraphStyle(
            "InstructionTerm",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=11.5,
            textColor=pdf_theme.MUTED,
        ),
        "definition": ParagraphStyle(
            "InstructionDefinition",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=11.5,
            textColor=pdf_theme.INK,
        ),
        "meta": ParagraphStyle(
            "InstructionMeta",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=11.5,
            textColor=pdf_theme.MUTED,
            spaceAfter=2,
        ),
        "score": ParagraphStyle(
            "InstructionScore",
            parent=base["BodyText"],
            fontName=bold_font_name,
            fontSize=16,
            leading=18,
            alignment=2,
            textColor=pdf_theme.INK,
        ),
    }


def _badge(text: str, variant_value: str, styles: dict[str, ParagraphStyle]) -> tuple[Table, float]:
    """A filled pill, the print twin of the on-screen badge."""
    ink, background = pdf_theme.semantic_pair(variant_value)
    label = ParagraphStyle(
        "Badge",
        parent=styles["meta"],
        fontSize=7.8,
        leading=9.5,
        textColor=ink,
        spaceAfter=0,
    )
    # Width follows the text: a table column would otherwise stretch the pill
    # across its share of the row.
    width = pdfmetrics.stringWidth(text, label.fontName, label.fontSize) + 12
    cell = Table([[Paragraph(_escape(text), label)]], colWidths=[width])
    cell.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("ROUNDEDCORNERS", [3, 3, 3, 3]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return cell, width


def _badge_row(badges: list[tuple[Table, float]]) -> Table | None:
    if not badges:
        return None
    row = Table(
        [[badge for badge, _ in badges]],
        colWidths=[width + 4 for _, width in badges],
        hAlign="LEFT",
    )
    row.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return row


def _panel(content: list, background: colors.Color, border: colors.Color | None = None) -> Table:
    """One surface on the page: no card inside a card, matching the screen."""
    panel = Table([[content]], colWidths=[CONTENT_WIDTH])
    style: list = [
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]
    if border is not None:
        style.append(("BOX", (0, 0), (-1, -1), 0.4, border))
    panel.setStyle(TableStyle(style))
    return panel


def _build_story(payload: InstructionResponse, styles: dict[str, ParagraphStyle]) -> list:
    instruction = payload.instruction
    links_by_step = {link.step_number: link for link in payload.step_frame_links}
    head: list = []
    badges = [
        _badge(instruction.workflow.status_label, instruction.workflow.status, styles),
        _badge(
            f"Уровень риска: {_risk_label(payload.evaluation.risk_level)}",
            payload.evaluation.risk_level,
            styles,
        ),
    ]
    badge_row = _badge_row(badges)
    if badge_row is not None:
        head.extend([badge_row, Spacer(1, 7)])
    head.append(Paragraph(_escape(instruction.title), styles["title"]))
    head.append(Paragraph(_escape(instruction.purpose), styles["lede"]))
    head.append(
        Paragraph(
            f"{_generation_mode_label(payload.generation_mode)} · {DRAFT_NOTICE}",
            styles["meta"],
        )
    )
    story: list = [
        _panel(head, pdf_theme.BRAND_SURFACE_SOFT, pdf_theme.BRAND_SURFACE),
        Spacer(1, 12),
        *_evaluation_summary(payload, styles),
    ]

    _section(story, styles, "Область применения", [instruction.scope])
    _section(
        story,
        styles,
        "Паспорт инструкции",
        [
            f"Участок: {instruction.department or 'Не указано'}",
            f"Оборудование: {instruction.equipment or 'Не указано'}",
            f"Уровень пользователя: {instruction.operator_level}",
            f"Статус: {instruction.workflow.status_label}.",
        ],
    )
    _section(story, styles, "Роли для согласования", instruction.workflow.required_review_roles)
    _section(story, styles, "Блокеры перед утверждением", instruction.workflow.approval_blockers)
    _section(story, styles, "Следующие действия по внедрению", instruction.workflow.next_actions)
    _section(story, styles, "Матрица ответственности", _responsibility_items())
    _section(story, styles, "Утверждения из входных данных", instruction.observed_facts)
    _section(
        story,
        styles,
        "Происхождение и статус утверждений",
        [
            (
                f"[{claim.claim_id or 'claim_id отсутствует'}; {claim.provenance}; "
                f"{claim.validation_status}; source={claim.source_id or 'не указан'}] {claim.text}"
                + (
                    " | validated by "
                    f"{claim.validation_record.reviewer_name} "
                    f"({claim.validation_record.reviewer_role}); "
                    f"evidence={claim.validation_record.evidence_reference}"
                    if claim.validation_record
                    else ""
                )
            )
            for claim in instruction.evidence_claims
        ],
    )
    _section(story, styles, "Что требуется проверить локально", instruction.local_verification_required)
    _section(story, styles, "Вопросы для экспертной проверки", instruction.expert_review_questions)
    _section(story, styles, "Средства индивидуальной защиты", instruction.required_ppe)
    _section(story, styles, "Инструменты и документы", instruction.required_tools)
    _section(story, styles, "Требования безопасности", instruction.safety_requirements)
    _section(story, styles, "Опасные зоны", instruction.hazard_zones)
    _section(story, styles, "Предварительные условия", instruction.prerequisites)

    _heading(story, styles, "Порядок выполнения")
    for step in instruction.steps:
        story.append(_step_block(step, links_by_step.get(step.number), styles))

    _section(story, styles, "Критерии приемки результата", _acceptance_items(instruction.control_points))
    _section(story, styles, "Чеклист качества", instruction.quality_checklist)
    _section(story, styles, "Действия при нештатной ситуации", instruction.emergency_actions)
    _section(story, styles, "Типовые ошибки", instruction.common_mistakes)
    _section(story, styles, "Экспертная проверка", _expert_review_items(payload))
    _section(story, styles, "Ограничения и проверка перед внедрением", _limitation_items())

    if payload.sources:
        story.append(PageBreak())
        story.append(Paragraph("Использованные источники", styles["h2"]))
        story.append(Spacer(1, 4))
        for source in payload.sources:
            story.append(_source_block(source, styles))

    return story


def _heading(story: list, styles: dict[str, ParagraphStyle], title: str) -> None:
    """A hairline plus a label. Space and a rule separate sections, not boxes."""
    rule = Table([[""]], colWidths=[CONTENT_WIDTH], rowHeights=[0.4])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), pdf_theme.LINE)]))
    story.append(Spacer(1, 9))
    story.append(rule)
    story.append(Spacer(1, 5))
    story.append(Paragraph(_escape(title), styles["h2"]))


def _section(story: list, styles: dict[str, ParagraphStyle], title: str, items: list[str]) -> None:
    _heading(story, styles, title)
    for item in items or ["Не указано"]:
        story.append(Paragraph(_escape(item), styles["bullet"], bulletText="•"))


def _source_block(source, styles: dict[str, ParagraphStyle]) -> Table:
    """One source, read top-down: what kind it is, what it is, why it is here.

    Everything numeric collapses into a single line. Nine equally grey lines per
    source made the section unreadable exactly where a customer checks whether
    the draft rests on anything real.
    """
    kind = "открытый интернет-источник" if source.source_type == "public" else "локальная база"
    badges = [_badge(kind, source.source_type, styles)]
    if source.document_type:
        badges.append(_badge(source.document_type, "neutral", styles))

    body: list = []
    badge_row = _badge_row(badges)
    if badge_row is not None:
        body.extend([badge_row, Spacer(1, 5)])
    body.append(Paragraph(_escape(source.title), styles["step"]))
    if source.contribution_reason:
        body.append(Paragraph(_escape(source.contribution_reason), styles["meta"]))

    facts = [
        f"релевантность {source.score:.2f}",
        f"влияние {source.influence_score:.2f}",
    ]
    if source.authority:
        facts.append(_escape(source.authority))
    if source.applicable_profiles:
        facts.append(", ".join(profile_label(profile) for profile in source.applicable_profiles))
    if source.matched_terms:
        facts.append("совпало: " + ", ".join(source.matched_terms))
    body.append(Paragraph(" · ".join(facts), styles["meta"]))
    body.append(Paragraph(_escape(source.url or f"{source.path} #{source.chunk_index}"), styles["meta"]))

    if source.excerpt:
        quote = ParagraphStyle(
            "SourceExcerpt",
            parent=styles["meta"],
            leftIndent=8,
            textColor=pdf_theme.INK,
            spaceAfter=0,
        )
        body.extend([Spacer(1, 3), Paragraph(_escape(source.excerpt), quote)])

    block = Table([[body]], colWidths=[CONTENT_WIDTH])
    block.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEABOVE", (0, 0), (-1, 0), 0.4, pdf_theme.LINE),
            ]
        )
    )
    # Not kept together: an excerpt can run long, and holding a whole source on
    # one page leaves half a page blank more often than it helps.
    return block


def _step_block(step, link, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    """Number in its own column, then the action, its terms and any warning.

    A step is the unit a reader acts on, so it never breaks across pages.
    """
    body: list = [Paragraph(_escape(step.action), styles["step"])]

    terms: list[tuple[str, str]] = [("Ожидаемый результат", step.expected_result)]
    if step.verification_method:
        terms.append(("Проверка", step.verification_method))
    if step.common_mistakes:
        terms.append(("Типовые ошибки", ", ".join(step.common_mistakes)))
    if link is not None:
        terms.append(("Видео", _step_link_text(link)))

    definitions = Table(
        [
            [Paragraph(_escape(term), styles["term"]), Paragraph(_escape(value), styles["definition"])]
            for term, value in terms
        ],
        colWidths=[34 * mm, CONTENT_WIDTH - STEP_NUMBER_WIDTH - 34 * mm - 6 * mm],
    )
    definitions.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    body.append(definitions)

    if step.safety_note:
        ink, background = pdf_theme.SEMANTIC["critical"]
        note_style = ParagraphStyle(
            "SafetyNote", parent=styles["meta"], textColor=ink, spaceAfter=0
        )
        note = Table(
            [[Paragraph(f"Безопасность: {_escape(step.safety_note)}", note_style)]],
            colWidths=[CONTENT_WIDTH - STEP_NUMBER_WIDTH - 6 * mm],
        )
        note.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), background),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                ]
            )
        )
        body.extend([Spacer(1, 4), note])

    row = Table(
        [[Paragraph(str(step.number), styles["step_number"]), body]],
        colWidths=[STEP_NUMBER_WIDTH, CONTENT_WIDTH - STEP_NUMBER_WIDTH],
    )
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEABOVE", (0, 0), (-1, 0), 0.4, pdf_theme.LINE),
            ]
        )
    )
    return KeepTogether(row)


def _evaluation_summary(payload, styles: dict[str, ParagraphStyle]) -> list:
    """Score, verdict and every criterion with a bar, as on the checks tab.

    The export used to carry the number and the verdict but not the ten
    criteria behind them, so a reader could not see which part was weak.
    """
    evaluation = payload.evaluation
    left: list = [
        Paragraph("Оценка структуры", styles["meta"]),
        Paragraph(_escape(evaluation.verdict), styles["body"]),
    ]
    header = Table(
        [[left, Paragraph(f"{evaluation.overall_score}", styles["score"])]],
        colWidths=[CONTENT_WIDTH - SCORE_COLUMN_WIDTH, SCORE_COLUMN_WIDTH],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (0, -1), "TOP"),
                ("VALIGN", (1, 0), (1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    rows: list = [header, Spacer(1, 8)]
    for criterion in evaluation.criteria:
        rows.append(_criterion_row(criterion, styles))
    return rows


def _criterion_row(criterion, styles: dict[str, ParagraphStyle]) -> Table:
    ink, _ = pdf_theme.SEMANTIC[pdf_theme.score_band(criterion.score)]
    bar_width = (SCORE_COLUMN_WIDTH - 6 * mm) * max(criterion.score, 0) / 100
    bar = Table(
        [[""]],
        colWidths=[max(bar_width, 0.5)],
        rowHeights=[2.4],
        hAlign="RIGHT",
    )
    bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ink)]))

    track = Table([[bar]], colWidths=[SCORE_COLUMN_WIDTH - 6 * mm], hAlign="RIGHT")
    track.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), pdf_theme.SURFACE_SUNKEN),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )

    score_cell = [Paragraph(str(criterion.score), styles["score"]), Spacer(1, 3), track]
    row = Table(
        [[Paragraph(_escape(criterion.label), styles["body"]), score_cell]],
        colWidths=[CONTENT_WIDTH - SCORE_COLUMN_WIDTH, SCORE_COLUMN_WIDTH],
    )
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEABOVE", (0, 0), (-1, 0), 0.4, pdf_theme.LINE),
            ]
        )
    )
    return row


def _meta(story: list, styles: dict[str, ParagraphStyle], text: str) -> None:
    story.append(Paragraph(_escape(text), styles["meta"]))


def _step_link_text(link: StepFrameLink) -> str:
    minutes = int(round(link.timestamp_seconds)) // 60
    seconds = int(round(link.timestamp_seconds)) % 60
    return (
        f"{minutes:02d}:{seconds:02d}, кадр {link.frame_index}, "
        f"уверенность {link.confidence:.2f}. {link.reason}"
    )


def _responsibility_items() -> list[str]:
    return [
        "Оператор выполняет действия только в пределах допуска и фиксирует отклонения.",
        "Мастер смены подтверждает применимость инструкции к конкретному участку и оборудованию.",
        "Инженер/технолог уточняет режимы, допуски и локальные требования, отсутствующие во входных данных.",
    ]


def _acceptance_items(control_points: list[str]) -> list[str]:
    return [
        "Все обязательные контрольные точки выполнены и подтверждены ответственным лицом.",
        "Рабочее место и оборудование находятся в безопасном, определенном состоянии.",
        "Отклонения, замечания и ограничения зафиксированы в принятой на участке форме.",
        *control_points,
    ]


def _limitation_items() -> list[str]:
    return [
        "Документ является AI-черновиком и не заменяет утвержденные инструкции предприятия.",
        "Точные режимы, нормы времени, допуски и ссылки на стандарты должны быть подтверждены локальной документацией.",
        "Перед применением на производстве инструкцию должен проверить ответственный специалист по технологии и охране труда.",
    ]


def _expert_review_items(payload: InstructionResponse) -> list[str]:
    review_status = "требуется" if payload.evaluation.expert_review_required else "не требуется"
    return [
        f"Статус экспертной проверки: {review_status}.",
        f"Уровень риска: {_risk_label(payload.evaluation.risk_level)}.",
        *payload.evaluation.expert_review_notes,
    ]


def _generation_mode_label(mode: str) -> str:
    """Say what produced the draft, not which internal identifier was stored."""
    labels = {"model": "языковая модель", "deterministic": "детерминированный шаблон"}
    return _escape(labels.get(mode, mode))


def _risk_label(risk_level: str) -> str:
    labels = {
        "low": "низкий",
        "medium": "средний",
        "high": "высокий",
        "critical": "критический",
    }
    return labels.get(risk_level, risk_level)


def _decorate_page(canvas, document, font_name: str) -> None:
    """Footer only.

    The diagonal wash across every page said the same thing a reader could not
    read and made the body harder to. The draft status now sits in the document
    head, in words, where it is actually noticed.
    """
    width, _ = A4
    canvas.saveState()
    canvas.setStrokeColor(pdf_theme.LINE)
    canvas.setLineWidth(0.4)
    canvas.line(document.leftMargin, 14 * mm, width - document.rightMargin, 14 * mm)
    if BRAND_WORDMARK_PNG.is_file():
        canvas.drawImage(
            str(BRAND_WORDMARK_PNG),
            document.leftMargin,
            7.7 * mm,
            width=25 * mm,
            height=4.7 * mm,
            preserveAspectRatio=True,
            anchor="sw",
            mask="auto",
        )
    else:
        canvas.setFont(font_name, 8)
        canvas.setFillColor(pdf_theme.MUTED)
        canvas.drawString(document.leftMargin, 10 * mm, SERVICE_NAME)
    canvas.setFont(font_name, 8)
    canvas.setFillColor(pdf_theme.MUTED)
    canvas.drawRightString(width - document.rightMargin, 10 * mm, str(document.page))
    canvas.restoreState()


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
