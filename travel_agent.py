import os
import re
import json
import logging
import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import google.generativeai as genai

# ==============================================================================
# 1. CONFIGURATION & LOGGING
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("TravelOrchestrator")

# API Key Retrieval
try:
    from kaggle_secrets import UserSecretsClient
    API_KEY = UserSecretsClient().get_secret("GEMINI_API_KEY")
except ImportError:
    API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    logger.error("GEMINI_API_KEY not found. System cannot initialize.")
    exit(1)

genai.configure(api_key=API_KEY)
MODEL_NAME = 'gemini-2.5-flash-lite' 

# ==============================================================================
# 2. SHARED MEMORY (STATE MANAGEMENT)
# ==============================================================================

@dataclass
class FlightRecord:
    flight_id: str
    airline: str
    price: int
    raw_price: str
    departure: str
    origin: str
    destination: str

class AgentMemory:
    """
    Central state store for the agent.
    Persists flight search results to allow for entity resolution in subsequent turns.
    """
    def __init__(self):
        self.flight_cache: List[FlightRecord] = []
        self.last_search_context: Dict[str, Any] = {}

    def update_cache(self, raw_flights: List[Dict], origin: str, dest: str):
        """Parses and stores flight data."""
        self.flight_cache = []
        for f in raw_flights:
            # Parse price string "$420" -> 420 for comparison logic
            try:
                price_int = int(re.sub(r'[^\d]', '', f['price']))
            except ValueError:
                price_int = 999999

            record = FlightRecord(
                flight_id=f['flight_id'],
                airline=f['airline'],
                price=price_int,
                raw_price=f['price'],
                departure=f['departure_time'],
                origin=origin,
                destination=dest
            )
            self.flight_cache.append(record)
        
        logger.info(f"Memory updated with {len(self.flight_cache)} flight options.")

    def find_flight_by_airline(self, airline_name: str) -> Optional[FlightRecord]:
        """Resolves fuzzy airline name match."""
        normalized_query = airline_name.lower().replace(" ", "")
        for flight in self.flight_cache:
            if normalized_query in flight.airline.lower().replace(" ", ""):
                return flight
        return None

    def find_cheapest_flight(self) -> Optional[FlightRecord]:
        """Resolves 'cheapest' intent."""
        if not self.flight_cache:
            return None
        return min(self.flight_cache, key=lambda x: x.price)

    def get_flight_by_id(self, flight_id: str) -> Optional[FlightRecord]:
        for flight in self.flight_cache:
            if flight.flight_id == flight_id:
                return flight
        return None

# ==============================================================================
# 3. MOCK TOOLS (DATA LAYER)
# ==============================================================================

def _search_flight_inventory(origin: str, destination: str, date_str: str) -> Dict:
    """Mock search tool returning deterministic results."""
    logger.info(f"TOOL CALL: SearchInventory [Origin: {origin}, Dest: {destination}, Date: {date_str}]")
    
    # Deterministic mock data
    return {
        "flights": [
            {"flight_id": "BA-2847", "airline": "British Airways", "departure_time": "09:00 AM", "price": "$420"},
            {"flight_id": "AF-1923", "airline": "Air France", "departure_time": "02:00 PM", "price": "$300"},
            {"flight_id": "LH-5614", "airline": "Lufthansa", "departure_time": "08:00 PM", "price": "$600"}
        ]
    }

def _commit_reservation(flight_id: str, passenger_name: str) -> Dict:
    """Mock booking tool."""
    logger.info(f"TOOL CALL: CommitReservation [ID: {flight_id}, Passenger: {passenger_name}]")
    import uuid
    pnr = f"PNR{str(uuid.uuid4())[:6].upper()}"
    return {
        "status": "CONFIRMED",
        "pnr": pnr,
        "flight_id": flight_id,
        "passenger": passenger_name
    }

# ==============================================================================
# 4. ORCHESTRATOR (CONTROLLER LOGIC - AGENTIC DECISION ENGINE)
# ==============================================================================

class TravelAgentSystem:
    def __init__(self):
        self.memory = AgentMemory()
        self.model = genai.GenerativeModel(MODEL_NAME)
        
    def _extract_parameters(self, user_input: str) -> Dict[str, Any]:
        """
        Uses LLM strictly for NLU (Natural Language Understanding) to parse intent and parameters.
        Does NOT make decisions.
        """
        prompt = f"""
        Analyze the following user input and extract structured data.
        User Input: "{user_input}"
        
        Output valid JSON with these keys:
        - "intent": "SEARCH", "BOOK", or "GENERAL"
        - "origin": City name or null
        - "destination": City name or null
        - "date_reference": "tomorrow", "next monday", "specific date", or null
        - "booking_target": If booking, the airline name (e.g., "Air France") or "cheapest", or null
        - "passenger": Passenger name or "Guest"
        
        Return ONLY JSON.
        """
        try:
            response = self.model.generate_content(prompt)
            # Clean markdown code blocks if present
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
        except Exception as e:
            logger.error(f"NLU Extraction failed: {e}")
            return {"intent": "GENERAL"}

    def _resolve_date(self, date_ref: str) -> str:
        """Python logic to calculate dates. No LLM guessing."""
        today = datetime.date.today()
        
        if not date_ref:
            return today.strftime("%Y-%m-%d")
            
        date_ref = date_ref.lower()
        target_date = today

        if "tomorrow" in date_ref:
            target_date = today + datetime.timedelta(days=1)
        elif "today" in date_ref:
            target_date = today
        # Add more logic here for "next week" etc if needed
        # For this production snippet, we handle 'tomorrow' explicitly as requested.
        
        return target_date.strftime("%Y-%m-%d")

    def _generate_response(self, context: str) -> str:
        """Uses LLM strictly for NLG (Natural Language Generation)."""
        prompt = f"""
        You are a professional corporate travel assistant.
        Based on the SYSTEM CONTEXT below, generate a concise, professional response to the user.
        Do not make up new facts. Use the provided context.
        
        SYSTEM CONTEXT:
        {context}
        """
        res = self.model.generate_content(prompt)
        return res.text.strip()

    def handle_request(self, user_input: str) -> str:
        """Main orchestrator logic."""
        
        # Step 1: NLU - extract intent and parameters
        nlu_data = self._extract_parameters(user_input)
        intent = nlu_data.get("intent", "GENERAL")
        logger.info(f"Intent Detected: {intent} | Data: {nlu_data}")

        # Step 2: Route to appropriate handler based on intent
        if intent == "SEARCH":
            return self._handle_search(nlu_data)
        elif intent == "BOOK":
            return self._handle_booking(nlu_data)
        else:
            return "I am a Travel Agent system. I can help you search for and book flights. How may I assist?"

    def _handle_search(self, data: Dict) -> str:
        origin = data.get("origin", "Unknown")
        dest = data.get("destination", "Unknown")
        date_ref = data.get("date_reference")
        
        # Resolve date using deterministic Python logic
        travel_date = self._resolve_date(date_ref)
        
        # Call search tool directly - no LLM involved
        search_results = _search_flight_inventory(origin, dest, travel_date)
        
        # Update agent memory with search results
        self.memory.update_cache(search_results['flights'], origin, dest)
        
        # Generate human-readable summary via NLG
        flight_strings = [f"- {f.airline} ({f.flight_id}): {f.raw_price} at {f.departure}" for f in self.memory.flight_cache]
        context_str = f"Search completed for {origin} to {dest} on {travel_date}. Found {len(flight_strings)} options:\n" + "\n".join(flight_strings)
        
        return self._generate_response(context_str)

    def _handle_booking(self, data: Dict) -> str:
        target = data.get("booking_target", "").lower()
        passenger = data.get("passenger", "Guest")
        
        flight_record = None

        # Entity resolution: map user reference to actual flight in memory
        if "cheapest" in target:
            flight_record = self.memory.find_cheapest_flight()
            logger.info(f"Entity Resolution: 'cheapest' resolved to ID {flight_record.flight_id if flight_record else 'None'}")
        else:
            # Try matching by airline name first
            flight_record = self.memory.find_flight_by_airline(target)
            if not flight_record:
                # Fallback: check if user provided raw flight ID
                flight_record = self.memory.get_flight_by_id(target.upper())
            logger.info(f"Entity Resolution: '{target}' resolved to ID {flight_record.flight_id if flight_record else 'None'}")

        if not flight_record:
            return "I could not identify the flight you wish to book. Please specify the airline name or flight ID from the search results."

        # Execute booking via tool call
        booking_result = _commit_reservation(flight_record.flight_id, passenger)
        
        # Generate confirmation message
        context_str = (
            f"Booking successful.\n"
            f"Airline: {flight_record.airline}\n"
            f"Flight ID: {booking_result['flight_id']}\n"
            f"Passenger: {booking_result['passenger']}\n"
            f"PNR: {booking_result['pnr']}\n"
            f"Status: {booking_result['status']}"
        )
        return self._generate_response(context_str)

# ==============================================================================
# 5. EXECUTION ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    
    agent = TravelAgentSystem()
    
    # Define a clean, professional scenario
    scenario_messages = [
        "Find me flights from London to Paris for tomorrow.",
        "Actually, book the Lufthansa one for Robin.",
        "Wait, cancel that thought. Book the cheapest option instead for Robin."
    ]

    print(" TRAVEL AGENT SYSTEM LOG ")
    
    for i, msg in enumerate(scenario_messages):
        print(f"\n[Turn {i+1}] User: {msg}")
        
        # Execute agent logic
        try:
            response = agent.handle_request(msg)
            print(f"[Turn {i+1}] Agent: {response}")
        except Exception as e:
            logger.error(f"Runtime error: {e}")
            
    print("\n END OF SESSION ")
