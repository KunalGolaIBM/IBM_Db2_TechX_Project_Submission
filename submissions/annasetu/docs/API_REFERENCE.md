# AnnaSetu API

FastAPI serves the API under `/api`. Interactive OpenAPI documentation is available at `/docs` while the API is running. JSON requests use `Content-Type: application/json`; protected endpoints require `Authorization: Bearer <access_token>` from `POST /api/auth/login`.

## Authentication and roles

| Role | Scope |
|---|---|
| `donor` | Create and view own food records; update own pre-allocation safety evidence; confirm pickup for own rescue batch. |
| `volunteer` | View assigned rescues; confirm the delivery/handoff checkpoint only for an assigned rescue; report an assigned rescue failure. |
| `ngo` | Review open food, allocate only to its own verified receiving profile, update its own capacity, and confirm its own distribution checkpoint. |
| `admin` | Operational override for verification, allocation, rescue checkpoints, capacity, and audit-chain verification. |

Checkpoint confirmation is stage-specific: `pickup` is recorded by the batch's donor, `delivery` by the assigned volunteer, and `distribution` by the receiving NGO. Administrators can override each stage. All checkpoints still require the correct one-time code and the next state in sequence. Wrong role or wrong owner returns `403`; a valid role attempting an out-of-order stage returns `409`.

## Routes

| Method and path | Access | Purpose / request |
|---|---|---|
| `GET /api/health` | Public | Runs a query on `SYSIBM.SYSDUMMY1`; reports the active Db2 server/database name, server time, and vector readiness. Db2 unavailable returns `503`. |
| `POST /api/auth/login` | Public | Body: `{"email":"…","password":"…"}`. Returns bearer token and profile; invalid credentials return `401`. |
| `POST /api/auth/demo-login` | Public, development only | Body: `{"role":"admin|donor|ngo|volunteer","password":"…"}`. Authenticates only that reserved role's Db2 demo identity; returns a role-only profile without its internal email or display name. Invalid credentials return `401`; returns `404` outside development. |
| `GET /api/auth/demo-accounts` | Public, development only | Returns only generic roles for reserved accounts actually present in Db2. It does not expose email addresses, names or password data. Returns `404` outside development. |
| `POST /api/auth/signup` | Public | Registers donor, NGO or volunteer. Body includes normalized email, name, password, confirmation and role-specific details. Returns a signed-in profile (`201`); duplicate email returns `409`; admin self-registration is not allowed. |
| `POST /api/auth/password-reset` | Public | Body: `{"email":"…"}`. Rate-limited and returns the same response for known and unknown accounts. In `development`, directs the requester to an administrator; no token is issued. Outside development, returns `recovery_mode: "unavailable"`. No email, SMS, SMTP, or external service is used. |
| `POST /api/auth/password-reset/admin-issue` | Admin | Body: `{"email":"…"}`. In development only, an authenticated Admin issues a six-digit code after verifying the person’s identity. The code is returned only to the admin UI, expires in five minutes, is rate-limited, stored as a keyed HMAC in Db2, and appended to the audit trail. |
| `POST /api/auth/password-reset/verify` | Public | Body: `{"token":"123456"}`. Checks the admin-approved code’s HMAC, expiry, unused state and rate limits in Db2. Only six-digit local codes are accepted. |
| `POST /api/auth/password-reset/confirm` | Public | Body: code, new password and confirmation. Atomically consumes the valid credential, changes the PBKDF2 password hash and appends an audit event. Used and expired codes cannot be reused. Local recovery is disabled outside development. |
| `GET /api/me` | Any signed-in user | Returns the token profile. |
| `GET /api/dashboard` | Any signed-in user | Db2 aggregates for donations, rescue stages, NGO performance, geography and 30-day trends. |
| `GET /api/food` | Any signed-in user | Lists food records scoped to the signed-in donor/NGO/volunteer where applicable. |
| `POST /api/food` | Donor, admin | Creates a batch and first append-only safety observation. Body follows `FoodCreate`: title, category, positive quantity, preparation/use-by timestamps, storage type/temperature, allergens, ingredients, pickup address/coordinates and storage note. Returns the created batch (`201`). |
| `GET /api/food/{batch_id}/passport` | Authorized participant/admin | Returns current batch, observations, human verification records and audit events. |
| `PATCH /api/food/{batch_id}/evidence` | Owner donor, admin | Appends a storage observation and resets human verification; evidence is locked after allocation (`409`). |
| `POST /api/food/{batch_id}/verify` | Verified NGO, admin | Body: decision `verified`, `hold` or `rejected`, plus review notes. Writes an immutable review record. |
| `GET /api/food/{batch_id}/evaluate` | Authorized participant | Returns `HOLD`, `INFEASIBLE` or `FEASIBLE`, reasons, declared remaining minutes, use-by and per-NGO distance/ETA/capacity assessment. |
| `POST /api/food/{batch_id}/allocate` | NGO, admin | Reserves eligible verified capacity in one Db2 transaction. Returns allocations, unallocated kg and one-time codes exactly once. Non-feasible or insufficient eligible capacity returns `409`. |
| `POST /api/rescues/{rescue_id}/confirm` | Stage actor, admin | Body: `{"stage":"pickup|delivery|distribution","otp":"six digits"}`; for `distribution`, also requires `actual_distributed_kg` (positive and no greater than allocated kg). Records actor, transition and Db2 timestamp. Wrong code returns `400`; wrong role `403`; wrong order `409`; invalid quantity returns `422`. |
| `POST /api/rescues/{rescue_id}/fail` | Assigned volunteer/NGO, admin | Body: a reason of 8–500 characters. Marks rescue failed, returns reserved capacity and appends an audit event. |
| `GET /api/rescues` | Any signed-in user | Lists rescue records with donor/NGO/volunteer scoping. |
| `GET /api/ngos` | Any signed-in user | Lists receiving profiles and available capacity. |
| `POST /api/ngos` | NGO, admin | Creates an unverified receiving profile. Body follows `NgoCreate`; an administrator must verify it before allocation. |
| `PATCH /api/ngos/{ngo_id}/capacity` | Profile owner NGO, admin | Body: non-negative `available_kg` and `active`. |
| `GET /api/policy/status` | Any signed-in user | Reports LangChain Db2 vector readiness. |
| `POST /api/policy/ask` | Any signed-in user | Body: 3–500 character question, optional batch ID. Returns retrieved source passages and official source links; optional batch context is deterministic and does not certify safety. Vector unavailable returns `503`. |
| `GET /api/audit/verify` | Admin | Recomputes the SHA-256 audit chain and returns validity and checked event count. |

## Validation and error handling

Pydantic models validate body fields, enumerations, ranges, timestamp ordering, OTP shape, and string/list lengths. Common responses are `401` unauthenticated/invalid login, `403` role or ownership denied, `404` missing resource, `409` invalid transition or unavailable capacity, `422` invalid request body, and `503` Db2/vector service unavailable. The frontend displays API `detail` responses and gives a connection-specific message when FastAPI cannot be reached.

## Data and safety behavior

- SQL uses bound parameters through `ibm_db_dbi`; operational records live in Db2.
- Allocation changes NGO capacity, creates rescue rows, and records audit events in one transaction. A failure rolls back the reservation.
- Food handoff OTPs are stored as SHA-256 digests and shown only to the allocation flow's designated actors. Password-recovery OTPs are returned only in development mode, stored as keyed HMAC digests, and never emailed or logged by that flow.
- Policy responses are assembled from retrieved Db2 passages. No generative model is configured; the cited passages are not official interpretation or food-safety certification.
