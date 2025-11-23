# Travel Booking Agent: Hybrid Logic-LLM Architecture

![Project Thumbnail](https://github.com/Jotaro1569/travel-booking-agent/blob/main/thumbnail.png)

Travel agent splitting Gemini NLU from Python logic to prevent hallucinations and maintain conversation state across turns.

## Problem Statement

Standard Large Language Models (LLMs) struggle with transactional accuracy and state management in production scenarios. In travel booking, a generic chatbot might hallucinate flight prices or invent nonexistent flight IDs. More critically, they suffer from context loss. If a user searches for flights in Turn 1 and says "book the cheapest one" in Turn 2, the model often forgets the specific options it just provided. For real-world applications, these aren't just bugs, they're deal-breakers.

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
git clone https://github.com/YOUR_USERNAME/travel-booking-agent.git
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
```

## Step 4: Create requirements.txt
```
google-generativeai>=0.3.0
