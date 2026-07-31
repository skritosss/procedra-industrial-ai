# Video and Computer Vision

The current video module accepts an uploaded video or a URL supported by `yt-dlp`, extracts high-value representative keyframes with OpenCV, analyzes selected frames, groups them into semantic video stages, stores the frames under `generated/keyframes/`, and returns browser-accessible image URLs.

For safety and local demo stability, video URLs must use `http://` or `https://`,
contain no credentials, encoded authority, ambiguous backslashes, or IPv6 zone
identifier, and every resolved IPv4/IPv6 address must be globally routable.
Local uploads plus URL downloads are limited by `VIDEO_MAX_BYTES`, duration is
bounded by `VIDEO_MAX_DURATION_SECONDS`, and network calls are bounded by
`VIDEO_NETWORK_TIMEOUT_SECONDS`.

All URL stages use one fail-closed egress policy. The initial URL and every
metadata, redirect, media CDN, manifest, fragment, and subtitle URL are checked
against `VIDEO_ALLOWED_HOSTS`; redirects are revalidated and DNS is resolved
again immediately before a connection. The socket connects to that validated
IP while retaining the original Host header and TLS SNI. Mixed public/private
answers, DNS rebinding to a private address, private/loopback/link-local IPv4 or
IPv6, unsupported transports, and external downloader paths are rejected.

`VIDEO_ALLOWED_HOSTS` is mandatory in production. Demo mode may leave it empty
to accept any fully public host. Subdomains are accepted, so operators must list
only provider domains they trust and include the specific CDN/caption domains
needed for their approved video source.

URL processing is split into two separate stages:

- text stage: title, description, subtitles, and transcript are read without downloading the visual stream;
- visual stage: a separate video-only stream is downloaded at the selected keyframe quality: `240p`, `360p`, `720p`, or `1080p`.

Multipart uploads are streamed to a tenant-scoped temporary file in bounded
chunks and atomically renamed only after the configured size limit and non-empty
checks pass. The primary UI path then persists a schema-v10 job and returns
`202 Accepted`; yt-dlp, OpenCV, and model work runs in a separate worker process.
The older synchronous routes remain available for API compatibility, but the UI
does not depend on a long-lived HTTP request.

This keeps speech/subtitle extraction fast while allowing the implemented vision
stage to analyze frames at the selected quality.

When `OPENAI_ENABLED=true` and an API key is configured, selected keyframes are analyzed by `OPENAI_VISION_MODEL`. When vision is disabled or unavailable, the API returns conservative fallback frame-analysis records instead of inventing visual details.

After frame analysis, the system builds `video_segments`: time-bounded semantic stages of the video. Each stage includes frame indices, a summary, dominant actions, visible equipment/objects, safety findings, and uncertainties. These stages are appended to the generation context so the instruction generator can reason over operation phases instead of isolated frames only.

## High-Value Frame Selection

The keyframe selector samples more candidate frames than requested and scores them before saving images. The score combines:

- scene change against the previous sampled frame;
- sharpness;
- contrast;
- brightness quality;
- visual distinctness from already selected frames.

Each returned keyframe includes `selection_score` and `selection_reason`, so the UI and JSON response explain why the frame was chosen.

## Durable job endpoints

```text
POST /api/videos/jobs
GET /api/videos/jobs/{job_id}
GET /api/videos/jobs/{job_id}/result
DELETE /api/videos/jobs/{job_id}
```

`POST` accepts the same upload/URL form fields described below and an optional
`Idempotency-Key` header. It returns `202` with a tenant/project-scoped job id,
status, coarse progress, attempt budget, and cancellation state. The status
response never returns the original URL, staged file path, lease owner, or raw
internal error. The result endpoint returns `409` until the job succeeds.

The worker atomically claims one queued job, renews a lease with a heartbeat,
recovers expired leases, retries bounded transient download failures, and checks
for cancellation throughout acquisition, extraction, analysis, and finalization.
Download, OpenCV extraction, and frame analysis each run in an isolated child
process with a configured hard deadline. The parent worker keeps the lease
heartbeat active and polls for cancellation or lease loss; any of those events
terminates the child's process group before the job state is changed. A timed-out
stage uses the public `processing_timeout` error and the existing bounded retry
budget. Partial staged/downloaded artifacts are removed when the job reaches a
terminal failure or cancellation state, and a completed result is never
published after cancellation.

The current Compose topology intentionally runs one worker, so video concurrency
is one per worker service. This is a single-host SQLite contract, not a
distributed multi-host queue. The older synchronous compatibility endpoints do
not use this subprocess contract and remain request-bound.

Run locally in a second terminal:

```bash
make video-worker
```

Docker Compose starts `video-job-worker` alongside the API and mounts the same
generated/upload volumes.

The 2026-07-16 daemon-backed drill killed the worker during
`extracting_keyframes`, observed the persisted lease remain on attempt 1, and
then observed a replacement worker reclaim only after lease expiry and complete
on attempt 2. The validated result contained 16 keyframes, 16 frame analyses,
and 6 semantic segments; API restart and force-recreate preserved the job and
artifacts in named volumes. Frame-derived context is capped at the response
schema's 12,000-character limit before persistence. This is single-host
recovery evidence only, not distributed queue or HA evidence.

A second isolated daemon drill on the same date verified the new hard stage
boundary. With a one-second extraction budget, a 90-second/50 MiB synthetic job
failed with `processing_timeout` about 1.1 seconds after extraction began and
left no staged artifact or child process. A separate running extraction was
cancelled in 0.18 seconds, its child process and artifact disappeared, and the
worker remained running. The normal isolated path then processed the same input
successfully in about 5.8 seconds with 8 keyframes, 8 analyses, and 6 segments.

## Compatibility endpoints

```text
POST /api/videos/keyframes
```

Multipart form fields:

- `file`: video file.
- `max_keyframes`: number of frames to extract, from 1 to 16.

```text
POST /api/videos/keyframes-from-url
```

Form fields:

- `video_url`: video URL.
- `max_keyframes`: number of frames to extract, from 1 to 16.
- `visual_quality`: frame extraction stream quality, one of `240`, `360`, `720`, `1080`.

Supported extensions:

- `.mp4`
- `.mov`
- `.avi`
- `.mkv`
- `.webm`
- `.m4v`

## Output

The response includes:

- video id;
- original filename;
- source URL, when available;
- frame count;
- FPS;
- duration;
- extracted keyframes with timestamps and image URLs;
- keyframe selection score and selection reason;
- per-keyframe frame analysis: visible equipment, operator actions, safety observations, PPE observations, potential hazards, and uncertainties;
- semantic video segments: time range, frame indices, dominant actions, equipment/objects, safety findings, and uncertainties;
- extracted text context from title, description, and subtitles/transcript when available;
- selected visual stream quality;
- notes if fewer frames were extracted than requested.

## What "Number of Frames" Means

This is the maximum number of representative keyframes the system extracts from the video. For example:

- `4`: quick overview;
- `8`: balanced default;
- `12` or `16`: more detailed visual coverage, but more noise and longer processing.

## Current Limitations

- URL support depends on `yt-dlp` and on whether the video is publicly accessible.
- Production URL support also depends on a complete explicit allowlist for the
  provider's webpage, media CDN, manifests/fragments, and subtitle hosts.
- Very long videos are rejected by `VIDEO_MAX_DURATION_SECONDS` before frame extraction when duration metadata is available, and again after OpenCV reads the stream.
- Vision analysis depends on API availability and selected frame quality.
- URL videos can generate a draft instruction from title, description, subtitles/transcript, semantic video stages, frame-analysis records, and keyframe timestamps.
- Local uploaded videos can generate a draft instruction from filename, semantic video stages, keyframe timestamps, and frame-analysis records.
- Real production use still requires expert review and approved documentation.
- Worker crash recovery, API/container persistence, hard stage timeout,
  cancellation, and the normal isolated path have daemon-backed single-host
  Compose evidence.
- The timeout/cancellation contract covers the primary queued job path only;
  synchronous compatibility routes remain request-bound.
- The SQLite contention probe is synthetic storage-level evidence, not a media
  throughput ceiling, multi-host test, or production load validation.

## Next Step

The next CV-specific improvement is stronger scene detection for long videos
and transcript-aware stage boundaries. Production hardening should first add
container/OS scanning, hash-locked transitive dependencies, and release SBOMs.
