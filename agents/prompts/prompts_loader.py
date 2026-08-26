"""
Load và render các system prompt từ file YAML trong thư mục prompts/.

Cách dùng:

    from agents.prompts.prompts_loader import get_system_prompt

    prompt = get_system_prompt(
        "planner",
        topic="MCP cho AI Engineer",
        article_type="blog",
        target_audience="AI Engineer",
        tone="technical",
        language="vi",
        research_mode="hybrid",
        research_reasoning="Cần thông tin mới nhất về MCP",
        feedback=None,
    )
"""

from pathlib import Path

import yaml
from jinja2 import Template

PROMPTS_DIR = Path(__file__).parent

# Cache để không phải đọc lại file mỗi lần gọi.
_cache: dict[str, dict] = {}


def _load_yaml(name: str) -> dict:
    """Đọc và cache nội dung file YAML theo tên prompt (không có đuôi .yaml)."""
    if name in _cache:
        return _cache[name]

    path = PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy prompt file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    _cache[name] = data
    return data


def get_system_prompt(name: str, **variables) -> str:
    """
    Load prompt theo tên và render với các biến truyền vào (Jinja2).

    Args:
        name: Tên file prompt (không có đuôi .yaml), ví dụ "planner".
        **variables: Các biến để render vào template, ví dụ topic=..., tone=...

    Returns:
        Chuỗi system prompt đã render hoàn chỉnh, sẵn sàng gửi cho LLM.
    """
    data = _load_yaml(name)
    template_str = data.get("system", "")
    template = Template(template_str)
    return template.render(**variables)


def get_prompt_metadata(name: str) -> dict:
    """Lấy metadata (name, description, version) của 1 prompt, không kèm nội dung system."""
    data = _load_yaml(name)
    return {k: v for k, v in data.items() if k != "system"}


def clear_cache() -> None:
    """Xóa cache, dùng khi cần reload lại prompt sau khi chỉnh sửa file YAML (dev mode)."""
    _cache.clear()