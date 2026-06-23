# Authorization and project ownership

Every stored document, instruction, and video belongs to one organization and
one project. The creator is recorded as the resource owner when available.
Execution evidence inherits the project boundary of its saved instruction.
Keyframes inherit the ownership of their video.

The default project id equals the organization id. Existing organization-scoped
data is migrated into that default project without moving or deleting files.
Authenticated clients may select another project with `X-Project-ID`, but the
API returns `404` unless the active user is a member of that project. Resource
lookups also return `404` when the resource belongs to another project or
organization, preventing identifier enumeration.

Schema version 7 also enforces these boundaries in SQLite. Membership rows must
reference a project and user from the same organization; resource ownership
must reference a project and, when present, an owner from that organization.
The controlled table rebuild validates legacy rows before changing the schema
and is fully transactional, so failed migrations leave the version 6 tables and
data intact.

Document listing never creates storage directories or ownership rows. It shows
only files that already have a matching organization/project ownership record;
retrieval and contextual generation apply the same allowlist, and filesystem
symlinks are ignored. Unregistered artifacts fail closed by remaining hidden
and unable to influence RAG. Legacy document
backfill is an explicit operator action through
`scripts/reconcile_document_ownership.py`: it is dry-run by default, validates
project paths, scope metadata, and owner tenancy, and applies a clean plan in
one transaction only with `--apply`.

## Permission matrix

| Action | Operator | Master | Technologist | Safety | Quality | Admin |
|---|---:|---:|---:|---:|---:|---:|
| Read documents/instructions/videos/executions | Yes | Yes | Yes | Yes | Yes | Yes |
| Create instructions, videos, and execution evidence | Yes | Yes | Yes | Yes | Yes | Yes |
| Upload enterprise documents | No | Yes | Yes | Yes | Yes | Yes |
| Review or reject workflow state | No | Yes | Yes | Yes | Yes | Yes |
| Final approval | No | No | Yes | Yes | Yes | Yes |
| Project administration | No | No | No | No | No | Yes |

Ownership never overrides role restrictions: an operator who created a resource
still cannot upload enterprise documents or change its workflow status. Project
members with the required role can collaborate on resources in that project.

Production requests require an authenticated user session. A static bootstrap
token alone cannot read or mutate organization/project resources. Demo mode
retains unauthenticated access only to the explicit `legacy` organization and
its default project.

## Browser and API session transport

Browser clients request cookie transport during registration, invitation
acceptance, and login; the current web UI does so for registration and login.
The session cookie is host-only, HttpOnly, SameSite=Strict, scoped to
`/`, and Secure in production. A separate readable SameSite=Strict CSRF cookie
is stored only as a SHA-256 hash bound to that server session. Every browser
`POST`, `PUT`, `PATCH`, or `DELETE` must send the same value in `X-CSRF-Token`;
missing, mismatched, forged, expired, or revoked values return `403
csrf_failed`. Invalid production session cookies are expired on `401`.

Demo mode omits the Secure attribute only so localhost HTTP remains usable.
Production mode always sets it. Neither session tokens nor the optional static
API token are persisted in browser `localStorage`; old stored values are removed
on page load.

Non-browser integrations remain backward compatible: auth endpoints without
`X-Auth-Transport: cookie` return a bearer token, and explicit bearer requests
do not require CSRF. When both transports are supplied, explicit bearer auth
takes precedence.

## Administrative lifecycle

The static bootstrap token can create only the first `admin` account and
organization. Bootstrap ownership is recorded in the admin audit trail. After
bootstrap, even an admin session cannot use public registration to create an
account. An active admin instead creates an expiring invitation bound to one
organization, one role, and optional non-default projects. The invitation token
is returned once, stored only as a hash, and can be accepted only once.

Admin-only APIs list organization users/projects/members, create projects,
change roles or activation state, and add or remove non-default project
memberships. Users always remain members of the organization default project;
removing that membership is rejected. Role changes and deactivation revoke all
existing sessions. An admin cannot demote or disable itself, and the last active
admin cannot be demoted or disabled.

Administrative lookups are organization-scoped. User, project, and invitation
identifiers from another organization return `404`. Invitation, role,
activation, project, and membership mutations are transactional and append an
immutable admin audit event. Responses under `/api/admin/` are marked
`Cache-Control: no-store`.
