import json
import re
import requests
from typing import Dict, Any
from config import Config

def clean_and_load_json(text: str) -> Dict[str, Any]:
    """Clean markdown code fences from JSON output and parse it."""
    text = text.strip()
    # Remove markdown code block markers
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
    text = text.strip()
    return json.loads(text)

class LLMClient:
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Generate a JSON response from Gemini API."""
        model = Config.GEMINI_MODEL
        api_key = Config.GEMINI_API_KEY
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1
            }
        }
        
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        
        res_data = response.json()
        try:
            text = res_data['candidates'][0]['content']['parts'][0]['text']
            return clean_and_load_json(text)
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected response structure from Gemini API: {res_data}") from e
