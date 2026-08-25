import os

from dotenv import load_dotenv
from google import genai

# ============================================================
# LOAD ENV
# ============================================================

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError(
        "GOOGLE_API_KEY không tồn tại trong file .env"
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

    # Chỉ quan tâm model có thể generate content
    supported_actions = getattr(
        model,
        "supported_actions",
        [],
    )

    if "generateContent" not in supported_actions:
        continue

    print(
        f"\nModel : {model.name}"
    )

    print(
        f"Display name : "
        f"{getattr(model, 'display_name', None)}"
    )

    print(
        f"Input limit : "
        f"{getattr(model, 'input_token_limit', None)}"
    )

    print(
        f"Output limit : "
        f"{getattr(model, 'output_token_limit', None)}"
    )

    print(
        f"Actions : "
        f"{supported_actions}"
    )


print("\n" + "=" * 70)
print("DONE")
print("=" * 70)