import os

from dotenv import load_dotenv
from google import genai


# ============================================================
# LOAD ENV
# ============================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY không tồn tại trong file .env"
    )


# ============================================================
# CREATE GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=api_key
)


# ============================================================
# LIST MODELS
# ============================================================

print("\n" + "=" * 70)
print("GEMINI MODELS AVAILABLE TO YOUR API KEY")
print("=" * 70)

models = client.models.list()


for model in models:

    supported_actions = getattr(
        model,
        "supported_actions",
        [],
    )

    # Chỉ lấy model có thể generate content
    if "generateContent" not in supported_actions:
        continue

    print(
        f"Model : {model.name}"
    )


print("\n" + "=" * 70)
print("DONE")
print("=" * 70)