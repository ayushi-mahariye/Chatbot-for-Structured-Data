from sqlalchemy import Column, String, Text, DateTime, UUID, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text)
    sql_query = Column(Text)
    results = Column(JSONB)
    explanation = Column(Text)
    username = Column(String(80))
    role = Column(String(50))
    outcome_status = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Feedback(Base):
    __tablename__ = "feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True))
    complexity_score = Column(String(10))
    intent_category = Column(String(100))
    reviewer = Column(String(80))
    feedback_comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False)
    db_role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    assigned_by = Column(String(80))
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())