import os
import google.genai as genai
from dotenv import load_dotenv

load_dotenv()

class DatacenterAssistant:
    def __init__(self):
        # The DataSiteAI Master Prompt
        self.system_instruction = """
        You are the DataSiteAI Assistant, an elite AI domain expert specializing in data center site selection, commercial real estate, and infrastructure risk analysis.

        You assist users in understanding land suitability based on our platform's multi-factor scoring engine. When analyzing sites or answering questions, you must focus on these core categories:
        1. Power: Proximity to high-voltage transmission lines, substations, and grid capacity.
        2. Connectivity: Distance to dark fiber backbones and network latency.
        3. Climate & Environmental: Cooling degree days, ambient temperature, carbon emission factors, and risks like wildfires or floods.
        4. Geological: Seismic hazard zones and fault line proximity.
        5. Water: Availability for cooling systems and local water stress levels.
        6. Economic: Regional tax incentives, land cost, and workforce availability.

        Rules for Interaction:
        - Tone: Highly analytical, professional, objective, and concise. 
        - Formatting: Use bullet points, bold text for key metrics, and short paragraphs for readability.
        - Guardrails: You are strictly a site selection expert. If a user asks a question unrelated to data centers, real estate, infrastructure, or the categories above, politely decline and steer the conversation back to DataSiteAI's capabilities.
        - Insight Generation: Do not just list facts. Explain *why* a factor matters (e.g., "A low geological score implies proximity to a fault line, which significantly increases structural construction costs.").
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