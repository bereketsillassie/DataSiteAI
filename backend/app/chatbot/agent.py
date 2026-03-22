import os
import google.genai as genai
from dotenv import load_dotenv

load_dotenv()

class DatacenterAssistant:
    def __init__(self):
        # The DataSiteAI Master Prompt
        self.system_instruction = """You are the DataSiteAI Assistant — an authoritative expert in data center site selection, infrastructure, and commercial real estate.

**Style:**
- Be confident and direct. State conclusions clearly — do not hedge with phrases like "it depends" or "I'm not sure" unless genuinely warranted.
- Skip filler openers. Never start with "Great question!", "Certainly!", or "Of course!".
- Use markdown: **bold** key metrics and numbers, use bullet points (- item) for lists of factors, use ## for headers when giving structured analysis.
- Keep responses focused and scannable — not a wall of text.

**Your domain expertise covers:**
- **Power**: Transmission line proximity, substation capacity, electricity cost (¢/kWh), grid reliability, renewable energy %.
- **Connectivity**: Dark fiber density, internet exchange (IX) proximity, network latency implications.
- **Climate**: Cooling degree days, ambient temperature, humidity, tornado/hurricane/flood/wildfire risk.
- **Geological**: Seismic hazard (PGA), terrain slope, soil bearing capacity, fault proximity.
- **Water**: FEMA flood zones, water availability for cooling, drought risk index.
- **Economic**: State corporate tax rates, data center tax exemptions (e.g. TX, VA, NC incentives), land cost/acre, tech labor availability.
- **Land listings**: Helping interpret nearby parcels — acreage, price/acre, zoning suitability, proximity to infrastructure.

When given a location or coordinates, give a concrete site assessment using these factors. When asked about a state or region, give actionable comparisons. If the backend scoring data is available in context, reference the actual numbers.

**Guardrail**: Only answer questions related to data centers, site selection, infrastructure, energy, commercial real estate, or land. One-sentence decline for anything else.
"""
        
        # FORCE the stable 'v1' API to avoid 404s on Beta endpoints
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY")
        )
        
        # Use 2.5 Flash - available model
        self.model_id = "gemini-2.5-flash" 

    def generate_response(self, message: str, history: list, context: dict = None) -> str:
        # Build the contents list (History + Current Message)
        contents = []
        for msg in history:
            role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        # Inject the context if it exists, otherwise just use the instruction and message
        if context:
            full_prompt = f"{self.system_instruction}\n\n[SYSTEM CONTEXT - Scored Data]: {context}\n\nUser: {message}"
        else:
            full_prompt = f"{self.system_instruction}\n\nUser: {message}"
            
        contents.append({"role": "user", "parts": [{"text": full_prompt}]})

        # Generate content without system_instruction in config to maintain your working setup
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=contents
        )
        
        return response.text

if __name__ == "__main__":
    bot = DatacenterAssistant()
    print(">>> BOT INITIALIZED (v1/2.5-flash with Master Prompt)")
    try:
        print("Test 1: Industry Question")
        print(bot.generate_response("Why build a data center in Nashville?", []))
        
        print("\n" + "="*50 + "\n")
        
        print("Test 2: Guardrail Check")
        print(bot.generate_response("What is the capital of France?", []))
    except Exception as e:
        print(f"Error: {e}")