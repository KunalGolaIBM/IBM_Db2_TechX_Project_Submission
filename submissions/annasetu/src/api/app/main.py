import hashlib
import json
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .audit import record_event, verify_chain
from .config import settings
from .models import CapacityUpdate, EvidenceUpdate, FoodCreate, LoginInput, NgoCreate, PolicyQuestion, RescueFailure, VerifyInput, VerifyStage
from .rag import ask_policy, ensure_policy_index, vector_status
from .schema import initialize_schema
from .security import decode_token, issue_token, password_matches
from .seed import DEMO_USERS, seed_database
from .services.safety import SafetyEvidence, estimate_distance_km, estimate_transit_minutes, evaluate_safety

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("annasetu")
bearer = HTTPBearer(auto_error=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters. Copy .env.example to .env and set a unique secret.")
    initialize_schema()
    if settings.seed_demo_data:
        seed_database()
    try:
        ready = ensure_policy_index()
        logger.info("Db2 policy vector index ready: %s", ready)
    except Exception:
        logger.exception("Db2 vector search initialization failed; policy retrieval will report unavailable")
    yield


app = FastAPI(title="AnnaSetu API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Sign in again.") from exc
    return {
        "user_id": payload["sub"], "email": payload["email"],
        "display_name": payload["name"], "role": payload["role"],
    }


def require_roles(*roles: str):
    def dependency(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="This action is not available for your role.")
        return user
    return dependency


def _dict(sql: str, params=(), conn=None):
    return db.row(sql, params, conn)


def _decode_json(value, fallback=None):
    if value is None:
        return fallback if fallback is not None else []
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback if fallback is not None else []


def _food_out(food: dict | None) -> dict | None:
    if not food:
        return None
    value = dict(food)
    value["batch_id"] = str(value["batch_id"]).strip()
    value["donor_id"] = str(value["donor_id"]).strip()
    value["allergens"] = _decode_json(value.get("allergens"))
    value["ingredients"] = _decode_json(value.get("ingredients"))
    value["human_verified"] = bool(value.get("human_verified"))
    value["allergens_confirmed"] = bool(value.get("allergens_confirmed"))
    return value


def _get_food(batch_id: str, conn=None):
    found = _dict("SELECT * FROM FOOD_BATCHES WHERE BATCH_ID=?", (batch_id,), conn)
    if not found:
        raise HTTPException(status_code=404, detail="Food batch not found.")
    return found


def _assert_food_access(food: dict, user: dict, conn=None):
    if user["role"] in {"admin", "donor"} and (user["role"] == "admin" or food["donor_id"].strip() == user["user_id"]):
        return
    if user["role"] == "volunteer":
        assignment = _dict(
            """SELECT R.RESCUE_ID FROM RESCUES R JOIN VOLUNTEERS V ON V.VOLUNTEER_ID=R.VOLUNTEER_ID
               WHERE R.BATCH_ID=? AND V.USER_ID=? FETCH FIRST 1 ROW ONLY""",
            (food["batch_id"], user["user_id"]), conn,
        )
        if assignment:
            return
    if user["role"] == "ngo":
        if food["status"] in {"listed", "hold"}:
            profile = _dict(
                """SELECT NGO_ID FROM NGOS WHERE OWNER_USER_ID=? AND VERIFIED=1 AND ACTIVE=1
                   FETCH FIRST 1 ROW ONLY""",
                (user["user_id"],), conn,
            )
            if profile:
                return
        assignment = _dict(
            """SELECT R.RESCUE_ID FROM RESCUES R JOIN NGOS N ON N.NGO_ID=R.NGO_ID
               WHERE R.BATCH_ID=? AND N.OWNER_USER_ID=? FETCH FIRST 1 ROW ONLY""",
            (food["batch_id"], user["user_id"]), conn,
        )
        if assignment:
            return
    raise HTTPException(status_code=403, detail="You do not have access to this food passport.")


def _candidates(food: dict, user: dict, conn=None) -> list[dict]:
    ngos = db.rows("SELECT * FROM NGOS WHERE VERIFIED=1 AND ACTIVE=1 ORDER BY AVAILABLE_KG DESC", conn=conn)
    matches = []
    for ngo in ngos:
        if user["role"] == "ngo" and ngo["owner_user_id"].strip() != user["user_id"]:
            continue
        categories = [item.lower() for item in _decode_json(ngo["accepted_categories"])]
        storage = [item.strip().lower() for item in ngo["storage_capabilities"].split(",")]
        if food["category"].lower() not in categories or food["storage_type"].lower() not in storage:
            continue
        if float(ngo["available_kg"]) <= 0:
            continue
        eta = estimate_transit_minutes(float(food["latitude"]), float(food["longitude"]),
                                       float(ngo["latitude"]), float(ngo["longitude"]))
        evidence = SafetyEvidence(
            human_verified=bool(food["human_verified"]),
            verification_recorded=bool(food["verified_at"]),
            allergens_confirmed=bool(food["allergens_confirmed"]),
            storage_type=food["storage_type"],
            storage_temp_c=float(food["storage_temp_c"]) if food["storage_temp_c"] is not None else None,
            use_by=food["use_by"], transit_minutes=eta,
        )
        decision = evaluate_safety(evidence)
        matches.append({
            "ngo_id": ngo["ngo_id"].strip(), "name": ngo["name"],
            "available_kg": float(ngo["available_kg"]),
            "distance_km": round(estimate_distance_km(float(food["latitude"]), float(food["longitude"]),
                                        float(ngo["latitude"]), float(ngo["longitude"])), 1),
            "estimated_transit_minutes": eta, "feasibility": decision.status,
            "remaining_minutes": decision.remaining_minutes,
            "reasons": list(decision.reasons), "receiving_hours": ngo["receiving_hours"],
        })
    return sorted(matches, key=lambda item: item["estimated_transit_minutes"])


def _otp_hash(code: str) -> str:
    return hashlib.sha256(code.encode("ascii")).hexdigest()


@app.get("/api/health")
def health():
    try:
        result = db.row("SELECT CURRENT SERVER AS DATABASE_NAME, CURRENT TIMESTAMP AS DB_TIME FROM SYSIBM.SYSDUMMY1")
        return {"status": "ok", "database": "IBM Db2", "database_name": result["database_name"],
                "database_time": result["db_time"],
                "vector": vector_status()}
    except Exception as exc:
        logger.exception("Db2 health check failed")
        raise HTTPException(status_code=503, detail="IBM Db2 is unavailable.") from exc


@app.post("/api/auth/login")
def login(payload: LoginInput):
    user = _dict("SELECT USER_ID,EMAIL,DISPLAY_NAME,ROLE,PASSWORD_HASH FROM USERS WHERE LOWER(EMAIL)=LOWER(?)",
                 (payload.email.strip(),))
    if not user or not password_matches(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    profile = {key: user[key] for key in ("user_id", "email", "display_name", "role")}
    return {"access_token": issue_token(profile), "token_type": "bearer", "user": profile}


@app.get("/api/auth/demo-accounts")
def demo_accounts():
    if settings.environment != "development":
        raise HTTPException(status_code=404, detail="Not found.")
    records = db.rows(
        "SELECT LOWER(EMAIL) AS EMAIL,DISPLAY_NAME,ROLE FROM USERS WHERE LOWER(EMAIL) IN (?,?,?,?)",
        tuple(email.lower() for email in DEMO_USERS),
    )
    accounts = {row["email"].strip().lower(): row for row in records}
    return [
        {"email": email, "name": accounts[email]["display_name"], "role": accounts[email]["role"]}
        for email, (_, expected_role) in DEMO_USERS.items()
        if email in accounts and accounts[email]["role"] == expected_role
    ]


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


@app.get("/api/dashboard")
def dashboard(_: dict = Depends(current_user)):
    donated = _dict("SELECT COALESCE(SUM(QUANTITY_KG),0) AS TOTAL FROM FOOD_BATCHES") or {}
    stages = _dict("""SELECT
      COALESCE(SUM(CASE WHEN R.STATUS IN ('picked_up','delivered','distributed') THEN R.ALLOCATED_KG ELSE 0 END),0) AS COLLECTED_KG,
      COALESCE(SUM(CASE WHEN R.STATUS IN ('delivered','distributed') THEN R.ALLOCATED_KG ELSE 0 END),0) AS DELIVERED_KG,
      COALESCE(SUM(CASE WHEN R.STATUS='distributed' THEN
        COALESCE(JSON_VALUE(CAST(A.EVENT_DATA AS CLOB(4000)), '$.data.actual_distributed_kg'
          RETURNING DECIMAL(10,2) NULL ON EMPTY NULL ON ERROR),R.ALLOCATED_KG) ELSE 0 END),0) AS DISTRIBUTED_KG
      FROM RESCUES R LEFT JOIN AUDIT_EVENTS A ON A.ENTITY_TYPE='rescue' AND A.ENTITY_ID=R.RESCUE_ID
        AND A.EVENT_TYPE='DISTRIBUTION_CONFIRMED'""") or {}
    hold = _dict("SELECT COUNT(*) AS N FROM FOOD_BATCHES WHERE STATUS='hold'") or {}
    rescue = _dict("""SELECT SUM(CASE WHEN STATUS='failed' THEN 1 ELSE 0 END) AS FAILED_ATTEMPTS,
       COUNT(*) AS RESCUE_COUNT FROM RESCUES""") or {}
    ngo_performance = db.rows("""SELECT N.NGO_ID,N.NAME,N.AVAILABLE_KG,
       COALESCE(SUM(CASE WHEN R.STATUS='distributed' THEN
         COALESCE(JSON_VALUE(CAST(A.EVENT_DATA AS CLOB(4000)), '$.data.actual_distributed_kg'
           RETURNING DECIMAL(10,2) NULL ON EMPTY NULL ON ERROR),R.ALLOCATED_KG) ELSE 0 END),0) AS DISTRIBUTED_KG,
       COALESCE(SUM(CASE WHEN R.STATUS='failed' THEN 1 ELSE 0 END),0) AS FAILED_ATTEMPTS,
       COUNT(R.RESCUE_ID) AS TOTAL_RESCUES
       FROM NGOS N LEFT JOIN RESCUES R ON R.NGO_ID=N.NGO_ID
       LEFT JOIN AUDIT_EVENTS A ON A.ENTITY_TYPE='rescue' AND A.ENTITY_ID=R.RESCUE_ID
         AND A.EVENT_TYPE='DISTRIBUTION_CONFIRMED'
       GROUP BY N.NGO_ID,N.NAME,N.AVAILABLE_KG ORDER BY DISTRIBUTED_KG DESC""")
    geography = db.rows("""SELECT N.NAME,N.LATITUDE,N.LONGITUDE,N.AVAILABLE_KG,
       COALESCE(SUM(CASE WHEN R.STATUS IN ('allocated','picked_up') THEN R.ALLOCATED_KG ELSE 0 END),0) AS OPEN_DEMAND_KG
       FROM NGOS N LEFT JOIN RESCUES R ON R.NGO_ID=N.NGO_ID
       GROUP BY N.NAME,N.LATITUDE,N.LONGITUDE,N.AVAILABLE_KG ORDER BY OPEN_DEMAND_KG DESC""")
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    since = now - timedelta(days=30)
    created_batches = db.rows("SELECT CREATED_AT,QUANTITY_KG FROM FOOD_BATCHES WHERE CREATED_AT>=? ORDER BY CREATED_AT", (since,))
    distributed_rescues = db.rows("""SELECT F.CREATED_AT,
       COALESCE(JSON_VALUE(CAST(A.EVENT_DATA AS CLOB(4000)), '$.data.actual_distributed_kg'
         RETURNING DECIMAL(10,2) NULL ON EMPTY NULL ON ERROR),R.ALLOCATED_KG) AS ACTUAL_DISTRIBUTED_KG
       FROM RESCUES R
       JOIN FOOD_BATCHES F ON F.BATCH_ID=R.BATCH_ID
       LEFT JOIN AUDIT_EVENTS A ON A.ENTITY_TYPE='rescue' AND A.ENTITY_ID=R.RESCUE_ID
         AND A.EVENT_TYPE='DISTRIBUTION_CONFIRMED'
       WHERE F.CREATED_AT>=? AND R.STATUS='distributed' ORDER BY F.CREATED_AT""", (since,))
    trend = []
    for week in range(5):
        start = since + timedelta(days=week * 7)
        end = min(start + timedelta(days=7), now)
        week_rows = [item for item in created_batches if start <= item["created_at"] < end]
        week_rescues = [item for item in distributed_rescues if start <= item["created_at"] < end]
        trend.append({
            "label": start.strftime("%d %b"),
            "donated_kg": sum(float(item["quantity_kg"]) for item in week_rows),
            "distributed_kg": sum(float(item["actual_distributed_kg"]) for item in week_rescues),
        })
    return {
        "metrics": {"donated_kg":float(donated["total"] or 0),
                    "collected_kg":float(stages["collected_kg"] or 0),
                    "delivered_kg":float(stages["delivered_kg"] or 0),
                    "distributed_kg":float(stages["distributed_kg"] or 0),
                    "hold_batches":int(hold["n"] or 0)},
        "failed_attempts": int(rescue["failed_attempts"] or 0),
        "rescue_count": int(rescue["rescue_count"] or 0),
        "ngo_performance": ngo_performance,
        "geography": geography,
        "trend": trend,
    }


@app.get("/api/food")
def list_food(user: dict = Depends(current_user)):
    if user["role"] == "donor":
        records = db.rows("SELECT F.*,U.DISPLAY_NAME AS DONOR_NAME FROM FOOD_BATCHES F JOIN USERS U ON U.USER_ID=F.DONOR_ID WHERE F.DONOR_ID=? ORDER BY F.CREATED_AT DESC", (user["user_id"],))
    elif user["role"] == "volunteer":
        records = db.rows("""SELECT DISTINCT F.*,U.DISPLAY_NAME AS DONOR_NAME FROM FOOD_BATCHES F
          JOIN USERS U ON U.USER_ID=F.DONOR_ID JOIN RESCUES R ON R.BATCH_ID=F.BATCH_ID
          JOIN VOLUNTEERS V ON V.VOLUNTEER_ID=R.VOLUNTEER_ID WHERE V.USER_ID=? ORDER BY F.CREATED_AT DESC""",
          (user["user_id"],))
    else:
        records = db.rows("SELECT F.*,U.DISPLAY_NAME AS DONOR_NAME FROM FOOD_BATCHES F JOIN USERS U ON U.USER_ID=F.DONOR_ID ORDER BY F.CREATED_AT DESC")
    return [_food_out(record) for record in records]


@app.post("/api/food", status_code=201)
def create_food(payload: FoodCreate, user: dict = Depends(require_roles("donor", "admin"))):
    batch_id = str(uuid4())
    conn = db.connect()
    try:
        db.execute("""INSERT INTO FOOD_BATCHES
           (BATCH_ID,DONOR_ID,TITLE,CATEGORY,QUANTITY_KG,PREPARED_AT,USE_BY,STORAGE_TYPE,STORAGE_TEMP_C,
            ALLERGENS,ALLERGENS_CONFIRMED,INGREDIENTS,PICKUP_ADDRESS,LATITUDE,LONGITUDE,NOTES)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
           (batch_id,user["user_id"],payload.title,payload.category,payload.quantity_kg,payload.prepared_at,
            payload.use_by,payload.storage_type,payload.storage_temp_c,json.dumps(payload.allergens),
            int(payload.allergens_confirmed),json.dumps(payload.ingredients),payload.pickup_address,
            payload.latitude,payload.longitude,payload.notes),conn)
        db.execute("INSERT INTO SAFETY_OBSERVATIONS (OBSERVATION_ID,BATCH_ID,RECORDED_BY,TEMP_C,STORAGE_NOTE) VALUES (?,?,?,?,?)",
                   (str(uuid4()),batch_id,user["user_id"],payload.storage_temp_c,payload.storage_note),conn)
        record_event(conn,"food_batch",batch_id,"BATCH_CREATED",user["user_id"],
                     {"quantity_kg":payload.quantity_kg,"category":payload.category})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _food_out(_get_food(batch_id))


@app.get("/api/food/{batch_id}/passport")
def passport(batch_id: str, user: dict = Depends(current_user)):
    food = _get_food(batch_id)
    _assert_food_access(food, user)
    obs = db.rows("SELECT OBSERVATION_ID,RECORDED_BY,TEMP_C,STORAGE_NOTE,OBSERVED_AT FROM SAFETY_OBSERVATIONS WHERE BATCH_ID=? ORDER BY OBSERVED_AT", (batch_id,))
    verifications = db.rows("SELECT V.DECISION,V.NOTES,V.VERIFIED_AT,U.DISPLAY_NAME AS VERIFIER FROM HUMAN_VERIFICATIONS V JOIN USERS U ON U.USER_ID=V.VERIFIER_ID WHERE V.BATCH_ID=? ORDER BY V.VERIFIED_AT", (batch_id,))
    events = db.rows("""SELECT EVENT_ID,ENTITY_TYPE,ENTITY_ID,EVENT_TYPE,ACTOR_ID,EVENT_DATA,PREVIOUS_HASH,EVENT_HASH,CREATED_AT
       FROM AUDIT_EVENTS WHERE (ENTITY_TYPE='food_batch' AND ENTITY_ID=?) OR
       (ENTITY_TYPE='rescue' AND ENTITY_ID IN (SELECT RESCUE_ID FROM RESCUES WHERE BATCH_ID=?))
       ORDER BY EVENT_ID""", (batch_id,batch_id))
    return {"batch": _food_out(food), "observations": obs, "verifications": verifications, "audit_events": events}


@app.post("/api/food/{batch_id}/verify")
def verify_food(batch_id: str, payload: VerifyInput, user: dict = Depends(require_roles("admin", "ngo"))):
    conn = db.connect()
    try:
        food = _get_food(batch_id, conn)
        if user["role"] == "ngo":
            verified_profile = _dict("SELECT NGO_ID FROM NGOS WHERE OWNER_USER_ID=? AND VERIFIED=1 AND ACTIVE=1 FETCH FIRST 1 ROW ONLY", (user["user_id"],), conn)
            if not verified_profile:
                raise HTTPException(status_code=403, detail="Only a verified, active NGO account may record this review.")
        verification_id = str(uuid4())
        is_verified = payload.decision == "verified"
        db.execute("""INSERT INTO HUMAN_VERIFICATIONS (VERIFICATION_ID,BATCH_ID,VERIFIER_ID,DECISION,NOTES)
                      VALUES (?,?,?,?,?)""",
                   (verification_id,batch_id,user["user_id"],payload.decision,payload.notes),conn)
        db.execute("UPDATE FOOD_BATCHES SET HUMAN_VERIFIED=?,VERIFIED_BY=?,VERIFIED_AT=?,STATUS=? WHERE BATCH_ID=?",
                   (int(is_verified),user["user_id"],datetime.now(timezone.utc).replace(tzinfo=None),"listed" if is_verified else "hold",batch_id),conn)
        record_event(conn,"food_batch",batch_id,"HUMAN_VERIFICATION",user["user_id"],
                     {"decision":payload.decision,"verification_id":verification_id,"notes":payload.notes})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _food_out(_get_food(batch_id))


@app.patch("/api/food/{batch_id}/evidence")
def update_food_evidence(batch_id: str, payload: EvidenceUpdate, user: dict = Depends(require_roles("admin", "donor"))):
    conn = db.connect()
    try:
        food = _get_food(batch_id, conn)
        if user["role"] == "donor" and food["donor_id"].strip() != user["user_id"]:
            raise HTTPException(status_code=403, detail="You can update your own food records only.")
        existing = _dict("SELECT COUNT(*) AS N FROM RESCUES WHERE BATCH_ID=?", (batch_id,), conn)
        if int(existing["n"] or 0):
            raise HTTPException(status_code=409, detail="Safety evidence is locked after allocation. Record new observations with an administrator.")
        db.execute("""UPDATE FOOD_BATCHES SET STORAGE_TEMP_C=?,ALLERGENS=?,ALLERGENS_CONFIRMED=?,
                   HUMAN_VERIFIED=0,VERIFIED_BY=NULL,VERIFIED_AT=NULL,STATUS='hold' WHERE BATCH_ID=?""",
                   (payload.storage_temp_c,json.dumps(payload.allergens),int(payload.allergens_confirmed),batch_id),conn)
        db.execute("INSERT INTO SAFETY_OBSERVATIONS (OBSERVATION_ID,BATCH_ID,RECORDED_BY,TEMP_C,STORAGE_NOTE) VALUES (?,?,?,?,?)",
                   (str(uuid4()),batch_id,user["user_id"],payload.storage_temp_c,payload.storage_note),conn)
        record_event(conn,"food_batch",batch_id,"SAFETY_EVIDENCE_UPDATED",user["user_id"],
                     {"storage_temp_c":payload.storage_temp_c,"allergens_confirmed":payload.allergens_confirmed,
                      "note":payload.storage_note,"human_verification_reset":True})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _food_out(_get_food(batch_id))


@app.get("/api/food/{batch_id}/evaluate")
def evaluate_batch(batch_id: str, user: dict = Depends(current_user)):
    food = _get_food(batch_id)
    _assert_food_access(food,user)
    now = datetime.now(timezone.utc)
    use_by = food["use_by"]
    expiry = use_by.replace(tzinfo=timezone.utc) if use_by.tzinfo is None else use_by
    remaining_minutes = round((expiry - now).total_seconds() / 60)
    matches = _candidates(food,user)
    if remaining_minutes <= 0:
        return {"status":"INFEASIBLE","reasons":["The declared use-by time has passed."],"candidates":matches,
                "remaining_minutes":remaining_minutes,"use_by":use_by}
    if not matches:
        return {"status":"HOLD","reasons":["No active, verified NGO has both matching category and storage capability."],
                "candidates":[],"remaining_minutes":remaining_minutes,"use_by":use_by}
    feasible = [item for item in matches if item["feasibility"] == "FEASIBLE"]
    if feasible:
        status_value = "FEASIBLE"
        reasons = ["At least one verified receiver has matching category, storage, capacity and an estimated trip before use-by."]
    else:
        status_value = "HOLD" if any(item["feasibility"] == "HOLD" for item in matches) else "INFEASIBLE"
        reasons = list(dict.fromkeys(reason for item in matches for reason in item["reasons"]))
    return {"status":status_value,"reasons":reasons,"candidates":matches,
            "remaining_minutes":remaining_minutes,"use_by":use_by,
            "estimate_label":"Travel time is straight-line distance at 20 km/h plus 15 minutes; actual routes vary."}


@app.post("/api/food/{batch_id}/allocate", status_code=201)
def allocate(batch_id: str, user: dict = Depends(require_roles("admin", "ngo"))):
    conn = db.connect()
    allocated = []
    try:
        food = _get_food(batch_id, conn)
        if food["status"] not in {"listed", "hold"}:
            raise HTTPException(status_code=409, detail="This batch has already entered a rescue workflow.")
        candidates = _candidates(food,user,conn)
        eligible = [item for item in candidates if item["feasibility"] == "FEASIBLE"]
        if not eligible:
            raise HTTPException(status_code=409, detail="No feasible, verified receiver is available. Keep the batch on HOLD.")
        volunteers = db.rows("SELECT VOLUNTEER_ID FROM VOLUNTEERS WHERE ACTIVE=1 ORDER BY CREATED_AT", conn=conn)
        if not volunteers:
            raise HTTPException(status_code=409, detail="No active volunteer is available to assign.")
        volunteer_id = volunteers[0]["volunteer_id"].strip()
        remaining = float(food["quantity_kg"])
        for candidate in eligible:
            if remaining <= 0:
                break
            amount = round(min(remaining,candidate["available_kg"]),2)
            if amount <= 0:
                continue
            reserved = db.execute("UPDATE NGOS SET AVAILABLE_KG=AVAILABLE_KG-? WHERE NGO_ID=? AND AVAILABLE_KG>=?",
                                  (amount,candidate["ngo_id"],amount),conn)
            if reserved != 1:
                continue
            pickup_code, delivery_code, distribution_code = (f"{secrets.randbelow(1_000_000):06d}" for _ in range(3))
            rescue_id = str(uuid4())
            db.execute("""INSERT INTO RESCUES (RESCUE_ID,BATCH_ID,NGO_ID,VOLUNTEER_ID,ALLOCATED_KG,
                 PICKUP_OTP_HASH,DELIVERY_OTP_HASH,DISTRIBUTION_OTP_HASH) VALUES (?,?,?,?,?,?,?,?)""",
                 (rescue_id,batch_id,candidate["ngo_id"],volunteer_id,amount,_otp_hash(pickup_code),
                  _otp_hash(delivery_code),_otp_hash(distribution_code)),conn)
            record_event(conn,"rescue",rescue_id,"RESCUE_ALLOCATED",user["user_id"],
                         {"batch_id":batch_id,"ngo_id":candidate["ngo_id"],"volunteer_id":volunteer_id,
                          "allocated_kg":amount,"estimated_transit_minutes":candidate["estimated_transit_minutes"]})
            allocated.append({"rescue_id":rescue_id,"ngo_id":candidate["ngo_id"],"ngo_name":candidate["name"],
                              "allocated_kg":amount,"volunteer_id":volunteer_id,
                              "estimated_transit_minutes":candidate["estimated_transit_minutes"],
                              "one_time_codes":{"pickup":pickup_code,"delivery":delivery_code,"distribution":distribution_code}})
            remaining = round(remaining-amount,2)
        if not allocated:
            raise HTTPException(status_code=409, detail="Capacity changed before reservation. Retry after refreshing NGO capacity.")
        db.execute("UPDATE FOOD_BATCHES SET STATUS='allocated' WHERE BATCH_ID=?",(batch_id,),conn)
        record_event(conn,"food_batch",batch_id,"BATCH_ALLOCATED",user["user_id"],
                     {"allocated_kg":round(float(food["quantity_kg"])-remaining,2),"unallocated_kg":remaining})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"batch_id":batch_id,"allocated":allocated,"allocated_kg":round(float(food["quantity_kg"])-remaining,2),
            "unallocated_kg":remaining,"codes_notice":"Codes are shown once. Share each code with the person receiving that handoff."}


@app.post("/api/rescues/{rescue_id}/confirm")
def confirm_rescue(rescue_id: str, payload: VerifyStage, user: dict = Depends(require_roles("admin", "donor", "volunteer", "ngo"))):
    conn = db.connect()
    try:
        rescue = _dict("SELECT * FROM RESCUES WHERE RESCUE_ID=?",(rescue_id,),conn)
        if not rescue:
            raise HTTPException(status_code=404,detail="Rescue assignment not found.")
        expected_role = {"pickup":"donor", "delivery":"volunteer", "distribution":"ngo"}[payload.stage]
        if user["role"] not in {"admin", expected_role}:
            raise HTTPException(status_code=403,detail=f"Only the {expected_role} or an administrator may confirm this checkpoint.")
        if user["role"] == "donor":
            food = _get_food(rescue["batch_id"].strip(),conn)
            if food["donor_id"].strip() != user["user_id"]:
                raise HTTPException(status_code=403,detail="This batch belongs to another donor.")
        if user["role"] == "volunteer":
            assigned = _dict("SELECT VOLUNTEER_ID FROM VOLUNTEERS WHERE USER_ID=?",(user["user_id"],),conn)
            if not assigned or assigned["volunteer_id"].strip() != rescue["volunteer_id"].strip():
                raise HTTPException(status_code=403,detail="This assignment belongs to another volunteer.")
        if user["role"] == "ngo":
            owner = _dict("SELECT OWNER_USER_ID FROM NGOS WHERE NGO_ID=?",(rescue["ngo_id"],),conn)
            if not owner or owner["owner_user_id"].strip() != user["user_id"]:
                raise HTTPException(status_code=403,detail="This assignment belongs to another NGO.")
        transitions = {
            "pickup": ("allocated","picked_up","PICKUP_OTP_HASH","PICKED_UP_AT"),
            "delivery": ("picked_up","delivered","DELIVERY_OTP_HASH","DELIVERED_AT"),
            "distribution": ("delivered","distributed","DISTRIBUTION_OTP_HASH","DISTRIBUTED_AT"),
        }
        expected, target, hash_column, timestamp_column = transitions[payload.stage]
        if rescue["status"] != expected:
            raise HTTPException(status_code=409,detail=f"{payload.stage.title()} confirmation is out of sequence.")
        actual_distributed_kg = payload.actual_distributed_kg
        if payload.stage == "distribution" and actual_distributed_kg > float(rescue["allocated_kg"]):
            raise HTTPException(status_code=422,detail="Actual distributed quantity cannot exceed the allocated quantity.")
        if not secrets.compare_digest(_otp_hash(payload.otp),rescue[hash_column.lower()].strip()):
            raise HTTPException(status_code=400,detail="The one-time code does not match.")
        db.execute(f"UPDATE RESCUES SET STATUS=?,{timestamp_column}=CURRENT TIMESTAMP WHERE RESCUE_ID=?",
                   (target,rescue_id),conn)
        record_event(conn,"rescue",rescue_id,f"{payload.stage.upper()}_CONFIRMED",user["user_id"],
                     {"batch_id":rescue["batch_id"].strip(),"ngo_id":rescue["ngo_id"].strip(),
                      "allocated_kg":float(rescue["allocated_kg"]),
                      **({"actual_distributed_kg":actual_distributed_kg} if payload.stage == "distribution" else {})})
        states = db.rows("SELECT STATUS FROM RESCUES WHERE BATCH_ID=?", (rescue["batch_id"].strip(),), conn)
        if states and all(item["status"] in {"distributed", "failed"} for item in states):
            aggregate = "distributed" if any(item["status"] == "distributed" for item in states) else "failed"
        elif any(item["status"] in {"delivered", "distributed"} for item in states):
            aggregate = "delivered"
        elif any(item["status"] == "picked_up" for item in states):
            aggregate = "picked_up"
        else:
            aggregate = "allocated"
        db.execute("UPDATE FOOD_BATCHES SET STATUS=? WHERE BATCH_ID=?", (aggregate, rescue["batch_id"].strip()), conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"rescue_id":rescue_id,"status":target,"stage":payload.stage,
            "actual_distributed_kg":actual_distributed_kg,"confirmed_at":datetime.now(timezone.utc)}


@app.post("/api/rescues/{rescue_id}/fail")
def fail_rescue(rescue_id: str, payload: RescueFailure, user: dict = Depends(require_roles("admin", "volunteer", "ngo"))):
    conn = db.connect()
    try:
        rescue = _dict("SELECT * FROM RESCUES WHERE RESCUE_ID=?",(rescue_id,),conn)
        if not rescue:
            raise HTTPException(status_code=404,detail="Rescue assignment not found.")
        if rescue["status"] in {"distributed", "failed"}:
            raise HTTPException(status_code=409,detail="This rescue is already closed.")
        if user["role"] == "volunteer":
            assigned = _dict("SELECT VOLUNTEER_ID FROM VOLUNTEERS WHERE USER_ID=?",(user["user_id"],),conn)
            if not assigned or assigned["volunteer_id"].strip() != rescue["volunteer_id"].strip():
                raise HTTPException(status_code=403,detail="This assignment belongs to another volunteer.")
        if user["role"] == "ngo":
            owner = _dict("SELECT OWNER_USER_ID FROM NGOS WHERE NGO_ID=?",(rescue["ngo_id"],),conn)
            if not owner or owner["owner_user_id"].strip() != user["user_id"]:
                raise HTTPException(status_code=403,detail="This assignment belongs to another NGO.")
        db.execute("UPDATE RESCUES SET STATUS='failed' WHERE RESCUE_ID=?",(rescue_id,),conn)
        db.execute("UPDATE NGOS SET AVAILABLE_KG=AVAILABLE_KG+? WHERE NGO_ID=?",
                   (float(rescue["allocated_kg"]),rescue["ngo_id"].strip()),conn)
        record_event(conn,"rescue",rescue_id,"RESCUE_FAILED",user["user_id"],
                     {"batch_id":rescue["batch_id"].strip(),"reason":payload.reason,
                      "capacity_released_kg":float(rescue["allocated_kg"])})
        states = db.rows("SELECT STATUS FROM RESCUES WHERE BATCH_ID=?",(rescue["batch_id"].strip(),),conn)
        if all(state["status"] in {"failed","distributed"} for state in states):
            batch_status = "distributed" if any(state["status"]=="distributed" for state in states) else "failed"
            db.execute("UPDATE FOOD_BATCHES SET STATUS=? WHERE BATCH_ID=?",
                       (batch_status,rescue["batch_id"].strip()),conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"rescue_id":rescue_id,"status":"failed","capacity_released_kg":float(rescue["allocated_kg"])}


@app.get("/api/ngos")
def list_ngos(_: dict = Depends(current_user)):
    records = db.rows("SELECT * FROM NGOS ORDER BY VERIFIED DESC,AVAILABLE_KG DESC")
    return [{**record,"ngo_id":record["ngo_id"].strip(),"owner_user_id":record["owner_user_id"].strip(),"verified":bool(record["verified"]),
             "active":bool(record["active"]),"accepted_categories":_decode_json(record["accepted_categories"]),
             "storage_capabilities":record["storage_capabilities"].split(",")} for record in records]


@app.post("/api/ngos", status_code=201)
def create_ngo(payload: NgoCreate, user: dict = Depends(require_roles("ngo", "admin"))):
    ngo_id = str(uuid4())
    db.execute("""INSERT INTO NGOS (NGO_ID,OWNER_USER_ID,NAME,AVAILABLE_KG,ACCEPTED_CATEGORIES,
       STORAGE_CAPABILITIES,LATITUDE,LONGITUDE,RECEIVING_HOURS) VALUES (?,?,?,?,?,?,?,?,?)""",
       (ngo_id,user["user_id"],payload.name,payload.available_kg,json.dumps(payload.accepted_categories),
        ",".join(payload.storage_capabilities),payload.latitude,payload.longitude,payload.receiving_hours))
    return {"ngo_id":ngo_id,"name":payload.name,"verified":False,"available_kg":payload.available_kg,
            "message":"Profile saved. An administrator must verify it before allocation."}


@app.patch("/api/ngos/{ngo_id}/capacity")
def update_capacity(ngo_id: str, payload: CapacityUpdate, user: dict = Depends(require_roles("admin", "ngo"))):
    ngo = _dict("SELECT * FROM NGOS WHERE NGO_ID=?",(ngo_id,))
    if not ngo:
        raise HTTPException(status_code=404,detail="NGO profile not found.")
    if user["role"] == "ngo" and ngo["owner_user_id"].strip() != user["user_id"]:
        raise HTTPException(status_code=403,detail="You can update your own NGO profile only.")
    db.execute("UPDATE NGOS SET AVAILABLE_KG=?,ACTIVE=? WHERE NGO_ID=?",
               (payload.available_kg,int(payload.active),ngo_id))
    return {"ngo_id":ngo_id,"available_kg":payload.available_kg,"active":payload.active}


@app.get("/api/rescues")
def list_rescues(user: dict = Depends(current_user)):
    sql = """SELECT R.RESCUE_ID,R.BATCH_ID,R.NGO_ID,N.NAME AS NGO_NAME,R.VOLUNTEER_ID,
      U.DISPLAY_NAME AS VOLUNTEER_NAME,R.ALLOCATED_KG,R.STATUS,R.PICKED_UP_AT,R.DELIVERED_AT,
      R.DISTRIBUTED_AT,R.CREATED_AT,F.TITLE AS FOOD_TITLE,
      (SELECT JSON_VALUE(CAST(A.EVENT_DATA AS CLOB(4000)), '$.data.actual_distributed_kg'
        RETURNING DECIMAL(10,2) NULL ON EMPTY NULL ON ERROR) FROM AUDIT_EVENTS A
       WHERE A.ENTITY_TYPE='rescue' AND A.ENTITY_ID=R.RESCUE_ID
         AND A.EVENT_TYPE='DISTRIBUTION_CONFIRMED' FETCH FIRST 1 ROW ONLY) AS ACTUAL_DISTRIBUTED_KG
      FROM RESCUES R JOIN NGOS N ON N.NGO_ID=R.NGO_ID JOIN VOLUNTEERS V ON V.VOLUNTEER_ID=R.VOLUNTEER_ID
      JOIN USERS U ON U.USER_ID=V.USER_ID JOIN FOOD_BATCHES F ON F.BATCH_ID=R.BATCH_ID"""
    params = ()
    if user["role"] == "volunteer":
        sql += " WHERE V.USER_ID=?"
        params = (user["user_id"],)
    elif user["role"] == "donor":
        sql += " WHERE F.DONOR_ID=?"
        params = (user["user_id"],)
    elif user["role"] == "ngo":
        sql += " WHERE N.OWNER_USER_ID=?"
        params = (user["user_id"],)
    sql += " ORDER BY R.CREATED_AT DESC"
    return db.rows(sql,params)


@app.get("/api/policy/status")
def policy_status(_: dict = Depends(current_user)):
    return vector_status()


@app.post("/api/policy/ask")
def policy_ask(payload: PolicyQuestion, user: dict = Depends(current_user)):
    if not vector_status()["ready"]:
        raise HTTPException(status_code=503,detail="IBM Db2 vector retrieval is not ready. Check API startup logs.")
    result = ask_policy(payload.question)
    if payload.batch_id:
        food = _get_food(payload.batch_id)
        _assert_food_access(food,user)
        candidates = _candidates(food,user)
        decisions = [candidate for candidate in candidates if candidate["feasibility"] == "FEASIBLE"]
        deterministic = "HOLD" if not decisions else "FEASIBLE for logistics only"
        result["batch_context"] = {
            "decision":deterministic,
            "reasons":list(dict.fromkeys(reason for item in candidates for reason in item["reasons"])) or ["No matching active receiver is available."],
            "note":"Policy retrieval cannot certify food safety; only a human verifier may approve the batch.",
        }
    return result


@app.get("/api/audit/verify")
def audit_verify(_: dict = Depends(require_roles("admin"))):
    return verify_chain()
