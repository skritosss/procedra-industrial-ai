import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.evaluation.quality import evaluate_instruction_request
from app.generation.focus import focus_instruction_on_request
from app.generation.markdown import render_instruction_markdown
from app.generation.pdf import render_instruction_pdf
from app.generation.pipeline import generate_instruction, generate_instruction_with_context
from app.generation.quality_improver import improve_instruction_quality
from app.generation.video_links import link_steps_to_frames
from app.retrieval.local_index import retrieve_sources
from app.retrieval.local_index import UPLOADED_KNOWLEDGE_BASE
from app.core.authorization import (
    list_project_resource_ownerships,
    project_storage_path,
    require_permission,
    require_resource_access,
)
from app.core.organization import LEGACY_ORGANIZATION_ID
from app.core.settings import get_settings
from app.vision import keyframes as keyframe_storage
from app.schemas.instruction import (
    ContextGenerationRequest,
    EvaluationRequest,
    InstructionPayloadRequest,
    InstructionEvaluation,
    InstructionRequest,
    InstructionResponse,
    RetrievedSource,
    VideoInstructionRequest,
    WorkInstruction,
)


router = APIRouter(prefix="/instructions", tags=["instructions"])


@router.post("/generate", response_model=InstructionResponse)
def create_instruction(payload: InstructionRequest, request: Request) -> InstructionResponse:
    require_permission(request, "instruction:create", get_settings())
    return generate_instruction(payload)


@router.post("/generate-with-context", response_model=InstructionResponse)
def create_instruction_with_context(payload: ContextGenerationRequest, request: Request) -> InstructionResponse:
    require_permission(request, "instruction:create", get_settings())
    knowledge_base, document_ids = _uploaded_document_scope(request)
    return generate_instruction_with_context(payload, knowledge_base, document_ids)


@router.post("/generate-from-video", response_model=InstructionResponse)
def create_instruction_from_video(payload: VideoInstructionRequest, request: Request) -> InstructionResponse:
    require_permission(request, "instruction:create", get_settings())
    _validate_video_keyframe_ownership(payload, request)
    context_request = ContextGenerationRequest(
        task=payload.task,
        user_level=payload.user_level,
        instruction_type=payload.instruction_type,
        department=payload.department,
        equipment=payload.equipment,
        operation_name=payload.operation_name,
        industry_profile=payload.industry_profile,
        technical_context=_compact_video_context(payload.technical_context),
        max_sources=payload.max_sources,
    )
    knowledge_base, document_ids = _uploaded_document_scope(request)
    response = generate_instruction_with_context(context_request, knowledge_base, document_ids)
    response.step_frame_links = link_steps_to_frames(
        response.instruction,
        payload.frame_analyses,
        payload.keyframes,
        payload.video_segments,
    )
    response.markdown = render_instruction_markdown(response.instruction, response.step_frame_links)
    return response


def _validate_video_keyframe_ownership(payload: VideoInstructionRequest, request: Request) -> None:
    settings = get_settings()
    context = require_permission(request, "video:read", settings)
    if context.user is None:
        return
    organization_id = context.organization_id
    organization_segment = "" if organization_id == LEGACY_ORGANIZATION_ID else f"{organization_id}/"
    for keyframe in payload.keyframes:
        match = re.fullmatch(
            rf"/generated/keyframes/{re.escape(organization_segment)}([a-f0-9]{{32}})/(frame_[0-9]{{2}}\.jpg)",
            keyframe.image_url,
        )
        if match is None:
            raise HTTPException(status_code=400, detail="Video keyframe does not belong to the current organization")
        video_id, filename = match.groups()
        expected_relative = Path("generated") / "keyframes"
        if organization_id != LEGACY_ORGANIZATION_ID:
            expected_relative /= organization_id
        expected_relative = expected_relative / video_id / filename
        if Path(keyframe.image_path) != expected_relative:
            raise HTTPException(status_code=400, detail="Video keyframe path does not match its organization URL")
        expected_file = keyframe_storage.PROJECT_ROOT / expected_relative
        if not expected_file.is_file():
            raise HTTPException(status_code=400, detail="Video keyframe file does not exist")
        require_resource_access(
            context,
            "video",
            video_id,
            database_path=settings.database_path,
        )


@router.post("/retrieve", response_model=list[RetrievedSource])
def retrieve_instruction_sources(payload: ContextGenerationRequest, request: Request) -> list[RetrievedSource]:
    knowledge_base, document_ids = _uploaded_document_scope(request)
    return retrieve_sources(
        payload,
        uploaded_knowledge_base=knowledge_base,
        uploaded_document_ids=document_ids,
    )


def _uploaded_document_scope(request: Request) -> tuple[Path, frozenset[str]]:
    settings = get_settings()
    context = require_permission(request, "document:read", settings)
    knowledge_base = project_storage_path(
        UPLOADED_KNOWLEDGE_BASE,
        context.organization_id,
        context.project_id,
    )
    ownerships = list_project_resource_ownerships(
        context.organization_id,
        context.project_id,
        "document",
        database_path=settings.database_path,
    )
    return knowledge_base, frozenset(ownerships)


@router.post("/evaluate", response_model=InstructionEvaluation)
def evaluate_instruction(payload: EvaluationRequest, request: Request) -> InstructionEvaluation:
    require_permission(request, "instruction:create", get_settings())
    return evaluate_instruction_request(payload)


@router.post("/rebuild", response_model=InstructionResponse)
def rebuild_instruction_payload(body: InstructionPayloadRequest, request: Request) -> InstructionResponse:
    require_permission(request, "instruction:create", get_settings())
    payload = body.payload.model_copy(deep=True)
    payload.markdown = render_instruction_markdown(payload.instruction, payload.step_frame_links)
    payload.evaluation = evaluate_instruction_request(
        EvaluationRequest(instruction=payload.instruction, source_request=body.source_request)
    )
    return payload


@router.post("/improve", response_model=InstructionResponse)
def improve_instruction_payload(body: InstructionPayloadRequest, request: Request) -> InstructionResponse:
    require_permission(request, "instruction:create", get_settings())
    payload = body.payload.model_copy(deep=True)
    source_request = body.source_request or _source_request_from_instruction(payload.instruction)
    instruction = improve_instruction_quality(payload.instruction, source_request)
    instruction = focus_instruction_on_request(instruction, source_request)
    payload.instruction = instruction
    payload.markdown = render_instruction_markdown(instruction, payload.step_frame_links)
    payload.evaluation = evaluate_instruction_request(
        EvaluationRequest(instruction=instruction, source_request=source_request)
    )
    return payload


@router.post("/export-pdf")
def export_instruction_pdf(payload: InstructionResponse, request: Request) -> Response:
    require_permission(request, "instruction:read", get_settings())
    pdf = render_instruction_pdf(payload)
    filename = _safe_filename(payload.instruction.title, "pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="instruction.pdf"; filename*=UTF-8\'\'{quote(filename)}'},
    )


def _safe_filename(title: str, extension: str) -> str:
    slug = re.sub(r"[^A-Za-zА-Яа-яЁё0-9]+", "-", title).strip("-").lower()
    return f"{(slug or 'instruction')[:80]}.{extension}"


def _source_request_from_instruction(instruction: WorkInstruction) -> InstructionRequest:
    task = instruction.title.strip()
    if len(task) < 10:
        task = f"Доработать производственную инструкцию: {task or 'без названия'}"
    return InstructionRequest(
        task=task,
        department=instruction.department,
        equipment=instruction.equipment,
        technical_context="\n".join(
            [
                instruction.purpose,
                instruction.scope,
                *instruction.observed_facts,
                *instruction.local_verification_required,
            ]
        )[:12000],
    )


def _compact_video_context(context: str | None, max_chars: int = 12_000) -> str | None:
    if context is None or len(context) <= max_chars:
        return context
    marker = (
        "\n\n[Контекст видео был автоматически сокращен: сохранены начало, ключевые факты "
        "и финальные фрагменты. Полный транскрипт нужно проверять отдельно при внедрении.]\n\n"
    )
    if max_chars <= len(marker) + 200:
        return context[:max(1, max_chars - len(marker))].rstrip() + marker
    head_chars = min(8_000, max_chars // 2)
    tail_chars = max(1, max_chars - head_chars - len(marker))
    return context[:head_chars].rstrip() + marker + context[-tail_chars:].lstrip()
