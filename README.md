# Travel Booking Agent: Hybrid Logic-LLM Architecture

![Project Thumbnail](https://github.com/Jotaro1569/travel-booking-agent/blob/main/thumbnail.png)

Travel agent splitting Gemini NLU from Python logic to prevent hallucinations and maintain conversation state across turns.

## Problem Statement

Standard Large Language Models (LLMs) struggle with transactional accuracy and state management in production scenarios. In travel booking, a generic chatbot might hallucinate flight prices or invent nonexistent flight IDs. More critically, they suffer from context loss. If a user searches for flights in Turn 1 and says "book the cheapest one" in Turn 2, the model often forgets the specific options it just provided. For real-world applications, these aren't just bugs, they're deal-breakers.


## Agent Architecture

The `TravelAgentSystem` is a multi-agent system composed of a main orchestrator agent and several specialized sub-components.

### Main Agent

**`TravelAgentSystem`**: This is the main agent that interacts with the user. It manages the workflow of processing booking requests and delegates tasks to the appropriate sub-components.

### Sub-Components

The sub-components are defined in the `TravelAgentSystem` class. Each component is responsible for a specific task in the booking process:

- **`_extract_parameters`**: Parses user input into structured JSON using Gemini 2.5 Flash Lite. Extracts intent (SEARCH/BOOK/GENERAL), origin, destination, date references, and passenger names without making decisions.

- **`_resolve_date`**: Handles temporal logic deterministically. Calculates actual dates from natural language references like "tomorrow" or "today" using Python's datetime library to prevent LLM hallucination.

- **`_handle_search`**: Orchestrates the flight search workflow. Resolves dates, calls inventory tools, updates memory cache, and formats results for the user.

- **`_handle_booking`**: Manages the booking workflow. Performs entity resolution to match user references ("cheapest", "Air France") to specific flights in memory, then executes reservation via tools.

- **`_generate_response`**: Formats system outputs into natural language using Gemini's NLG capabilities. Takes deterministic tool results and creates professional, user-friendly responses.

- **`AgentMemory`**: A stateful blackboard that persists flight search results across conversation turns. Enables entity resolution by caching flight data and providing methods to query by airline name, flight ID, or price.

### Tools

The agents use the following custom tools:

- **`_search_flight_inventory`**: Searches available flights for a given origin, destination, and date. Returns flight data including IDs, airlines, departure times, and prices.

- **`_commit_reservation`**: Executes booking transactions. Takes a flight ID and passenger name, generates a unique PNR (Passenger Name Record), and returns confirmation status.

The agents also use the built-in `Gemini 2.5 Flash Lite` model for NLU and NLG tasks.

### Workflow

The `TravelAgentSystem` follows this workflow:

1. **Analyze Input**: The user provides a request. The agent analyzes it to extract structured parameters and intent.

2. **Plan**: The agent delegates the task to either the search handler or booking handler based on detected intent.

3. **Refine**: For searches, the system calculates dates deterministically. For bookings, it performs entity resolution using cached memory to identify the target flight.

4. **Execute**: Python code executes tool calls (`_search_flight_inventory` or `_commit_reservation`) without LLM involvement to ensure accuracy.

5. **Respond**: The agent formats tool outputs into natural language and presents results to the user. Search results are cached in memory for future booking requests.
# FlowChart

![FlowChart](https://github.com/Jotaro1569/travel-booking-agent/blob/main/flowchart.png)

## Why Agents?

Agents solve this by separating what LLMs do well (understanding intent) from what they don't (executing deterministic logic). A raw LLM can't reliably calculate "next Friday" or manage database transactions. An agentic architecture uses the LLM for Natural Language Understanding while delegating critical operations like date math, entity resolution, and booking commits to deterministic Python code. This hybrid approach keeps the system conversational while ensuring factual accuracy.

## Architecture

**1) NLU Layer (The Brain):** Uses Gemini 2.5 Flash Lite to parse user input into structured JSON, extracting intent, destinations, and relative dates like "tomorrow."

**2) Controller Layer (Python Logic):** A deterministic engine that handles:
   - State Management: An `AgentMemory` class persists search results across conversation turns
   - Entity Resolution: Custom logic maps vague requests ("book the Air France one" or "book the cheapest") to specific cached flight IDs
   - Tool Orchestration: Decides when to search vs. book based on intent

**3) NLG Layer (The Voice):** Feeds deterministic tool outputs back to Gemini to generate professional, user-facing responses.

## Demo

**Demo Flow:**
- **Turn 1:** User asks for flights "tomorrow." System calculates the date programmatically and returns three options from mock inventory.
- **Turn 2:** User says "book the Lufthansa one for Robin." System resolves "Lufthansa" to flight ID LH-5614 using memory and executes booking.
- **Turn 3:** User changes mind: "Actually, book the cheapest option." System re-resolves to Air France (AF-1923 at $300) and creates new reservation, all without re-searching.

See full output in [`demo_output.txt`](https://github.com/Jotaro1569/travel-booking-agent/blob/main/demon_output.txt)

## Installation
```bash
# Clone the repository
git clone https://github.com/Jotaro1569/travel-booking-agent.git
cd travel-booking-agent

# Install dependencies
pip install -r requirements.txt

# Set your API key
export GEMINI_API_KEY="your_key_here"

# Run the agent
python travel_agent.py
```

## Technical Implementation

- Built with Google AI SDK (`google-generativeai`) and Python 3
- **Model:** Gemini 2.5 Flash Lite for low-latency responses in a real-time booking flow
- **Architecture:** Hub-and-spoke pattern where a central orchestrator manages data flow between memory and service tools (`_search_flight_inventory`, `_commit_reservation`)
- **Key Innovation:** Custom `AgentMemory` blackboard prevents context loss by caching search results, enabling entity resolution in subsequent turns without re-querying

## Future Enhancements

- **Live API Integration:** Replace mock tools with real GDS APIs (Amadeus/Sabre) for actual flight inventory
- **Cancellation Logic:** Add a `CANCEL` intent to properly handle booking modifications
- **Multi-turn Date Handling:** Extend `_resolve_date()` to handle "next Monday," "two weeks from today," etc.
- **Web Interface:** Build a FastAPI backend with a simple frontend to move beyond CLI interaction
- **Multi-modal Input:** Allow users to upload flight screenshot images for the agent to parse and price-match

## License

MIT License - feel free to use this for learning!



