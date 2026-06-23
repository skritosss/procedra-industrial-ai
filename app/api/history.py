from typing import cast

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.authorization import require_permission
from app.core.settings import get_settings
from app.schemas.history import (
    InstructionAuditTrail,
    InstructionExecutionList,
    InstructionExecutionSummary,
    InstructionHistoryDetail,
    InstructionHistoryList,
    SaveInstructionExecutionRequest,
    SaveInstructionExecutionResponse,
    SaveInstructionHistoryRequest,
    SaveInstructionHistoryResponse,
    UpdateInstructionWorkflowRequest,
    UpdateInstructionWorkflowResponse,
    ReviewerRole,
)
from app.storage.instruction_history import (
    get_instruction_audit_trail,
    get_instruction_history_detail,
    list_instruction_executions,
    list_instruction_history,
    save_instruction_execution,
    save_instruction_history,
    summarize_instruction_executions,
    update_instruction_workflow_status,
)


router = APIRouter(prefix="/instructions/history", tags=["instruction-history"])
@router.get("", response_model=InstructionHistoryList)
def list_saved_instructions(request: Request, limit: int = Query(default=50, ge=1, le=200)) -> InstructionHistoryList:
    context = require_permission(request, "instruction:read", get_settings())
    return InstructionHistoryList(
        records=list_instruction_history(
            limit=limit,
            organization_id=context.organization_id,
            project_id=context.project_id,
        )
    )


@router.get("/execution-summary", response_model=InstructionExecutionSummary)
def get_execution_summary(request: Request) -> InstructionExecutionSummary:
    context = require_permission(request, "execution:read", get_settings())
    return summarize_instruction_executions(
        organization_id=context.organization_id,
        project_id=context.project_id,
    )


@router.post("", response_model=SaveInstructionHistoryResponse)
def save_instruction_version(request: Request, payload: SaveInstructionHistoryRequest) -> SaveInstructionHistoryResponse:
    context = require_permission(request, "instruction:create", get_settings())
    user = context.user
    record = save_instruction_history(
        payload.payload,
        organization_id=context.organization_id,
        project_id=context.project_id,
        owner_user_id=user.user_id if user else None,
        actor=user.full_name if user else "system",
        actor_user_id=user.user_id if user else None,
        actor_role=user.role if user else None,
    )
    return SaveInstructionHistoryResponse(record=record, message="Instruction version saved")


@router.get("/{instruction_id}/versions/{version}", response_model=InstructionHistoryDetail)
def get_saved_instruction(instruction_id: str, version: int, request: Request) -> InstructionHistoryDetail:
    context = require_permission(request, "instruction:read", get_settings())
    detail = get_instruction_history_detail(
        instruction_id,
        version,
        organization_id=context.organization_id,
        project_id=context.project_id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Instruction version not found")
    return detail


@router.get("/{instruction_id}/versions/{version}/audit", response_model=InstructionAuditTrail)
def get_saved_instruction_audit(instruction_id: str, version: int, request: Request) -> InstructionAuditTrail:
    context = require_permission(request, "instruction:read", get_settings())
    trail = get_instruction_audit_trail(
        instruction_id,
        version,
        organization_id=context.organization_id,
        project_id=context.project_id,
    )
    if trail is None:
        raise HTTPException(status_code=404, detail="Instruction version not found")
    return trail


@router.patch("/{instruction_id}/versions/{version}/workflow", response_model=UpdateInstructionWorkflowResponse)
def update_saved_instruction_workflow(
    instruction_id: str,
    version: int,
    http_request: Request,
    request: UpdateInstructionWorkflowRequest,
) -> UpdateInstructionWorkflowResponse:
    context = require_permission(http_request, "workflow:review", get_settings())
    if request.status == "approved":
        require_permission(http_request, "workflow:approve", get_settings())
    user = context.user
    reviewer = request.reviewer
    reviewer_role = request.reviewer_role
    actor_user_id = None
    actor_role = None
    if user is not None:
        reviewer = user.full_name
        reviewer_role = cast(ReviewerRole, user.role)
        actor_user_id = user.user_id
        actor_role = user.role
    try:
        record = update_instruction_workflow_status(
            instruction_id=instruction_id,
            version=version,
            status=request.status,
            reviewer=reviewer,
            reviewer_role=reviewer_role,
            comment=request.comment,
            resolved_blockers=request.resolved_blockers,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            organization_id=context.organization_id,
            project_id=context.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Instruction version not found")
    return UpdateInstructionWorkflowResponse(record=record, message="Instruction workflow updated")


@router.get("/{instruction_id}/versions/{version}/execution", response_model=InstructionExecutionList)
def list_saved_instruction_executions(
    instruction_id: str,
    version: int,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> InstructionExecutionList:
    context = require_permission(request, "execution:read", get_settings())
    records = list_instruction_executions(
        instruction_id,
        version,
        limit=limit,
        organization_id=context.organization_id,
        project_id=context.project_id,
    )
    if records is None:
        raise HTTPException(status_code=404, detail="Instruction version not found")
    return InstructionExecutionList(records=records)


@router.post("/{instruction_id}/versions/{version}/execution", response_model=SaveInstructionExecutionResponse)
def save_saved_instruction_execution(
    instruction_id: str,
    version: int,
    http_request: Request,
    request: SaveInstructionExecutionRequest,
) -> SaveInstructionExecutionResponse:
    context = require_permission(http_request, "execution:create", get_settings())
    user = context.user
    executor = user.full_name if user is not None else request.executor
    try:
        record = save_instruction_execution(
            instruction_id=instruction_id,
            version=version,
            executor=executor,
            notes=request.notes,
            steps=request.steps,
            quality_items=request.quality_items,
            actor_user_id=user.user_id if user else None,
            actor_role=user.role if user else None,
            organization_id=context.organization_id,
            project_id=context.project_id,
            owner_user_id=user.user_id if user else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Instruction version not found")
    return SaveInstructionExecutionResponse(record=record, message="Instruction execution saved")
