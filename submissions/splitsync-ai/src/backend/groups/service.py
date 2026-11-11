"""Group management service."""

import logging
from typing import Optional

from db.repositories.group_repo import group_repo
from db.repositories.member_repo import member_repo
from db.repositories.user_repo import user_repo
from audit.service import audit_service
from api.middleware import AppError

logger = logging.getLogger(__name__)


class GroupService:
    """Handles group creation, updates, and member management."""

    def create_group(self, name: str, user_id: str, description: Optional[str] = None,
                     currency: str = "INR", split_method: str = "EQUAL") -> dict:
        """Create a new group and add the creator as admin."""
        group = group_repo.create_group(
            name=name,
            created_by=user_id,
            description=description,
            currency=currency,
            split_method=split_method,
        )
        if not group:
            raise AppError(500, "Failed to create group")

        # Add creator as admin
        member_repo.add_member(group["GROUP_ID"], user_id, role="ADMIN")

        audit_service.log(
            event_type="GROUP_CREATED",
            group_id=group["GROUP_ID"],
            actor_id=user_id,
            entity_type="GROUP",
            entity_id=group["GROUP_ID"],
            details={"name": name},
        )

        return self._format_group(group)

    def get_group(self, group_id: str, user_id: str) -> dict:
        """Get group details. User must be a member."""
        self._require_membership(group_id, user_id)
        group = group_repo.get_by_id(group_id)
        if not group:
            raise AppError(404, "Group not found")
        return self._format_group(group)

    def get_user_groups(self, user_id: str) -> list[dict]:
        """Get all groups for a user."""
        groups = group_repo.get_groups_for_user(user_id)
        return [self._format_group(g) for g in groups]

    def update_group(self, group_id: str, user_id: str, name: Optional[str] = None,
                     description: Optional[str] = None, status: Optional[str] = None) -> dict:
        """Update a group. Only admins can update."""
        self._require_admin(group_id, user_id)
        group = group_repo.update_group(group_id, name=name, description=description, status=status)
        if not group:
            raise AppError(404, "Group not found")

        audit_service.log(
            event_type="GROUP_UPDATED",
            group_id=group_id,
            actor_id=user_id,
            entity_type="GROUP",
            entity_id=group_id,
        )
        return self._format_group(group)

    def add_member(self, group_id: str, admin_user_id: str, member_email: str, role: str = "MEMBER") -> dict:
        """Add a member to a group by email. Only admins can add members."""
        self._require_admin(group_id, admin_user_id)

        target_user = user_repo.get_by_email(member_email.lower().strip())
        if not target_user:
            raise AppError(404, "User with this email not found. They must register first.")

        if member_repo.is_member(group_id, target_user["USER_ID"]):
            raise AppError(409, "User is already a member of this group")

        member = member_repo.add_member(group_id, target_user["USER_ID"], role)

        audit_service.log(
            event_type="MEMBER_ADDED",
            group_id=group_id,
            actor_id=admin_user_id,
            entity_type="MEMBER",
            entity_id=member["GROUP_MEMBER_ID"],
            details={"added_user": target_user["USER_ID"], "role": role},
        )

        return self._format_member(member)

    def get_members(self, group_id: str, user_id: str) -> list[dict]:
        """Get all members of a group. User must be a member."""
        self._require_membership(group_id, user_id)
        members = member_repo.get_members_of_group(group_id)
        return [self._format_member(m) for m in members]

    def remove_member(self, group_id: str, admin_user_id: str, member_id: str) -> None:
        """Remove a member from a group. Only admins can remove."""
        self._require_admin(group_id, admin_user_id)

        member = member_repo.get_by_id(member_id)
        if not member or member["GROUP_ID"] != group_id:
            raise AppError(404, "Member not found in this group")

        if member["USER_ID"] == admin_user_id:
            raise AppError(400, "Cannot remove yourself from the group")

        member_repo.remove_member(member_id)

        audit_service.log(
            event_type="MEMBER_REMOVED",
            group_id=group_id,
            actor_id=admin_user_id,
            entity_type="MEMBER",
            entity_id=member_id,
        )

    def get_current_member(self, group_id: str, user_id: str) -> dict:
        """Get the current user's membership record for a group."""
        member = member_repo.get_member_by_group_and_user(group_id, user_id)
        if not member:
            raise AppError(403, "You are not a member of this group")
        return self._format_member(member)

    def _require_membership(self, group_id: str, user_id: str) -> None:
        """Raise 403 if user is not a member of the group."""
        if not member_repo.is_member(group_id, user_id):
            raise AppError(403, "You are not a member of this group")

    def _require_admin(self, group_id: str, user_id: str) -> None:
        """Raise 403 if user is not an admin of the group."""
        if not member_repo.is_admin(group_id, user_id):
            raise AppError(403, "Only group admins can perform this action")

    def _format_group(self, group: dict) -> dict:
        """Format a raw Db2 group row to a response dict."""
        count = member_repo.get_member_count(group["GROUP_ID"])
        return {
            "group_id": group["GROUP_ID"],
            "name": group["NAME"],
            "description": group.get("DESCRIPTION"),
            "currency": group["CURRENCY"],
            "split_method": group["SPLIT_METHOD"],
            "accounting_mode": group["ACCOUNTING_MODE"],
            "status": group["STATUS"],
            "created_by": group["CREATED_BY"],
            "created_at": str(group.get("CREATED_AT", "")),
            "member_count": count,
        }

    def _format_member(self, member: dict) -> dict:
        """Format a raw Db2 member row to a response dict."""
        return {
            "group_member_id": member["GROUP_MEMBER_ID"],
            "group_id": member["GROUP_ID"],
            "user_id": member["USER_ID"],
            "display_name": member.get("DISPLAY_NAME", ""),
            "email": member.get("EMAIL", ""),
            "role": member["ROLE"],
            "status": member["STATUS"],
            "joined_at": str(member.get("JOINED_AT", "")),
        }


group_service = GroupService()
