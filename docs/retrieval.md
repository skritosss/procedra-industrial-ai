# Retrieval

The current retrieval module is a hybrid RAG foundation. It indexes `.md` and `.txt` files from `examples/knowledge_base/`, extracted text from uploaded enterprise documents in `uploads/documents/`, splits them into chunks, and ranks chunks with a combined semantic + lexical score. It also adds a curated public-source layer with open standards, rules, methods, and public legal/reference pages relevant to industrial work instructions.

Semantic retrieval uses OpenAI embeddings when `OPENAI_ENABLED=true` and `OPENAI_API_KEY` is configured. If embeddings are unavailable, the module falls back to deterministic local hashed embeddings over normalized tokens and character n-grams. Lexical retrieval remains active through token overlap and IDF weighting, so exact technical terms still matter.

## Endpoints

```text
POST /api/instructions/retrieve
```

Returns relevant source chunks for a request.

```text
POST /api/instructions/generate-with-context
```

Retrieves relevant documentation chunks, public references, merges them into `technical_context`, generates an instruction, evaluates it, and returns the used sources.

```text
GET /api/documents
POST /api/documents/upload
```

Lists uploaded enterprise documents and uploads `.txt`, `.md`, or text-based `.pdf` files. Uploaded files are converted into extracted text artifacts for retrieval instead of being used as opaque binary files.

## Current Knowledge Base

The demo knowledge base includes:

- workplace preparation;
- equipment startup;
- equipment shutdown and shift handover.

Uploaded enterprise documents are stored under `uploads/documents/` as normalized `.txt` files with original filename metadata. These sources are labeled as `Загруженные документы пользователя` and are preferred over built-in demo documents in the local-source portion of the result set.

Retrieval is fail closed: an uploaded artifact is eligible only when the active
organization/project has a matching `resource_ownership` row. Unregistered
files and filesystem symlinks are ignored by list, retrieve, and contextual
generation paths. Retrieved text, document metadata, video transcripts, and
visible text in frames are always treated as untrusted evidence, never as model
instructions; expert review remains mandatory because prompt-injection risk can
be reduced but not proven absent.

The public catalog includes source families for:

- machine and equipment safety;
- production equipment general safety;
- workplace preparation and hazard zones;
- PPE selection;
- occupational-safety management;
- technological equipment maintenance and repair;
- electrical-safety operations;
- fire-safety regime;
- sanitary and working-condition checks;
- occupational-safety legal/reference navigation.

Public sources are returned with `source_type=public`, a `url`, authority/platform, document type, applicable industry profiles, matched terms, influence score, and a short contribution reason. The default source limit is 15, and public sources are prioritized before local demo documents so the generated instruction is grounded primarily in open standards, rules, and reference materials. Their excerpts are intentionally short and review-oriented. The system must not treat them as a final legal conclusion: current edition, legal force, and applicability must be verified before real enterprise deployment.

For partner demos, use source count `15`. The expected behavior is an external-source majority first, followed by a small number of uploaded enterprise documents and local demo documents when relevant. This makes the evidence trail visible while still allowing enterprise-specific context to influence the draft.

The public catalog is profile-aware. The selected `industry_profile` adds ranking weight for sources applicable to the domain, while instruction type and query-term overlap still matter. This helps construction, manufacturing, occupational-safety, sanitation, fire-safety, and other scenarios surface more relevant references before local demo documents are used.

## Why This Step Matters

The project no longer generates instructions only from a user prompt. It can ground the result in technical documentation and show which source excerpts were used. Hybrid retrieval helps when the user's wording differs from the source wording, while the deterministic fallback keeps local demos stable.

## Limitations

- Direct indexing supports `.md` and `.txt`; uploaded text-based `.pdf` files are supported after text extraction.
- Scanned image-only PDFs require OCR before upload or a future OCR layer.
- Public sources are curated references, not a live legal-status validator.
- Sources may include uploaded enterprise documents, demo documents, and public-reference documents; approval status must still be verified.
- Expert review is still required before any real production use.

## Source Review Checklist

- Check that most returned sources are public when public retrieval is enabled.
- Check source authority/platform, document type, matched terms, and contribution reason.
- Open the most important public URLs before the demo when internet access is available.
- Confirm that the generated instruction does not cite a public source as final legal approval.
- Move enterprise-specific requirements into approved local documents before a real pilot.
