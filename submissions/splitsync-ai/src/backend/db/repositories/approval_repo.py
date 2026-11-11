"""Repository for CASH_APPROVALS table operations."""

import uuid
from typing import Optional

from db.repositories.base import BaseRepository


class ApprovalRepository(BaseRepository):
    """Handles all Db2 operations for the CASH_APPROVALS table."""

    table_name = "CASH_APPROVALS"

    def record_approval(
        self,
        entity_type: str,
        entity_id: str,
        approver_member_id: str,
        decision: str,
        comment: Optional[str] = None,
    ) -> dict:
        """Record an approval or rejection decision."""
        approval_id = str(uuid.uuid4())
        sql = """
            INSERT INTO CASH_APPROVALS
            (APPROVAL_ID, ENTITY_TYPE, ENTITY_ID, APPROVER_MEMBER_ID, DECISION, COMMENT)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        self._insert(
            sql,
            (approval_id, entity_type.upper(), entity_id, approver_member_id, decision.upper(), comment),
        )
        return self.get_by_id(approval_id) or {}

    def get_by_id(self, approval_id: str) -> Optional[dict]:
        """Fetch approval record by ID."""
        sql = """
            SELECT a.APPROVAL_ID, a.ENTITY_TYPE, a.ENTITY_ID, a.APPROVER_MEMBER_ID,
                   a.DECISION, a.COMMENT, a.DECIDED_AT, u.DISPLAY_NAME, u.EMAIL
            FROM CASH_APPROVALS a
            INNER JOIN GROUP_MEMBERS gm ON a.APPROVER_MEMBER_ID = gm.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE a.APPROVAL_ID = ?
        """
        return self._fetch_one(sql, (approval_id,))

    def get_by_entity(self, entity_type: str, entity_id: str) -> Optional[dict]:
        """Fetch approval history for an entity."""
        sql = """
            SELECT a.APPROVAL_ID, a.ENTITY_TYPE, a.ENTITY_ID, a.APPROVER_MEMBER_ID,
                   a.DECISION, a.COMMENT, a.DECIDED_AT, u.DISPLAY_NAME, u.EMAIL
            FROM CASH_APPROVALS a
            INNER JOIN GROUP_MEMBERS gm ON a.APPROVER_MEMBER_ID = gm.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE a.ENTITY_TYPE = ? AND a.ENTITY_ID = ?
            ORDER BY a.DECIDED_AT DESC
            FETCH FIRST 1 ROWS ONLY
        """
        return self._fetch_one(sql, (entity_type.upper(), entity_id))

    def get_pending_approvals(self, group_id: str) -> list[dict]:
        """Union pending cash contributions and pending cash expenses for a group."""
        sql = """
            SELECT 'CASH_CONTRIBUTION' AS ENTITY_TYPE,
                   cc.CASH_CONTRIBUTION_ID AS ENTITY_ID,
                   cc.GROUP_ID,
                   cc.MEMBER_ID AS SUBMITTER_MEMBER_ID,
                   u.DISPLAY_NAME AS SUBMITTER_NAME,
                   cc.AMOUNT_MINOR,
                   cc.DESCRIPTION,
                   cc.STATUS,
                   cc.CREATED_AT
            FROM CASH_CONTRIBUTIONS cc
            INNER JOIN GROUP_MEMBERS gm ON cc.MEMBER_ID = gm.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE cc.GROUP_ID = ? AND cc.STATUS = 'PENDING_APPROVAL'

            UNION ALL

            SELECT 'EXPENSE' AS ENTITY_TYPE,
                   e.EXPENSE_ID AS ENTITY_ID,
                   e.GROUP_ID,
                   e.PAID_BY_MEMBER_ID AS SUBMITTER_MEMBER_ID,
                   u.DISPLAY_NAME AS SUBMITTER_NAME,
                   e.AMOUNT_MINOR,
                   e.DESCRIPTION,
                   e.STATUS,
                   e.CREATED_AT
            FROM EXPENSES e
            INNER JOIN GROUP_MEMBERS gm ON e.PAID_BY_MEMBER_ID = gm.GROUP_MEMBER_ID
            INNER JOIN APP_USERS u ON gm.USER_ID = u.USER_ID
            WHERE e.GROUP_ID = ? AND e.STATUS = 'PENDING_APPROVAL'
            ORDER BY CREATED_AT DESC
        """
        return self._fetch_all(sql, (group_id, group_id))


approval_repo = ApprovalRepository()
