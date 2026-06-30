# Что уже готово

- SSRN requirements check: `docs/research/ssrn_requirements_check.md`
- Materials inventory: `docs/research/procedra_materials_inventory.md`
- Evidence audit: `docs/research/procedra_evidence_audit.md`
- Paper strategy: `docs/research/procedra_paper_strategy.md`
- SSRN metadata package: `docs/research/procedra_ssrn_submission_package.md`
- Working paper Markdown: `docs/research/procedra_ssrn_working_paper.md`
- PDF-ready Markdown: `docs/research/procedra_ssrn_working_paper_pdf_ready.md`
- SSRN readiness audit: `docs/research/procedra_ssrn_readiness_audit.md`
- Final pre-submission quality audit: `docs/research/procedra_final_pre_submission_quality_audit.md`
- External benchmark audit: `docs/research/procedra_external_benchmark_audit.md`
- Reproducible PDF generator: `scripts/build_procedra_ssrn_pdf.py`

# Что Александр должен заполнить вручную

- Фамилия / полное имя на английском: `Aleksander Shuvalov`
- Affiliation: `South Ural State University, Center for Elite IT Training "Digital Ural"`
- Email: `shuv.aleksandr@icloud.com`
- ORCID: `Not provided`
- Location: `Chelyabinsk, Russia`
- SSRN author profile: completed in browser; do one final visual check in SSRN preview
- Final date written: сейчас стоит `June 29, 2026`, подтверди или измени
- Funding statement confirmation: `No external funding was received for this work.`
- Conflict of interest confirmation: `The author declares no known conflicts of interest related to this working paper.`
- GitHub/public repo link: `https://github.com/skritosss/procedra-industrial-ai`
- Final permission/public-safety check for screenshots and materials: author confirmed current screenshots/materials are OK to use

# Что вставить в SSRN

## Title

Procedra: A Source-Supported Software Artifact for Human-in-the-Loop Industrial AI

## Abstract

Industrial work instructions are often created through document-heavy workflows that require engineers, technologists, supervisors, and safety specialists to coordinate task context, local procedures, source materials, and reviewer decisions. Plain large language model generation is not sufficient for this setting because fluent procedural text can obscure missing information, unsupported assumptions, and accountability boundaries. This working paper presents Procedra, a source-supported software artifact and controlled local-demo prototype for human-in-the-loop industrial AI. Positioned as an early-stage design-science artifact, Procedra transforms task descriptions, technical context, enterprise documents, curated public references, and optional video-derived signals into structured, review-ready work-instruction drafts. The prototype combines schema-validated generation, deterministic fallback behavior, retrieval-based context handling, rule-based quality evaluation, local verification prompts, expert-review questions, version history, workflow decisions, execution checklist evidence, and audit events. The paper contributes a bounded artifact description, a source-supported drafting workflow pattern, and an evidence protocol that separates implementation evidence from customer, field, safety, and compliance validation. It does not claim production deployment, certified compliance, measured productivity gains, or replacement of approved local procedures and qualified expert review.

## Keywords

Industrial AI; human-in-the-loop AI; work instructions; large language models; retrieval-augmented generation; source grounding; traceability; quality evaluation; manufacturing documentation; software artifact; audit trail; AI product engineering.

## Author metadata

- Author name: Aleksander Shuvalov
- Affiliation: South Ural State University, Center for Elite IT Training "Digital Ural"
- Email: shuv.aleksandr@icloud.com
- ORCID: Not provided
- Location: Chelyabinsk, Russia

## AI disclosure

The author used AI-assisted tools, including OpenAI Codex/ChatGPT, for drafting support, language refinement, structural editing, evidence consistency checks, and preparation of publication-support materials. The author reviewed and edited the manuscript and takes responsibility for the final content, claims, evidence interpretation, and submission.

## Data / code availability

The public software artifact is available at https://github.com/skritosss/procedra-industrial-ai as a source-visible portfolio and research artifact. Raw logs, runtime artifacts, private handoff materials, generated databases, uploads, customer-sensitive data, and local-only working evidence are not part of the public evidence package. Repository use is subject to the license or rights statement selected for the repository.

## Suggested subject areas

Suggested, not guaranteed:

- Artificial Intelligence & Machine Learning eJournal
- Information Systems & eBusiness Network
- Operations Management eJournal
- Innovation & Management Science eJournal
- Human-Computer Interaction eJournal
- Technology, Operations & Analytics eJournal
- Management of Innovation eJournal

# Что проверить перед нажатием Submit

- SSRN profile completed.
- Author name, affiliation, and email are final and consistent in SSRN and PDF.
- PDF opens correctly.
- PDF has 10 pages and keeps Figure 1, references, and appendix table intact.
- PDF title and author block are visible.
- Abstract in SSRN metadata matches the PDF.
- AI disclosure is included in SSRN metadata and PDF.
- Funding and conflict statements are confirmed.
- Data/code availability statement includes the public GitHub URL and excludes local-only evidence.
- References are included.
- No secrets, tokens, `.env` values, private paths, raw logs, generated databases, uploads, or private handoff details.
- No unsupported pilots, customers, revenue, production readiness, compliance, or fake metrics.
- Screenshots/materials are public-safe if linked or included.
- Rights/copyright confirmation is true.

# Что НЕ делать

- Не загружать raw logs.
- Не загружать runtime/generated artifacts.
- Не включать `PROJECT_HANDOFF.md` в public evidence.
- Не указывать неподтвержденные pilots/customers.
- Не обещать production readiness или enterprise readiness.
- Не заявлять legal/regulatory certification.
- Не использовать private screenshots.
- Не добавлять fake metrics.
- Не называть репозиторий open-source, если license не выбран.
- Не называть проект open-source, если license не выбран.

# Финальный SSRN upload sequence

1. Log in to SSRN.
2. Confirm author profile.
3. Start new submission.
4. Upload PDF.
5. Paste title.
6. Paste abstract.
7. Paste keywords.
8. Add author metadata.
9. Add AI disclosure.
10. Add funding/conflict/data availability statements where SSRN asks for them.
11. Choose closest subject areas.
12. Confirm rights/copyright.
13. Review preview.
14. Submit for moderation.

# Минимальный следующий шаг

Открой финальный PDF, проверь первую страницу и disclosure sections, затем можно переносить metadata в SSRN.
