from agents.schemas import UserRequest, Plan, Task, WriterState

# Test tạo UserRequest
req = UserRequest(topic="MCP cho AI Engineer")
print(req)

# Test tạo Plan với dependency
plan = Plan(
    title="MCP cho AI Engineer",
    objective="Giải thích MCP",
    target_audience="AI Engineer",
    tone="technical",
    tasks=[
        Task(id="task_01", title="Intro", description="...", objective="...", expected_output="..."),
        Task(id="task_02", title="Architecture", description="...", objective="...", expected_output="...", depends_on=["task_01"]),
        Task(id="task_03", title="Conclusion", description="...", objective="...", expected_output="...", depends_on=["task_02"]),
    ],
)
print(plan)

# Test cycle detection (phải raise ValidationError)
try:
    bad_plan = Plan(
        title="Bad",
        objective="test",
        target_audience="test",
        tone="test",
        tasks=[
            Task(id="task_01", title="A", description="...", objective="...", expected_output="...", depends_on=["task_02"]),
            Task(id="task_02", title="B", description="...", objective="...", expected_output="...", depends_on=["task_01"]),
            Task(id="task_03", title="C", description="...", objective="...", expected_output="..."),
        ],
    )
except Exception as e:
    print(f"✅ Cycle detected correctly: {e}")