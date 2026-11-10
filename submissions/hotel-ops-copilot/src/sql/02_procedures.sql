-- Hotel Ops Copilot - SQL PL stored procedures
-- The AI agent may only CALL SP_PROPOSE_ACTION. Applying, rejecting and
-- rolling back actions is reserved for the manager connection.

-- ---------------------------------------------------------------------------
-- SP_APPLY_ACTION: manager approves a pending action; Db2 enforces guardrails
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE SP_APPLY_ACTION (
    IN  P_ACTION_ID  INTEGER,
    IN  P_APPROVER   VARCHAR(40),
    OUT P_STATUS     VARCHAR(12),
    OUT P_MESSAGE    VARCHAR(1000)
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
    DECLARE V_BEFORE   TIMESTAMP(12);
    DECLARE V_TYPE     VARCHAR(20);
    DECLARE V_PAYLOAD  VARCHAR(4000);
    DECLARE V_STATE    VARCHAR(12);
    DECLARE V_CNT      INTEGER DEFAULT 0;
    DECLARE V_ROWS     INTEGER DEFAULT 0;
    DECLARE V_CODE     VARCHAR(8);
    DECLARE V_RT       SMALLINT;
    DECLARE V_START    DATE;
    DECLARE V_END      DATE;
    DECLARE V_RATE     DECIMAL(10,2);
    DECLARE V_FLOOR    DECIMAL(10,2);
    DECLARE V_CEIL     DECIMAL(10,2);
    DECLARE V_MAXCHG   DECIMAL(9,4);
    DECLARE V_RES      INTEGER;
    DECLARE V_IN       DATE;
    DECLARE V_OUT      DATE;
    DECLARE V_CUR_TIER SMALLINT;
    DECLARE V_NEW_TIER SMALLINT;
    DECLARE V_TO_RT    SMALLINT;
    DECLARE V_ROOM     VARCHAR(6);
    DECLARE V_OOO      VARCHAR(5);

    SET V_BEFORE = CURRENT TIMESTAMP(12);

    SELECT COUNT(*) INTO V_CNT FROM AGENT_ACTIONS WHERE ACTION_ID = P_ACTION_ID;
    IF V_CNT = 0 THEN
        SET P_STATUS = 'FAILED';
        SET P_MESSAGE = 'Action not found';
        RETURN;
    END IF;

    SELECT ACTION_TYPE, PAYLOAD, STATUS INTO V_TYPE, V_PAYLOAD, V_STATE
      FROM AGENT_ACTIONS WHERE ACTION_ID = P_ACTION_ID;

    IF V_STATE <> 'PENDING' THEN
        SET P_STATUS = V_STATE;
        SET P_MESSAGE = 'Action is not pending (status ' || V_STATE || ')';
        RETURN;
    END IF;

    SET P_STATUS = 'APPLIED';

    IF V_TYPE = 'RATE_CHANGE' THEN
        SET V_CODE  = JSON_VALUE(V_PAYLOAD, '$.room_type_code' RETURNING VARCHAR(8));
        SET V_START = JSON_VALUE(V_PAYLOAD, '$.start_date' RETURNING DATE);
        SET V_END   = JSON_VALUE(V_PAYLOAD, '$.end_date' RETURNING DATE);
        SET V_RATE  = JSON_VALUE(V_PAYLOAD, '$.new_rate' RETURNING DECIMAL(10,2));
        SELECT ROOM_TYPE_ID, FLOOR_RATE, CEILING_RATE INTO V_RT, V_FLOOR, V_CEIL
          FROM ROOM_TYPES WHERE CODE = V_CODE;
        SELECT MAX(ABS(V_RATE - RATE) / RATE) INTO V_MAXCHG
          FROM RATE_PLAN WHERE ROOM_TYPE_ID = V_RT AND STAY_DATE BETWEEN V_START AND V_END;
        IF V_START < CURRENT DATE THEN
            SET P_STATUS = 'FAILED';
            SET P_MESSAGE = 'Guardrail: cannot reprice dates in the past';
        ELSEIF V_RATE < V_FLOOR OR V_RATE > V_CEIL THEN
            SET P_STATUS = 'FAILED';
            SET P_MESSAGE = 'Guardrail: rate outside floor/ceiling band';
        ELSEIF V_MAXCHG > 0.35 THEN
            SET P_STATUS = 'FAILED';
            SET P_MESSAGE = 'Guardrail: change exceeds 35% of the current rate on at least one date';
        ELSE
            UPDATE RATE_PLAN
               SET RATE = V_RATE,
                   UPDATED_BY = P_APPROVER,
                   CHANGE_REASON = 'Approved agent action #' || TRIM(CHAR(P_ACTION_ID)),
                   SOURCE_ACTION_ID = P_ACTION_ID
             WHERE ROOM_TYPE_ID = V_RT AND STAY_DATE BETWEEN V_START AND V_END;
            GET DIAGNOSTICS V_ROWS = ROW_COUNT;
            SET P_MESSAGE = 'Repriced ' || TRIM(CHAR(V_ROWS)) || ' night(s) of ' || V_CODE
                            || ' to INR ' || TRIM(CHAR(V_RATE));
        END IF;

    ELSEIF V_TYPE = 'ROOM_UPGRADE' THEN
        SET V_RES  = JSON_VALUE(V_PAYLOAD, '$.reservation_id' RETURNING INTEGER);
        SET V_CODE = JSON_VALUE(V_PAYLOAD, '$.to_room_type_code' RETURNING VARCHAR(8));
        SELECT X.CHECK_IN, X.CHECK_OUT, RT.TIER INTO V_IN, V_OUT, V_CUR_TIER
          FROM RESERVATIONS X JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = X.ROOM_TYPE_ID
         WHERE X.RESERVATION_ID = V_RES;
        SELECT ROOM_TYPE_ID, TIER INTO V_TO_RT, V_NEW_TIER FROM ROOM_TYPES WHERE CODE = V_CODE;
        IF V_NEW_TIER <= V_CUR_TIER THEN
            SET P_STATUS = 'FAILED';
            SET P_MESSAGE = 'Guardrail: target room type is not an upgrade';
        ELSE
            SET V_ROOM = (
                SELECT R.ROOM_NO FROM ROOMS R
                 WHERE R.ROOM_TYPE_ID = V_TO_RT AND R.STATUS = 'IN_SERVICE'
                   AND NOT EXISTS (
                       SELECT 1 FROM RESERVATIONS X
                        WHERE X.ROOM_NO = R.ROOM_NO
                          AND X.STATUS IN ('CONFIRMED', 'CHECKED_IN')
                          AND X.CHECK_IN < V_OUT AND X.CHECK_OUT > V_IN)
                 ORDER BY R.ROOM_NO
                 FETCH FIRST 1 ROW ONLY);
            IF V_ROOM IS NULL THEN
                SET P_STATUS = 'FAILED';
                SET P_MESSAGE = 'No free ' || V_CODE || ' room for the whole stay';
            ELSE
                UPDATE RESERVATIONS
                   SET ROOM_TYPE_ID = V_TO_RT,
                       ROOM_NO = V_ROOM,
                       SPECIAL_NOTE = RTRIM(SUBSTR(COALESCE(SPECIAL_NOTE || '; ', '')
                                     || 'Complimentary upgrade (action #' || TRIM(CHAR(P_ACTION_ID)) || ')', 1, 400))
                 WHERE RESERVATION_ID = V_RES;
                SET P_MESSAGE = 'Reservation ' || TRIM(CHAR(V_RES)) || ' upgraded to ' || V_CODE
                                || ', room ' || V_ROOM;
            END IF;
        END IF;

    ELSEIF V_TYPE = 'MAINTENANCE' THEN
        SET V_ROOM = JSON_VALUE(V_PAYLOAD, '$.room_no' RETURNING VARCHAR(6));
        SET V_OOO  = LOWER(COALESCE(JSON_VALUE(V_PAYLOAD, '$.take_out_of_order' RETURNING VARCHAR(5)), 'false'));
        INSERT INTO MAINTENANCE_TICKETS (ROOM_NO, CATEGORY, PRIORITY, DESCRIPTION, SOURCE_ACTION_ID)
        VALUES (V_ROOM,
                COALESCE(JSON_VALUE(V_PAYLOAD, '$.category' RETURNING VARCHAR(30)), 'GENERAL'),
                JSON_VALUE(V_PAYLOAD, '$.priority' RETURNING VARCHAR(8)),
                COALESCE(JSON_VALUE(V_PAYLOAD, '$.description' RETURNING VARCHAR(1000)), 'Raised by Hotel Ops Copilot'),
                P_ACTION_ID);
        IF V_OOO = 'true' THEN
            UPDATE ROOMS SET STATUS = 'OUT_OF_ORDER' WHERE ROOM_NO = V_ROOM;
            SET P_MESSAGE = 'Ticket raised and room ' || V_ROOM || ' taken out of order';
        ELSE
            SET P_MESSAGE = 'Ticket raised for room ' || V_ROOM;
        END IF;
    END IF;

    UPDATE AGENT_ACTIONS
       SET STATUS = P_STATUS,
           DECIDED_BY = P_APPROVER,
           DECIDED_AT = CURRENT TIMESTAMP,
           APPLIED_AT = CASE WHEN P_STATUS = 'APPLIED' THEN V_BEFORE ELSE NULL END,
           RESULT_MESSAGE = P_MESSAGE
     WHERE ACTION_ID = P_ACTION_ID;
END
@

-- ---------------------------------------------------------------------------
-- SP_REJECT_ACTION
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE SP_REJECT_ACTION (
    IN  P_ACTION_ID  INTEGER,
    IN  P_APPROVER   VARCHAR(40),
    IN  P_REASON     VARCHAR(1000)
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
    UPDATE AGENT_ACTIONS
       SET STATUS = 'REJECTED', DECIDED_BY = P_APPROVER, DECIDED_AT = CURRENT TIMESTAMP,
           RESULT_MESSAGE = COALESCE(P_REASON, 'Rejected by manager')
     WHERE ACTION_ID = P_ACTION_ID AND STATUS = 'PENDING';
END
@

-- ---------------------------------------------------------------------------
-- SP_ROLLBACK_ACTION: undo an applied action using Db2 time travel
-- (FOR SYSTEM_TIME AS OF the instant before the action was applied)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE SP_ROLLBACK_ACTION (
    IN  P_ACTION_ID  INTEGER,
    IN  P_APPROVER   VARCHAR(40),
    OUT P_STATUS     VARCHAR(12),
    OUT P_MESSAGE    VARCHAR(1000)
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
    DECLARE V_TYPE    VARCHAR(20);
    DECLARE V_PAYLOAD VARCHAR(4000);
    DECLARE V_STATE   VARCHAR(12);
    DECLARE V_AT      TIMESTAMP(12);
    DECLARE V_CNT     INTEGER DEFAULT 0;
    DECLARE V_ROWS    INTEGER DEFAULT 0;
    DECLARE V_CODE    VARCHAR(8);
    DECLARE V_RT      SMALLINT;
    DECLARE V_START   DATE;
    DECLARE V_END     DATE;
    DECLARE V_RES     INTEGER;
    DECLARE V_ROOM    VARCHAR(6);

    SELECT COUNT(*) INTO V_CNT FROM AGENT_ACTIONS WHERE ACTION_ID = P_ACTION_ID;
    IF V_CNT = 0 THEN
        SET P_STATUS = 'FAILED';
        SET P_MESSAGE = 'Action not found';
        RETURN;
    END IF;

    SELECT ACTION_TYPE, PAYLOAD, STATUS, APPLIED_AT INTO V_TYPE, V_PAYLOAD, V_STATE, V_AT
      FROM AGENT_ACTIONS WHERE ACTION_ID = P_ACTION_ID;

    IF V_STATE <> 'APPLIED' OR V_AT IS NULL THEN
        SET P_STATUS = V_STATE;
        SET P_MESSAGE = 'Only APPLIED actions can be rolled back';
        RETURN;
    END IF;

    IF V_TYPE = 'RATE_CHANGE' THEN
        SET V_CODE  = JSON_VALUE(V_PAYLOAD, '$.room_type_code' RETURNING VARCHAR(8));
        SET V_START = JSON_VALUE(V_PAYLOAD, '$.start_date' RETURNING DATE);
        SET V_END   = JSON_VALUE(V_PAYLOAD, '$.end_date' RETURNING DATE);
        SELECT ROOM_TYPE_ID INTO V_RT FROM ROOM_TYPES WHERE CODE = V_CODE;
        SELECT COUNT(*) INTO V_CNT FROM RATE_PLAN
         WHERE ROOM_TYPE_ID = V_RT AND STAY_DATE BETWEEN V_START AND V_END
           AND COALESCE(SOURCE_ACTION_ID, -1) <> P_ACTION_ID;
        IF V_CNT > 0 THEN
            SET P_STATUS = 'APPLIED';
            SET P_MESSAGE = 'Cannot roll back: ' || TRIM(CHAR(V_CNT)) || ' night(s) were changed again after this action';
            RETURN;
        END IF;
        UPDATE RATE_PLAN T
           SET (RATE, UPDATED_BY, CHANGE_REASON, SOURCE_ACTION_ID) = (
               SELECT H.RATE, P_APPROVER, 'Rollback of action #' || TRIM(CHAR(P_ACTION_ID)), CAST(NULL AS INTEGER)
                 FROM RATE_PLAN FOR SYSTEM_TIME AS OF V_AT H
                WHERE H.ROOM_TYPE_ID = T.ROOM_TYPE_ID AND H.STAY_DATE = T.STAY_DATE)
         WHERE T.ROOM_TYPE_ID = V_RT AND T.STAY_DATE BETWEEN V_START AND V_END;
        GET DIAGNOSTICS V_ROWS = ROW_COUNT;
        SET P_MESSAGE = 'Restored ' || TRIM(CHAR(V_ROWS)) || ' night(s) of ' || V_CODE
                        || ' to their rates as of ' || VARCHAR_FORMAT(V_AT, 'YYYY-MM-DD HH24:MI:SS');

    ELSEIF V_TYPE = 'ROOM_UPGRADE' THEN
        SET V_RES = JSON_VALUE(V_PAYLOAD, '$.reservation_id' RETURNING INTEGER);
        UPDATE RESERVATIONS T
           SET (ROOM_TYPE_ID, ROOM_NO, SPECIAL_NOTE) = (
               SELECT H.ROOM_TYPE_ID, H.ROOM_NO, H.SPECIAL_NOTE
                 FROM RESERVATIONS FOR SYSTEM_TIME AS OF V_AT H
                WHERE H.RESERVATION_ID = T.RESERVATION_ID)
         WHERE T.RESERVATION_ID = V_RES;
        SET P_MESSAGE = 'Reservation ' || TRIM(CHAR(V_RES)) || ' restored to its pre-upgrade room';

    ELSEIF V_TYPE = 'MAINTENANCE' THEN
        SET V_ROOM = JSON_VALUE(V_PAYLOAD, '$.room_no' RETURNING VARCHAR(6));
        UPDATE MAINTENANCE_TICKETS SET STATUS = 'CANCELLED'
         WHERE SOURCE_ACTION_ID = P_ACTION_ID AND STATUS IN ('OPEN', 'IN_PROGRESS');
        UPDATE ROOMS T
           SET STATUS = (SELECT H.STATUS FROM ROOMS FOR SYSTEM_TIME AS OF V_AT H
                          WHERE H.ROOM_NO = T.ROOM_NO)
         WHERE T.ROOM_NO = V_ROOM;
        SET P_MESSAGE = 'Ticket cancelled and room ' || V_ROOM || ' status restored';
    END IF;

    SET P_STATUS = 'ROLLED_BACK';
    UPDATE AGENT_ACTIONS
       SET STATUS = 'ROLLED_BACK',
           RESULT_MESSAGE = RTRIM(SUBSTR(COALESCE(RESULT_MESSAGE, '') || ' | ROLLBACK by ' || P_APPROVER || ': ' || P_MESSAGE, 1, 1000))
     WHERE ACTION_ID = P_ACTION_ID;
END
@

-- ---------------------------------------------------------------------------
-- SP_PROPOSE_ACTION: validate an agent proposal, queue it as PENDING, and
-- apply it immediately only if a manager granted earned autonomy for it.
-- (Defined after SP_APPLY_ACTION because it calls it.)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE SP_PROPOSE_ACTION (
    IN  P_RUN_ID     VARCHAR(36),
    IN  P_TYPE       VARCHAR(20),
    IN  P_PAYLOAD    VARCHAR(4000),
    IN  P_RATIONALE  VARCHAR(2000),
    OUT P_ACTION_ID  INTEGER,
    OUT P_MESSAGE    VARCHAR(1000)
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
    DECLARE V_CNT    INTEGER DEFAULT 0;
    DECLARE V_CODE   VARCHAR(100);  -- wide on purpose: an over-long value must be REJECTED, not crash
    DECLARE V_START  DATE;
    DECLARE V_END    DATE;
    DECLARE V_RATE   DECIMAL(10,2);
    DECLARE V_FLOOR  DECIMAL(10,2);
    DECLARE V_CEIL   DECIMAL(10,2);
    DECLARE V_RES    INTEGER;
    DECLARE V_ROOM   VARCHAR(100);
    DECLARE V_PRIO   VARCHAR(100);
    DECLARE V_RT     SMALLINT;
    DECLARE V_PCT    DECIMAL(9,2);
    DECLARE V_MAXPCT DECIMAL(5,2);
    DECLARE V_LEAD   SMALLINT;
    DECLARE V_MAXPRI VARCHAR(8);
    DECLARE V_LIMIT  SMALLINT;
    DECLARE V_USED   INTEGER DEFAULT 0;
    DECLARE V_OOO    VARCHAR(100);
    DECLARE V_WHY    VARCHAR(300) DEFAULT '';
    DECLARE V_STATUS VARCHAR(12);
    DECLARE V_AMSG   VARCHAR(1000);

    SET P_ACTION_ID = 0;  -- 0 = no action created (avoids NULL OUT params in drivers)

    IF P_PAYLOAD IS NULL OR NOT JSON_EXISTS(P_PAYLOAD, '$') THEN
        SET P_MESSAGE = 'REJECTED: payload is not valid JSON';
        RETURN;
    END IF;

    IF P_TYPE = 'RATE_CHANGE' THEN
        SET V_CODE  = JSON_VALUE(P_PAYLOAD, '$.room_type_code' RETURNING VARCHAR(100));
        SET V_START = JSON_VALUE(P_PAYLOAD, '$.start_date' RETURNING DATE);
        SET V_END   = JSON_VALUE(P_PAYLOAD, '$.end_date' RETURNING DATE);
        SET V_RATE  = JSON_VALUE(P_PAYLOAD, '$.new_rate' RETURNING DECIMAL(10,2));
        IF V_CODE IS NULL OR V_START IS NULL OR V_END IS NULL OR V_RATE IS NULL THEN
            SET P_MESSAGE = 'REJECTED: RATE_CHANGE needs room_type_code, start_date, end_date, new_rate';
            RETURN;
        END IF;
        SELECT COUNT(*), MAX(FLOOR_RATE), MAX(CEILING_RATE) INTO V_CNT, V_FLOOR, V_CEIL
          FROM ROOM_TYPES WHERE CODE = V_CODE;
        IF V_CNT = 0 THEN
            SET P_MESSAGE = 'REJECTED: unknown room_type_code ' || V_CODE;
            RETURN;
        END IF;
        IF V_START < CURRENT DATE OR V_END < V_START OR V_END > CURRENT DATE + 90 DAYS THEN
            SET P_MESSAGE = 'REJECTED: date range must be within today .. today+90 and start <= end';
            RETURN;
        END IF;
        IF V_RATE < V_FLOOR OR V_RATE > V_CEIL THEN
            SET P_MESSAGE = 'REJECTED: new_rate ' || TRIM(CHAR(V_RATE)) || ' is outside the guardrail band '
                            || TRIM(CHAR(V_FLOOR)) || ' - ' || TRIM(CHAR(V_CEIL)) || ' for ' || V_CODE;
            RETURN;
        END IF;
    ELSEIF P_TYPE = 'ROOM_UPGRADE' THEN
        SET V_RES  = JSON_VALUE(P_PAYLOAD, '$.reservation_id' RETURNING INTEGER);
        SET V_CODE = JSON_VALUE(P_PAYLOAD, '$.to_room_type_code' RETURNING VARCHAR(100));
        SELECT COUNT(*) INTO V_CNT FROM RESERVATIONS
         WHERE RESERVATION_ID = V_RES AND STATUS IN ('CONFIRMED', 'CHECKED_IN');
        IF V_CNT = 0 THEN
            SET P_MESSAGE = 'REJECTED: reservation not found or not active';
            RETURN;
        END IF;
        -- consent check: the guest row must be visible to the caller AND consenting.
        -- For the agent, the GUEST_CONSENT_ROWS permission already hides opted-out guests.
        SELECT COUNT(*) INTO V_CNT FROM RESERVATIONS X JOIN GUESTS G ON G.GUEST_ID = X.GUEST_ID
         WHERE X.RESERVATION_ID = V_RES AND G.AI_CONSENT = 'Y';
        IF V_CNT = 0 THEN
            SET P_MESSAGE = 'REJECTED: guest has withdrawn consent for AI-assisted processing';
            RETURN;
        END IF;
        SELECT COUNT(*) INTO V_CNT FROM ROOM_TYPES WHERE CODE = V_CODE;
        IF V_CNT = 0 THEN
            SET P_MESSAGE = 'REJECTED: unknown to_room_type_code';
            RETURN;
        END IF;
    ELSEIF P_TYPE = 'MAINTENANCE' THEN
        SET V_ROOM = JSON_VALUE(P_PAYLOAD, '$.room_no' RETURNING VARCHAR(100));
        SET V_PRIO = JSON_VALUE(P_PAYLOAD, '$.priority' RETURNING VARCHAR(100));
        SELECT COUNT(*) INTO V_CNT FROM ROOMS WHERE ROOM_NO = V_ROOM;
        IF V_CNT = 0 THEN
            SET P_MESSAGE = 'REJECTED: unknown room_no';
            RETURN;
        END IF;
        IF V_PRIO IS NULL OR V_PRIO NOT IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT') THEN
            SET P_MESSAGE = 'REJECTED: priority must be LOW, MEDIUM, HIGH or URGENT';
            RETURN;
        END IF;
    ELSE
        SET P_MESSAGE = 'REJECTED: unknown action type ' || COALESCE(P_TYPE, 'NULL');
        RETURN;
    END IF;

    -- one pending proposal per identical payload
    SELECT COUNT(*) INTO V_CNT FROM AGENT_ACTIONS
     WHERE STATUS = 'PENDING' AND ACTION_TYPE = P_TYPE AND PAYLOAD = P_PAYLOAD;
    IF V_CNT > 0 THEN
        SET P_MESSAGE = 'DUPLICATE: an identical proposal is already pending';
        RETURN;
    END IF;

    INSERT INTO AGENT_ACTIONS (RUN_ID, ACTION_TYPE, PAYLOAD, RATIONALE, PROPOSED_BY)
    VALUES (P_RUN_ID, P_TYPE, P_PAYLOAD, P_RATIONALE, SESSION_USER);
    SET P_ACTION_ID = IDENTITY_VAL_LOCAL();
    SET P_MESSAGE = 'PENDING: action #' || TRIM(CHAR(P_ACTION_ID)) || ' queued for manager approval';

    -- -----------------------------------------------------------------------
    -- Earned autonomy: Db2 (not the agent) decides whether this action may be
    -- applied without a human, using limits only a manager can grant. It then
    -- runs the same guarded SP_APPLY_ACTION a manager would, so every guardrail
    -- still applies and the change can still be rolled back with time travel.
    -- -----------------------------------------------------------------------
    SELECT COUNT(*) INTO V_CNT FROM AUTONOMY_POLICY WHERE ACTION_TYPE = P_TYPE AND ENABLED = 'Y';
    IF V_CNT = 0 THEN
        RETURN;  -- no autonomy granted for this action type: a human decides
    END IF;
    SELECT MAX_CHANGE_PCT, MIN_LEAD_DAYS, MAX_PRIORITY, DAILY_LIMIT INTO V_MAXPCT, V_LEAD, V_MAXPRI, V_LIMIT
      FROM AUTONOMY_POLICY WHERE ACTION_TYPE = P_TYPE;
    SELECT COUNT(*) INTO V_USED FROM AGENT_ACTIONS
     WHERE DECIDED_BY = 'autonomy' AND STATUS = 'APPLIED' AND DATE(DECIDED_AT) = CURRENT DATE;  -- rolled-back ones don't count

    IF V_USED >= V_LIMIT THEN
        SET V_WHY = 'daily autonomy budget of ' || TRIM(CHAR(V_LIMIT)) || ' actions is used up';
    ELSEIF P_TYPE = 'RATE_CHANGE' THEN
        SELECT ROOM_TYPE_ID INTO V_RT FROM ROOM_TYPES WHERE CODE = V_CODE;
        SELECT MAX(ABS(V_RATE - RATE) * 100.0 / RATE) INTO V_PCT
          FROM RATE_PLAN WHERE ROOM_TYPE_ID = V_RT AND STAY_DATE BETWEEN V_START AND V_END;
        IF V_START < CURRENT DATE + COALESCE(V_LEAD, 0) DAYS THEN
            SET V_WHY = 'nights within ' || TRIM(CHAR(V_LEAD)) || ' days need a human';
        ELSEIF V_PCT IS NULL OR V_PCT > V_MAXPCT THEN
            SET V_WHY = 'a ' || TRIM(CHAR(DECIMAL(COALESCE(V_PCT, 0), 9, 1))) || '% change exceeds the autonomous limit of '
                        || TRIM(CHAR(V_MAXPCT)) || '%';
        END IF;
    ELSEIF P_TYPE = 'MAINTENANCE' THEN
        SET V_OOO = LOWER(COALESCE(JSON_VALUE(P_PAYLOAD, '$.take_out_of_order' RETURNING VARCHAR(100)), 'false'));
        IF V_OOO = 'true' THEN
            SET V_WHY = 'taking a room out of order always needs a human';
        ELSEIF CASE V_PRIO WHEN 'LOW' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'HIGH' THEN 3 ELSE 4 END
             > CASE V_MAXPRI WHEN 'LOW' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 0 END THEN
            SET V_WHY = V_PRIO || ' priority is above the autonomous limit of ' || COALESCE(V_MAXPRI, 'none');
        END IF;
    ELSE
        SET V_WHY = 'room upgrades always need a human';
    END IF;

    IF V_WHY <> '' THEN
        SET P_MESSAGE = P_MESSAGE || ' (not autonomous: ' || V_WHY || ')';
        RETURN;
    END IF;

    CALL HOTELOPS.SP_APPLY_ACTION(P_ACTION_ID, 'autonomy', V_STATUS, V_AMSG);
    IF V_STATUS = 'APPLIED' THEN
        SET P_MESSAGE = 'AUTO-APPLIED: action #' || TRIM(CHAR(P_ACTION_ID)) || ' under earned autonomy for ' || P_TYPE
                        || ' (manager can roll it back): ' || V_AMSG;
    ELSE
        SET P_MESSAGE = 'AUTONOMY BLOCKED BY GUARDRAIL: action #' || TRIM(CHAR(P_ACTION_ID)) || ' ' || V_STATUS || ': ' || V_AMSG;
    END IF;
END
@
