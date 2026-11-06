"""
User Management, Access Control, and Authentication Service for IBM Db2.
Supports Account Creation, Secure Login, Role Updates, Account Deletion,
and Security Question Password Recovery.
"""

import uuid
import hashlib
from typing import List, Dict, Any, Optional
from db.db2_client import db_client

class UserService:
    @staticmethod
    def _hash_str(val: str) -> str:
        if not val:
            return ""
        return hashlib.sha256(val.strip().encode('utf-8')).hexdigest()

    @staticmethod
    def _hash_answer(val: str) -> str:
        if not val:
            return ""
        # Lowercase and strip so user capitalization differences don't block recovery
        return hashlib.sha256(val.strip().lower().encode('utf-8')).hexdigest()

    @staticmethod
    def get_all_users() -> List[Dict[str, Any]]:
        sql = "SELECT user_id, username, full_name, role, email, status FROM USERS ORDER BY full_name"
        return db_client.query(sql)

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        if not username:
            return None
        sql = "SELECT * FROM USERS WHERE LOWER(username) = LOWER(?)"
        rows = db_client.query(sql, [username.strip()])
        return rows[0] if rows else None

    @staticmethod
    def get_user_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
        """Look up user by either username or email address (case-insensitive)."""
        if not identifier:
            return None
        ident = identifier.strip().lower()
        sql = "SELECT * FROM USERS WHERE LOWER(username) = ? OR LOWER(email) = ?"
        rows = db_client.query(sql, [ident, ident])
        return rows[0] if rows else None

    @staticmethod
    def authenticate(identifier: str, password: str) -> Dict[str, Any]:
        """
        Validates credentials via username or email against stored password hash.
        Returns concise, enterprise-standard error messages.
        """
        if not identifier or not password:
            return {"success": False, "error": "Please enter your username or email and password."}

        user = UserService.get_user_by_identifier(identifier)
        if not user:
            return {"success": False, "error": "Incorrect username or password."}

        entered_hash = UserService._hash_str(password)
        stored_hash = user.get("password_hash")

        if stored_hash and stored_hash == entered_hash:
            return {"success": True, "user": user}
        
        return {"success": False, "error": "Incorrect username or password."}

    @staticmethod
    def create_account(data: Dict[str, Any]) -> Dict[str, Any]:
        """Registers a new user with password and security question in IBM Db2."""
        username = data.get("username", "").strip()
        full_name = data.get("full_name", "").strip()
        password = data.get("password", "").strip()
        email = data.get("email", "").strip()
        role = data.get("role", "Kitchen Staff")
        question = data.get("security_question", "").strip()
        answer = data.get("security_answer", "").strip()

        if not username or not password or not full_name:
            return {"success": False, "error": "Full name, username, and password are required."}

        if len(password) < 4:
            return {"success": False, "error": "Password must be at least 4 characters long."}

        if not question or not answer:
            return {"success": False, "error": "Please select a security question and provide an answer."}

        existing_user = UserService.get_user_by_username(username)
        if existing_user:
            return {"success": False, "error": f"Username '{username}' is already taken. Please choose another."}

        if email:
            existing_email = UserService.get_user_by_identifier(email)
            if existing_email:
                return {"success": False, "error": f"Email '{email}' is already registered. Please sign in or use another email."}

        uid = f"USR_{uuid.uuid4().hex[:6].upper()}"
        pwd_hash = UserService._hash_str(password)
        ans_hash = UserService._hash_answer(answer)

        sql = """
        INSERT INTO USERS (user_id, username, full_name, role, email, status, password_hash, security_question, security_answer)
        VALUES (?, ?, ?, ?, ?, 'Active', ?, ?, ?)
        """
        success = db_client.execute(sql, [
            uid, username, full_name, role, email, pwd_hash, question, ans_hash
        ])

        if success:
            user = UserService.get_user_by_username(username)
            return {"success": True, "user": user}
        return {"success": False, "error": "Failed to create user account in IBM Db2."}

    @staticmethod
    def get_security_question(identifier: str) -> Optional[str]:
        user = UserService.get_user_by_identifier(identifier)
        if not user:
            return None
        return user.get("security_question") or "What is your secret security keyword?"

    @staticmethod
    def reset_password(identifier: str, answer: str, new_password: str) -> Dict[str, Any]:
        """Verifies security answer and updates password."""
        user = UserService.get_user_by_identifier(identifier)
        if not user:
            return {"success": False, "error": "Account not found."}

        if not new_password or len(new_password) < 4:
            return {"success": False, "error": "New password must be at least 4 characters long."}

        stored_ans = user.get("security_answer")
        entered_ans_hash = UserService._hash_answer(answer)

        is_match = False
        if stored_ans:
            if stored_ans == entered_ans_hash or stored_ans.strip().lower() == answer.strip().lower():
                is_match = True

        if not is_match:
            return {"success": False, "error": "Incorrect answer to security question."}

        new_pwd_hash = UserService._hash_str(new_password)
        sql = "UPDATE USERS SET password_hash = ? WHERE user_id = ?"
        success = db_client.execute(sql, [new_pwd_hash, user["user_id"]])

        if success:
            return {"success": True, "message": "Password updated successfully! You can now sign in."}
        return {"success": False, "error": "Failed to update password in IBM Db2."}

    @staticmethod
    def add_user(data: Dict[str, Any]) -> bool:
        """Admin helper to add team member."""
        res = UserService.create_account({
            "username": data.get("username"),
            "full_name": data.get("full_name"),
            "email": data.get("email", ""),
            "role": data.get("role", "Kitchen Staff"),
            "password": data.get("password") or "smartstock123",
            "security_question": "What is the organization name?",
            "security_answer": "smartstock"
        })
        return res.get("success", False)

    @staticmethod
    def update_user_role(user_id: str, new_role: str) -> bool:
        """Updates user role in IBM Db2."""
        sql = "UPDATE USERS SET role = ? WHERE user_id = ?"
        return db_client.execute(sql, [new_role, user_id])

    @staticmethod
    def delete_user(user_id: str) -> bool:
        """Deletes user from IBM Db2."""
        sql = "DELETE FROM USERS WHERE user_id = ?"
        return db_client.execute(sql, [user_id])
