"""Label-based access control (LBAC) on guest notes: Db2 mandatory access control for the AI.

Guest notes carry a Db2 security label: PUBLIC (preferences), INTERNAL (service history) or RESTRICTED
(medical and legal). The AI login holds the INTERNAL label for reading, so Db2 returns PUBLIC and INTERNAL
notes to it and silently hides RESTRICTED ones; managers hold RESTRICTED and see everything. Unlike the
RCAC permissions elsewhere, the rule lives in the labels themselves: the label component orders the levels,
the security policy enforces DB2LBACRULES, and only a separate security administrator (DB2_SECADM_USER) can
create labels or grant them. Db2 does not let an authorization ID grant labels to itself, which is why the
instance owner cannot do it alone.
"""
from __future__ import annotations

from hotelops.config import SCHEMA, load_settings
from hotelops.db import Db2, Db2Error

POLICY = "GUEST_NOTES_POLICY"  # security policies are not schema-qualified in Db2
LEVELS = ("RESTRICTED", "INTERNAL", "PUBLIC")  # highest first, as Db2 orders an ARRAY component

NOTES = [
    # (guest_id, level, category, note)
    (901, "PUBLIC", "PREFERENCE", "Prefers a sea-view room on a high floor and a late check-out."),
    (901, "INTERNAL", "SERVICE", "Complained twice about AC noise in room 307 on her last stay; comped one night."),
    (901, "RESTRICTED", "MEDICAL", "Severe tree-nut allergy: kitchen must be told before every meal."),
]
for g in range(3, 900, 9):
    NOTES.append((g, "PUBLIC", "PREFERENCE", ["Likes a quiet room away from the lift.", "Vegetarian breakfast.",
                                              "Early riser: asks for a 6 am wake-up call."][g % 3]))
    if g % 2:
        NOTES.append((g, "INTERNAL", "SERVICE", ["Late check-out granted last stay.",
                                                 "Raised a billing query, resolved.",
                                                 "Upgraded once for a delayed room."][g % 3]))
    if g % 5 == 0:
        NOTES.append((g, "RESTRICTED", ["MEDICAL", "LEGAL"][g % 2],
                      ["Uses a wheelchair: needs an accessible room.",
                       "Open chargeback dispute: refer to finance."][g % 2]))


def configured() -> bool:
    return bool(load_settings().db2.secadm_password)


def _secadm() -> Db2:
    s = load_settings().db2
    return Db2(s.conn_str(s.secadm_user, s.secadm_password), "lbac-secadm")


def teardown(admin: Db2) -> None:
    """Drop the protected table (manager), then the labels, policy and component (security administrator, since
    the instance owner may not revoke labels from itself either)."""
    s = load_settings().db2
    try:
        admin.execute(f"DROP TABLE {SCHEMA}.GUEST_NOTES")
    except Db2Error:
        pass
    stmts = [f"REVOKE SECURITY LABEL {POLICY}.RESTRICTED FROM USER {s.admin_user.upper()}",
             f"REVOKE EXEMPTION ON RULE DB2LBACWRITEARRAY WRITEDOWN FOR {POLICY} FROM USER {s.admin_user.upper()}",
             f"REVOKE SECURITY LABEL {POLICY}.INTERNAL FROM USER {s.agent_user.upper()}",
             *[f"DROP SECURITY LABEL {POLICY}.{lvl}" for lvl in LEVELS],
             f"DROP SECURITY POLICY {POLICY}", "DROP SECURITY LABEL COMPONENT GUEST_SENSITIVITY"]
    try:
        sec = _secadm() if configured() else admin
    except Db2Error:
        sec = admin
    try:
        for stmt in stmts:
            try:
                sec.execute(stmt)
            except Db2Error:
                pass
    finally:
        if sec is not admin:
            sec.close()


def setup(admin: Db2) -> int:
    """Create the labels (as the security administrator), then the protected table and its notes."""
    s = load_settings().db2
    admin.execute(f"GRANT CONNECT ON DATABASE TO USER {s.secadm_user.upper()}")
    admin.execute(f"GRANT SECADM ON DATABASE TO USER {s.secadm_user.upper()}")
    sec = _secadm()
    try:
        sec.execute("CREATE SECURITY LABEL COMPONENT GUEST_SENSITIVITY ARRAY ['RESTRICTED', 'INTERNAL', 'PUBLIC']")
        sec.execute(f"CREATE SECURITY POLICY {POLICY} COMPONENTS GUEST_SENSITIVITY WITH DB2LBACRULES "
                    "RESTRICT NOT AUTHORIZED WRITE SECURITY LABEL")
        for lvl in LEVELS:
            sec.execute(f"CREATE SECURITY LABEL {POLICY}.{lvl} COMPONENT GUEST_SENSITIVITY '{lvl}'")
        # managers: read everything, and write any level (exempt from the no-write-down rule)
        sec.execute(f"GRANT SECURITY LABEL {POLICY}.RESTRICTED TO USER {s.admin_user.upper()} FOR ALL ACCESS")
        sec.execute(f"GRANT EXEMPTION ON RULE DB2LBACWRITEARRAY WRITEDOWN FOR {POLICY} TO USER {s.admin_user.upper()}")
        # the AI: read up to INTERNAL, write nothing
        sec.execute(f"GRANT SECURITY LABEL {POLICY}.INTERNAL TO USER {s.agent_user.upper()} FOR READ ACCESS")
    finally:
        sec.close()
    owner = Db2(s.conn_str(s.admin_user, s.admin_password), "lbac-owner")  # LBAC credentials are read at connect
    try:
        owner.execute(f"""CREATE TABLE {SCHEMA}.GUEST_NOTES (
            NOTE_ID     INTEGER      NOT NULL PRIMARY KEY,
            GUEST_ID    INTEGER      NOT NULL REFERENCES {SCHEMA}.GUESTS,
            CATEGORY    VARCHAR(20)  NOT NULL,
            NOTE        VARCHAR(400) NOT NULL,
            SENSITIVITY DB2SECURITYLABEL NOT NULL
        ) SECURITY POLICY {POLICY}""")
        owner.execute(f"COMMENT ON TABLE {SCHEMA}.GUEST_NOTES IS 'Guest notes protected by Db2 LBAC: each row has a "
                      "PUBLIC, INTERNAL or RESTRICTED security label; the AI agent can read up to INTERNAL only.'")
        owner.bulk_insert(f"INSERT INTO {SCHEMA}.GUEST_NOTES (NOTE_ID, GUEST_ID, CATEGORY, NOTE, SENSITIVITY) "
                          "VALUES (?, ?, ?, ?, SECLABEL_BY_NAME('" + POLICY + "', ?))",
                          [(i + 1, g, cat, note, lvl) for i, (g, lvl, cat, note) in enumerate(NOTES)])
        # LBAC and RCAC combine: notes about guests who withdrew AI consent are hidden from the agent as well
        owner.execute(f"CREATE PERMISSION {SCHEMA}.GUEST_NOTES_CONSENT ON {SCHEMA}.GUEST_NOTES FOR ROWS WHERE "
                      "VERIFY_ROLE_FOR_USER(SESSION_USER, 'HOTELOPS_AGENT') = 0 OR GUEST_ID IN "
                      f"(SELECT G.GUEST_ID FROM {SCHEMA}.GUESTS G WHERE G.AI_CONSENT = 'Y') "
                      "ENFORCED FOR ALL ACCESS ENABLE")
        owner.execute(f"ALTER TABLE {SCHEMA}.GUEST_NOTES ACTIVATE ROW ACCESS CONTROL")
        owner.execute(f"GRANT SELECT ON {SCHEMA}.GUEST_NOTES TO ROLE HOTELOPS_AGENT")
    finally:
        owner.close()
    return len(NOTES)


def lbac_check() -> dict:
    """What the manager and the AI login each get from GUEST_NOTES, and what the AI is refused."""
    s = load_settings().db2
    admin = Db2(s.conn_str(s.admin_user, s.admin_password), "lbac-check-admin")
    agent = Db2(s.conn_str(s.agent_user, s.agent_password), "lbac-check-agent")
    count = (f"SELECT SECLABEL_TO_CHAR('{POLICY}', SENSITIVITY) AS LVL, COUNT(*) AS N "
             f"FROM {SCHEMA}.GUEST_NOTES GROUP BY SECLABEL_TO_CHAR('{POLICY}', SENSITIVITY)")
    try:
        out = {"manager": {r["LVL"]: r["N"] for r in admin.query(count)},
               "agent": {r["LVL"]: r["N"] for r in agent.query(count)},
               "vip_manager": [r["NOTE"] for r in admin.query(
                   f"SELECT NOTE FROM {SCHEMA}.GUEST_NOTES WHERE GUEST_ID = 901 ORDER BY NOTE_ID")],
               "vip_agent": [r["NOTE"] for r in agent.query(
                   f"SELECT NOTE FROM {SCHEMA}.GUEST_NOTES WHERE GUEST_ID = 901 ORDER BY NOTE_ID")]}
        opted_out = f"SELECT COUNT(*) FROM {SCHEMA}.GUEST_NOTES N JOIN {SCHEMA}.GUESTS G ON G.GUEST_ID = N.GUEST_ID " \
                    "WHERE G.AI_CONSENT = 'N'"
        out["manager_opted_out_notes"] = admin.scalar(opted_out)
        out["agent_opted_out_notes"] = agent.scalar(
            f"SELECT COUNT(*) FROM {SCHEMA}.GUEST_NOTES WHERE MOD(GUEST_ID, 40) = 0")  # the agent cannot see them
        try:
            agent.execute(f"UPDATE {SCHEMA}.GUEST_NOTES SET NOTE = 'x' WHERE 1 = 0")
            out["agent_can_write"] = True
        except Db2Error:
            out["agent_can_write"] = False
        return out
    finally:
        agent.close()
        admin.close()
