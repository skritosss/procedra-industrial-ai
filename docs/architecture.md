# Architecture

```text
Input
  task description
  technical context
  user level
  local documentation
  local video file
  public video URL

Generation Pipeline
  optional hybrid embedding + keyword retrieval
  optional video metadata and subtitle extraction
  optional visual-stream download for keyframes
  optional frame-level vision analysis
  optional video-derived context construction
  prompt construction
  model call
  JSON parsing
  schema validation
  fallback on API or validation failure
  quality evaluation
  Markdown rendering

Output
  structured instruction
  quality evaluation
  retrieved sources
  extracted keyframes
  frame analysis
  video transcript/context
  markdown instruction

Packaging
  Docker runtime
  Docker Compose local demo
  GitHub Actions CI
```

The implementation keeps the pipeline modular. Text generation, retrieval, video text extraction, visual keyframe extraction, and evaluation can be tested independently before adding frame-level vision captions.

## Retrieval

Documentation retrieval uses a hybrid score. When OpenAI embeddings are configured, the retrieval layer builds an embedding bundle for the request and indexed chunks, then combines cosine similarity with IDF-weighted keyword overlap. If the external embedding call is disabled or unavailable, the same retrieval path falls back to deterministic local hashed embeddings. This keeps the system usable during offline demos while still supporting semantic RAG in production-like runs.

## Video Processing Split

Video URL processing deliberately separates:

- metadata and subtitle extraction, which does not need the visual stream;
- visual stream download, which uses the selected frame quality for keyframe extraction.

This avoids downloading high-resolution video for transcript-only work while still allowing better frames for future vision analysis.

## Frame Analysis

After keyframe extraction, each selected frame can be analyzed with the configured vision model. The analysis is intentionally conservative and records equipment, operator actions, safety observations, PPE observations, potential hazards, and uncertainties. When OpenAI vision is disabled or unavailable, the pipeline returns fallback records that tell the user which visual checks still need expert review.

## Reliability Behavior

The service falls back to a deterministic industrial template when:

- OpenAI is disabled with `OPENAI_ENABLED=false`.
- No API key is configured.
- The API returns an error.
- The model response is not valid JSON.
- The model response does not satisfy the instruction schema.

This keeps the API usable during local demos even when external API quota is unavailable.

## Packaging And CI

The Docker runtime installs the system packages needed by OpenCV and video processing, runs the FastAPI app as a non-root user, exposes `/health`, and stores generated frames, saved instruction versions, and uploads in writable directories. Docker Compose provides a repeatable local demo setup with named volumes. GitHub Actions runs Python compilation, the full test suite, and a Docker image build.
