from app.models.user import User
from app.models.client import Client
from app.models.ticket import Ticket, TicketComment, TicketHistory
from app.models.sla import SLAPolicy
from app.models.escalation import EscalationRule, EscalationLog
from app.models.attendance import Attendance
from app.models.notification import Notification
# Phase 5 models
from app.models.knowledge_base import KnowledgeBaseArticle, KnowledgeBaseCategory
from app.models.time_tracking import TimeEntry
from app.models.custom_field import CustomField, CustomFieldValue
from app.models.api_token import ApiToken
