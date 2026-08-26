"""
Cấu hình tập trung cho tất cả LLM models dùng trong project.

Mỗi "role" (vai trò node) map tới 1 model cụ thể. Muốn đổi model cho
1 node nào đó, chỉ cần sửa ở đây, không cần đụng vào code của agent.

Cách dùng:

    from agents.models import get_llm

    llm = get_llm("planner")       # -> ChatGoogleGenerativeAI (gemini-3.1-flash-lite)
    llm = get_llm("worker")        # -> ChatGroq (openai/gpt-oss-20b)
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


@dataclass
class ModelConfig:
    """Cấu hình cho 1 model cụ thể."""

    provider: str  # "groq" | "gemini"
    model_name: str
    temperature: float = 0.3


# ============================================================
# BẢNG CẤU HÌNH MODEL THEO TỪNG ROLE (theo bảng bạn đã chốt)
# ============================================================

MODEL_REGISTRY: dict[str, ModelConfig] = {
    "input_guardrails": ModelConfig(
        provider="groq",
        model_name="openai/gpt-oss-safeguard-20b",
        temperature=0.0,
    ),
    "supervisor": ModelConfig(
        provider="gemini",
        model_name="gemini-3.1-flash-lite",
        temperature=0.2,
    ),
    "planner": ModelConfig(
        provider="gemini",
        model_name="gemini-3.1-flash-lite",
        temperature=0.4,
    ),
    "worker": ModelConfig(
        provider="groq",
        model_name="openai/gpt-oss-20b",
        temperature=0.5,
    ),
    "research_worker": ModelConfig(
        provider="groq",
        model_name="openai/gpt-oss-20b",
        temperature=0.5,
    ),
    "synthesizer": ModelConfig(
        provider="gemini",
        model_name="gemini-3.5-flash-lite",
        temperature=0.5,
    ),
    "evaluator": ModelConfig(
        provider="gemini",
        model_name="gemini-3.1-flash-lite",
        temperature=0.0,
    ),
    "fallback": ModelConfig(
        provider="groq",
        model_name="openai/gpt-oss-120b",
        temperature=0.5,
    ),
}


def get_model_config(role: str) -> ModelConfig:
    """Lấy config model theo role. Raise lỗi rõ ràng nếu role không tồn tại."""
    if role not in MODEL_REGISTRY:
        raise ValueError(
            f"Role '{role}' không tồn tại trong MODEL_REGISTRY. "
            f"Các role hợp lệ: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[role]


def get_llm(role: str):
    """
    Trả về instance LLM (LangChain chat model) tương ứng với role.
    """
    config = get_model_config(role)

    if config.provider == "groq":
        return ChatGroq(
            model=config.model_name,
            temperature=config.temperature,
            api_key=GROQ_API_KEY,
        )

    if config.provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=config.model_name,
            temperature=config.temperature,
            google_api_key=GEMINI_API_KEY,
        )

    raise ValueError(f"Provider không được hỗ trợ: {config.provider}")