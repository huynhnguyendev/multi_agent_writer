"""
Export toàn bộ schemas để tiện import từ 1 chỗ duy nhất.

Thay vì:
    from agents.schemas.user_request import UserRequest
    from agents.schemas.plan import Plan, Task

Có thể viết gọn:
    from agents.schemas import UserRequest, Plan, Task
"""

from agents.schemas.article import FinalArticle
from agents.schemas.evaluation import (
    ACCEPTANCE_THRESHOLD,
    MAX_REVISIONS,
    Evaluation,
)
from agents.schemas.guardrail import GuardrailCategory, GuardrailResult
from agents.schemas.hitl import HITLAction, HITLDecision
from agents.schemas.image import ImageCandidate, ImageSpec
from agents.schemas.plan import Plan, Task
from agents.schemas.research import ResearchResult, ResearchSource
from agents.schemas.state import WriterState
from agents.schemas.supervisor import ResearchMode, SupervisorDecision
from agents.schemas.user_request import UserRequest
from agents.schemas.worker import WorkerOutput, WorkerState

__all__ = [
    # user_request
    "UserRequest",
    # guardrail
    "GuardrailResult",
    "GuardrailCategory",
    # supervisor
    "SupervisorDecision",
    "ResearchMode",
    # plan
    "Plan",
    "Task",
    # hitl
    "HITLDecision",
    "HITLAction",
    # research
    "ResearchResult",
    "ResearchSource",
    # image
    "ImageSpec",
    "ImageCandidate",
    # worker
    "WorkerOutput",
    "WorkerState",
    # article
    "FinalArticle",
    # evaluation
    "Evaluation",
    "ACCEPTANCE_THRESHOLD",
    "MAX_REVISIONS",
    # state
    "WriterState",
]