from agents.prompts import get_system_prompt

prompt = get_system_prompt("supervisor", topic="MCP", article_type="blog", target_audience="dev", tone="technical", language="vi", raw_input="test")
print(prompt)