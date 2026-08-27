"""
Base class chung cho tất cả các agent (Supervisor, Planner, Worker,
Synthesizer, Evaluator...).

Mỗi agent cụ thể sẽ kế thừa BaseAgent, chỉ cần khai báo:
    - prompt_name: tên file prompt trong agents/prompts/ (không .yaml)
    - model_role: key trong agents/models.py (MODEL_REGISTRY)
    - output_schema: Pydantic schema để validate output JSON của LLM

Ví dụ dùng ở file planner.py sau này:

    class PlannerAgent(BaseAgent):
        def __init__(self):
            super().__init__(
                prompt_name="planner",
                model_role="planner",
                output_schema=Plan,
            )

    agent = PlannerAgent()
    plan = await agent.run(topic="...", tone="...", ...)
"""

import json
import re
from typing import Type, TypeVar

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from agents.models import get_llm
from agents.prompts import get_system_prompt

T = TypeVar("T", bound=BaseModel)


class LLMOutputError(Exception):
    """Raise khi LLM trả về output không parse/validate được sau khi đã retry."""


class BaseAgent:
    """Base class cho các agent dùng chung pattern: render prompt -> gọi LLM
    -> parse JSON -> validate bằng Pydantic schema."""

    def __init__(
        self,
        prompt_name: str,
        model_role: str,
        output_schema: Type[T],
        max_json_retries: int = 1,
    ):
        self.prompt_name = prompt_name
        self.model_role = model_role
        self.output_schema = output_schema
        self.max_json_retries = max_json_retries
        self.llm = get_llm(model_role)

    # ========================================================
    # PUBLIC API
    # ========================================================

    async def run(self, **prompt_variables) -> T:
        """
        Render prompt với variables, gọi LLM, parse + validate output.

        Raise LLMOutputError nếu sau khi retry vẫn không parse/validate được.
        Caller (node function) chịu trách nhiệm catch exception này và áp
        dụng chiến lược "bỏ qua và log lỗi" phù hợp với từng node.
        """
        prompt = get_system_prompt(self.prompt_name, **prompt_variables)

        last_error: Exception | None = None
        raw_text = ""

        for attempt in range(self.max_json_retries + 1):
            try:
                raw_text = await self._call_llm(prompt, retry_hint=(attempt > 0))
                json_data = self._extract_json(raw_text)
                return self.output_schema(**json_data)

            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_error = e
                print(
                    f"⚠️  [{self.__class__.__name__}] Lần thử {attempt + 1} "
                    f"thất bại: {e}"
                )
                continue

        raise LLMOutputError(
            f"[{self.__class__.__name__}] Không parse/validate được output "
            f"sau {self.max_json_retries + 1} lần thử. Lỗi cuối: {last_error}. "
            f"Raw output: {raw_text[:500]}"
        )

    # ========================================================
    # INTERNAL HELPERS
    # ========================================================

    async def _call_llm(self, prompt: str, retry_hint: bool = False) -> str:
        """Gọi LLM với prompt đã render, trả về raw text response."""
        content = prompt
        if retry_hint:
            content += (
                "\n\nLƯU Ý: Lần trả lời trước của bạn không đúng định dạng "
                "JSON yêu cầu. Hãy chỉ trả lời DUY NHẤT bằng JSON hợp lệ, "
                "không thêm bất kỳ văn bản, giải thích, hay markdown code "
                "fence nào khác."
            )

        response = await self.llm.ainvoke([HumanMessage(content=content)])
        return self._normalize_content(response.content)

    @staticmethod
    def _normalize_content(content) -> str:
        """
        Chuẩn hóa response.content về string thuần.

        Gemini (ChatGoogleGenerativeAI) đôi khi trả content dạng list
        các content block (ví dụ: [{"type": "text", "text": "..."}])
        thay vì str thuần như Groq. Hàm này gộp lại thành 1 string,
        bất kể provider nào.
        """
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    # Các dạng phổ biến: {"type": "text", "text": "..."}
                    text = block.get("text") or block.get("content") or ""
                    parts.append(text)
            return "".join(parts)

        return str(content)

    @staticmethod
    def _fix_invalid_escapes(text: str) -> str:
        r"""
        Sửa các backslash không hợp lệ trong JSON string.

        LLM (đặc biệt khi sinh markdown dài) đôi khi chèn backslash
        không thuộc bộ escape hợp lệ của JSON (chỉ có: \" \\ \/ \b \f
        \n \r \t \uXXXX). Ví dụ markdown dùng "\_" hoặc "\*" để escape
        ký tự đặc biệt sẽ làm json.loads() báo lỗi "Invalid \escape".

        Hàm này quét qua text, gặp backslash không theo sau bởi ký tự
        escape hợp lệ thì tự động escape lại backslash đó (thành \\),
        để JSON parser hiểu đó là 1 dấu backslash literal.
        """
        valid_escape_chars = set('"\\/bfnrtu')
        result = []
        i = 0
        length = len(text)

        while i < length:
            char = text[i]
            if char == "\\" and i + 1 < length:
                next_char = text[i + 1]
                if next_char in valid_escape_chars:
                    result.append(char)
                    result.append(next_char)
                    i += 2
                    continue
                else:
                    # Backslash không hợp lệ -> escape lại thành \\
                    result.append("\\\\")
                    i += 1
                    continue
            result.append(char)
            i += 1

        return "".join(result)
    @classmethod
    def _try_parse(cls, candidate: str) -> dict | None:
        """
        Thử parse JSON, nếu lỗi do invalid escape thì tự sửa và thử
        lại 1 lần. Trả về None nếu vẫn thất bại (để caller thử cách khác).
        """
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            if "Invalid \\escape" in str(e):
                try:
                    fixed = cls._fix_invalid_escapes(candidate)
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    return None
            return None

    @classmethod
    def _extract_json(cls, text: str) -> dict:
        """
        Trích JSON object từ raw text response của LLM.

        LLM đôi khi bọc JSON trong ```json ... ``` hoặc thêm text thừa
        trước/sau, nên cần tìm đoạn JSON object đầu tiên (từ '{' tới '}'
        khớp nhau) thay vì json.loads() trực tiếp toàn bộ text. Mỗi
        bước thử parse đều có fallback tự sửa invalid escape.
        """
        # Thử parse trực tiếp trước (trường hợp LLM trả JSON sạch)
        result = cls._try_parse(text)
        if result is not None:
            return result

        # Bóc markdown code fence nếu có (```json ... ``` hoặc ``` ... ```)
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fence_match:
            result = cls._try_parse(fence_match.group(1))
            if result is not None:
                return result

        # Fallback: tìm object JSON đầu tiên bằng cách đếm ngoặc {} khớp nhau
        start = text.find("{")
        if start == -1:
            raise json.JSONDecodeError("Không tìm thấy JSON object nào", text, 0)

        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    result = cls._try_parse(candidate)
                    if result is not None:
                        return result
                    # Đã thử cả sửa escape mà vẫn lỗi -> raise lỗi gốc
                    return json.loads(candidate)

        raise json.JSONDecodeError("JSON object không đóng ngoặc hợp lệ", text, start)