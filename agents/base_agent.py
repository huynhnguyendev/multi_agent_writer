"""
Base class chung cho tất cả các agent (Supervisor, Planner, Worker,
Synthesizer, Evaluator...).

Mỗi agent cụ thể sẽ kế thừa BaseAgent, chỉ cần khai báo:
    - prompt_name: tên file prompt trong agents/prompts/ (không .yaml)
    - model_role: key trong agents/models.py (MODEL_REGISTRY)
    - output_schema: Pydantic schema để validate output của LLM

"""

from typing import Type, TypeVar

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from agents.models import get_llm, get_model_config
from agents.prompts import get_system_prompt

T = TypeVar("T", bound=BaseModel)


class LLMOutputError(Exception):
    """Raise khi LLM không tạo ra được output hợp lệ sau khi đã retry."""


class BaseAgent:
    """Base class cho các agent dùng chung pattern: render prompt -> gọi LLM
    (structured output) -> trả về instance đã validate của output_schema."""

    def __init__(
        self,
        prompt_name: str,
        model_role: str,
        output_schema: Type[T],
        max_retries: int = 1,
    ):
        self.prompt_name = prompt_name
        self.model_role = model_role
        self.output_schema = output_schema
        self.max_retries = max_retries

        base_llm = get_llm(model_role)
        provider = get_model_config(model_role).provider

        # ====================================================
        # LƯU Ý QUAN TRỌNG: chọn method structured output theo provider.
        #
        # Gemini: dùng method mặc định ("function_calling") - hoạt động
        # ổn định qua langchain-google-genai.
        #
        # Groq (đặc biệt các model gpt-oss): method mặc định bị lỗi đã
        # biết của langchain-groq (model cố gọi 1 tool nội bộ tên "json"
        # do đặc thù Harmony format, nhưng tool đó không nằm trong
        # request.tools -> Groq server reject). Dùng method="json_mode"
        # (response_format: json_object, KHÔNG qua cơ chế tool-calling)
        # để né hẳn bug này - đây là tính năng ổn định, lâu đời hơn của
        # Groq API. Yêu cầu: prompt phải có chữ "JSON" trong nội dung
        # (các prompt hiện tại đều đã có dòng "Trả lời DUY NHẤT bằng
        # JSON..." nên đã thỏa điều kiện này).
        # ====================================================
        if provider == "groq":
            self.llm = base_llm.with_structured_output(output_schema, method="json_mode")
        else:
            self.llm = base_llm.with_structured_output(output_schema)

    # ========================================================
    # PUBLIC API
    # ========================================================

    async def run(self, **prompt_variables) -> T:
        """
        Render prompt với variables, gọi LLM bằng structured output.

        Raise LLMOutputError nếu sau khi retry vẫn thất bại (bao gồm cả
        lỗi validate từ các custom validator trong schema, ví dụ cycle
        detection ở Plan). Caller (node function) chịu trách nhiệm catch
        exception này và áp dụng chiến lược "bỏ qua và log lỗi" phù hợp.
        """
        prompt = get_system_prompt(self.prompt_name, **prompt_variables)

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await self.llm.ainvoke([HumanMessage(content=prompt)])

                if isinstance(result, self.output_schema):
                    return result
                if isinstance(result, dict):
                    return self.output_schema(**result)

                raise TypeError(
                    f"Kiểu kết quả không mong đợi từ structured output: {type(result)}"
                )

            except (ValidationError, TypeError, ValueError) as e:
                last_error = e
                print(
                    f"⚠️  [{self.__class__.__name__}] Lần thử {attempt + 1} "
                    f"thất bại: {e}"
                )
                continue
            except Exception as e:
                last_error = e
                print(
                    f"⚠️  [{self.__class__.__name__}] Lần thử {attempt + 1} "
                    f"gặp lỗi khi gọi LLM: {e}"
                )
                continue

        raise LLMOutputError(
            f"[{self.__class__.__name__}] Không tạo ra được output hợp lệ "
            f"sau {self.max_retries + 1} lần thử. Lỗi cuối: {last_error}"
        )