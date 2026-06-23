from pydantic import BaseModel, Field


class UploadedDocument(BaseModel):
    document_id: str
    organization_id: str = Field(default="legacy", min_length=1, max_length=64)
    project_id: str = Field(default="legacy", min_length=1, max_length=64)
    owner_user_id: str | None = Field(default=None, max_length=64)
    original_filename: str
    stored_filename: str
    title: str
    size_bytes: int = Field(..., ge=0)
    extracted_characters: int = Field(..., ge=0)
    source_type: str = "uploaded_document"


class DocumentUploadResponse(BaseModel):
    document: UploadedDocument
    message: str


class DocumentListResponse(BaseModel):
    documents: list[UploadedDocument] = Field(default_factory=list)
