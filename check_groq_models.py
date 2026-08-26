import os

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# LOAD ENV
# ============================================================

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError(
        "GROQ_API_KEY không tồn tại trong file .env"
    )


# ============================================================
# CREATE GROQ CLIENT
# ============================================================

client = Groq(
    api_key=api_key
)


# ============================================================
# LIST MODELS
# ============================================================

print("\n" + "=" * 70)
print("GROQ MODELS AVAILABLE TO YOUR API KEY")
print("=" * 70)

models = client.models.list()


for model in models.data:

    print(
        f"Model : {model.id}"
    )


print("\n" + "=" * 70)
print("DONE")
print("=" * 70)