from dotenv import load_dotenv
from google import genai
import os

load_dotenv(".env", override=True)

key = os.getenv("GEMINI_API_KEY")

if not key:
    raise RuntimeError("Gemini API key is missing")

client = genai.Client(api_key=key)

print("\nAVAILABLE TEXT GENERATION MODELS\n")

found = False

for model in client.models.list():
    actions = getattr(model, "supported_actions", []) or []

    if "generateContent" in actions:
        print(model.name)
        found = True

if not found:
    print("No text generation models found.")