import hashlib
import os
import tempfile
import re
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.core.authorization import (
    list_project_resource_ownerships,
    project_storage_path,
    register_resource_ownership,
    require_permission,
)
from app.core.settings import get_settings
from app.schemas.documents import DocumentListResponse, DocumentUploadResponse, UploadedDocument


router = APIRouter(prefix="/documents", tags=["documents"])
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOADED_DOCUMENTS_DIR = PROJECT_ROOT / "uploads" / "documents"
UPLOAD_READ_CHUNK_BYTES = 512 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MIN_EXTRACTED_TEXT_CHARS = 40
MAX_STORED_TEXT_CHARS = 200_000


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(request: Request, file: UploadFile = File(...)) -> DocumentUploadResponse:
    settings = get_settings()
    context = require_permission(request, "document:upload", settings)
    try:
        original_filename = _safe_display_filename(file.filename or "document")
        extension = Path(original_filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"Unsupported document type. Allowed extensions: {allowed}")

        max_bytes = settings.document_max_bytes
        if file.size is not None and file.size > max_bytes:
            raise ValueError(f"Document is too large. Maximum size is {max_bytes // (1024 * 1024)} MB")

        spooled_path, spooled_size, content_digest = await _spool_upload_limited(file, max_bytes)
        if not spooled_size:
            raise ValueError("Uploaded document is empty")

        try:
            text = _extract_text(spooled_path, extension)
        finally:
            spooled_path.unlink(missing_ok=True)
        if len(text.strip()) < MIN_EXTRACTED_TEXT_CHARS:
            raise ValueError("Document text is too short or could not be extracted")

        document_dir = project_storage_path(
            UPLOADED_DOCUMENTS_DIR,
            context.organization_id,
            context.project_id,
        )
        document_dir.mkdir(parents=True, exist_ok=True)
        document_id = _document_id(original_filename, content_digest, context.project_id)
        stored_filename = f"{document_id}.txt"
        stored_path = document_dir / stored_filename
        title = _title_from_text(text, original_filename)
        created_file = not stored_path.exists()
        if created_file:
            temporary_path = stored_path.with_name(f".{stored_filename}.{os.urandom(4).hex()}.tmp")
            try:
                temporary_path.write_text(
                    _stored_document_text(
                        title,
                        original_filename,
                        text,
                        context.organization_id,
                        context.project_id,
                        context.user.user_id if context.user else None,
                    ),
                    encoding="utf-8",
                )
                os.chmod(temporary_path, 0o600)
                temporary_path.replace(stored_path)
            finally:
                temporary_path.unlink(missing_ok=True)
        try:
            ownership = register_resource_ownership(
                context.organization_id,
                context.project_id,
                "document",
                document_id,
                context.user.user_id if context.user else None,
                database_path=settings.database_path,
            )
        except Exception:
            if created_file:
                stored_path.unlink(missing_ok=True)
            raise

        document = UploadedDocument(
            document_id=document_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            owner_user_id=ownership.owner_user_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            title=title,
            size_bytes=spooled_size,
            extracted_characters=len(text.strip()),
        )
        return DocumentUploadResponse(
            document=document,
            message="Document uploaded and added to the retrieval base",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=DocumentListResponse)
def list_documents(request: Request) -> DocumentListResponse:
    settings = get_settings()
    context = require_permission(request, "document:read", settings)
    document_dir = project_storage_path(
        UPLOADED_DOCUMENTS_DIR,
        context.organization_id,
        context.project_id,
    )
    ownerships = list_project_resource_ownerships(
        context.organization_id,
        context.project_id,
        "document",
        database_path=settings.database_path,
    )
    documents: list[UploadedDocument] = []
    for path in sorted(document_dir.glob("*.txt")) if document_dir.is_dir() else ():
        if path.is_symlink() or not path.is_file():
            continue
        ownership = ownerships.get(path.stem)
        if ownership is None:
            continue
        document = _document_from_path(path, context.organization_id, context.project_id)
        if document is not None:
            documents.append(document.model_copy(update={"owner_user_id": ownership.owner_user_id}))
    return DocumentListResponse(documents=documents)


async def _spool_upload_limited(file: UploadFile, max_bytes: int) -> tuple[Path, int, str]:
    """Stream the upload to disk and return its path, size and digest.

    The previous version accumulated the whole file in a list and then joined it,
    so peak memory was about twice the file size for every upload in flight.
    With a configurable ceiling of up to 100 MB, a handful of concurrent uploads
    was enough to exhaust the process. Video already streams to disk; documents
    now do the same.
    """
    digest = hashlib.sha256()
    total = 0
    handle = tempfile.NamedTemporaryFile(prefix="procedra-upload-", delete=False)
    spooled_path = Path(handle.name)
    try:
        with handle:
            while True:
                chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(
                        f"Document is too large. Maximum size is {max_bytes // (1024 * 1024)} MB"
                    )
                digest.update(chunk)
                handle.write(chunk)
    except BaseException:
        spooled_path.unlink(missing_ok=True)
        raise
    return spooled_path, total, digest.hexdigest()


def _extract_text(path: Path, extension: str) -> str:
    if extension in {".txt", ".md"}:
        # Text is decoded whole, but only after the size ceiling has been
        # enforced during spooling, and only for one document at a time.
        return _decode_text(path.read_bytes())
    if extension == ".pdf":
        return _extract_pdf_text(path)
    raise ValueError("Unsupported document type")


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode document text")


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF support requires the pypdf package") from exc

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages[:80]]
    except Exception as exc:
        raise ValueError("Unable to extract text from PDF") from exc
    return "\n\n".join(page.strip() for page in pages if page.strip())


def _document_id(filename: str, content_digest: str, project_id: str = "legacy") -> str:
    safe_stem = _safe_stem(Path(filename).stem)
    digest = hashlib.sha256(
        project_id.encode("utf-8") + b"\0" + content_digest.encode("utf-8")
    ).hexdigest()[:12]
    return f"{safe_stem}-{digest}"[:96].strip("-") or digest


def _safe_stem(value: str) -> str:
    transliterated = value.lower().replace("ё", "е")
    slug = re.sub(r"[^a-zа-я0-9]+", "-", transliterated, flags=re.IGNORECASE).strip("-")
    return slug or "document"


def _title_from_text(text: str, filename: str) -> str:
    for line in text.splitlines():
        stripped = line.strip(" #\t")
        if stripped:
            return stripped[:120]
    return Path(filename).stem[:120] or "Uploaded document"


def _stored_document_text(
    title: str,
    original_filename: str,
    text: str,
    organization_id: str = "legacy",
    project_id: str = "legacy",
    owner_user_id: str | None = None,
) -> str:
    compact_text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(compact_text) > MAX_STORED_TEXT_CHARS:
        compact_text = (
            compact_text[:MAX_STORED_TEXT_CHARS].rstrip()
            + "\n\n[Документ был сокращен при индексации: превышен лимит извлеченного текста.]"
        )
    return (
        f"# {title}\n\n"
        f"Original filename: {original_filename}\n"
        "Source kind: uploaded enterprise document\n\n"
        f"Organization ID: {organization_id}\n"
        f"Project ID: {project_id}\n"
        f"Owner user ID: {owner_user_id or ''}\n\n"
        f"{compact_text}\n"
    )


def _document_from_path(path: Path, organization_id: str, project_id: str) -> UploadedDocument | None:
    try:
        text = path.read_text(encoding="utf-8")
        stat = path.stat()
    except OSError:
        return None
    title = _title_from_text(text, path.name)
    original_filename = _metadata_value(text, "Original filename") or path.name
    metadata_matches_scope = (
        _metadata_value(text, "Organization ID") == organization_id
        and _metadata_value(text, "Project ID") == project_id
    )
    return UploadedDocument(
        document_id=path.stem,
        organization_id=organization_id,
        project_id=project_id,
        owner_user_id=_metadata_value(text, "Owner user ID") if metadata_matches_scope else None,
        original_filename=original_filename,
        stored_filename=path.name,
        title=title,
        size_bytes=stat.st_size,
        extracted_characters=max(0, len(text.strip())),
    )


def _metadata_value(text: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in text.splitlines()[:8]:
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            return value or None
    return None


def _safe_display_filename(value: str) -> str:
    decoded = unquote(value)
    compact = re.sub(r"[\x00-\x1f\x7f]+", " ", decoded).strip()
    compact = re.sub(r"\s{2,}", " ", compact)
    return compact[:180] or "document"
