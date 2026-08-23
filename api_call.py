from dotenv import load_dotenv
import os
from google import genai


load_dotenv()

print("ok")

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
)

tools = [
    {
        'type': 'google_search',
    },
]

generation_config = {
    'temperature': 1,
    'max_output_tokens': 65536,
    'top_p': 0.95,
    'thinking_level': 'high',
}

prompt = "Explain transformers in simple words."

response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=prompt
)

with open("output.txt", "w") as file:
    file.write(prompt)
    file.write(response.text)




