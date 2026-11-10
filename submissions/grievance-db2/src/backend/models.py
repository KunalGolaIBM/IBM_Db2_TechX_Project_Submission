from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Float,
    Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Department(Base):
    """
    Departments & Ministries managing public grievance redressal
    """
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    nodal_email = Column(String(150), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    grievances = relationship("Grievance", back_populates="department")

    def __repr__(self):
        return f"<Department(code='{self.code}', name='{self.name}')>"


class Grievance(Base):
    """
    Citizen Grievances stored in IBM Db2
    """
    __tablename__ = "grievances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tracking_id = Column(String(32), unique=True, nullable=False, index=True)
    citizen_name = Column(String(150), nullable=False)
    contact = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    description = Column(String(3000), nullable=False)
    ward = Column(String(100), nullable=True, index=True)
    priority = Column(String(20), nullable=False, default="Medium", index=True)
    status = Column(String(50), nullable=False, default="Filed", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)

    # AI Triage & Analytics Columns (LangChain Powered)
    ai_category = Column(String(50), nullable=True, index=True)
    ai_priority = Column(String(20), nullable=True, index=True)
    ai_summary = Column(String(255), nullable=True)

    # Contextual fields for rich portal interaction
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    subject = Column(String(255), nullable=True)
    state = Column(String(100), nullable=True, default="Delhi (NCT)")
    pincode = Column(String(10), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Relationships
    department = relationship("Department", back_populates="grievances")
    updates = relationship(
        "GrievanceUpdate",
        back_populates="grievance",
        cascade="all, delete-orphan",
        order_by="GrievanceUpdate.created_at.asc()"
    )

    __table_args__ = (
        Index("idx_grv_cat_status", "category", "status"),
        Index("idx_grv_ward_status", "ward", "status"),
    )

    def __repr__(self):
        return f"<Grievance(tracking_id='{self.tracking_id}', status='{self.status}', category='{self.category}')>"


class GrievanceUpdate(Base):
    """
    Audit log / status history timeline for grievances in IBM Db2
    """
    __tablename__ = "grievance_updates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    grievance_id = Column(Integer, ForeignKey("grievances.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    notes = Column(String(1000), nullable=True)
    updated_by = Column(String(100), nullable=False, default="System")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    grievance = relationship("Grievance", back_populates="updates")

    def __repr__(self):
        return f"<GrievanceUpdate(grievance_id={self.grievance_id}, {self.previous_status}->{self.new_status})>"
