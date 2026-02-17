# RPMX Demo Platform

End-to-end demo platform for RPMX Construction human-emulator agents.

## Stack

- Agent runtime: Python orchestration with spec-aligned tool interfaces
- API: FastAPI + WebSocket streaming
- Data: SQLite + PDF invoice files + JSON seed files
- Frontend: React + Tailwind + Vite

## Included Capabilities

- 11 runnable agent implementations with spec-aligned scenarios
- PO Match primary flow with:
  - Real PDF invoice reads
  - Exact/fuzzy PO match logic
  - Variance, no-PO, and duplicate exception handling
  - Training-driven post-run behavior update for invoice `INV-9007`
- FastAPI orchestration with REST + WebSocket stream (`/ws/agent/{session_id}`)
- Command Center + Agent Workspace UI (review queue, training chat, skills, communications)
- Full reset pipeline (`/api/demo/reset` and `scripts/reset_demo.py`)

## Quick Start

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env`
4. `python /Users/jesseanglen/Documents/RPMxDemo3/scripts/reset_demo.py`
5. `python3 /Users/jesseanglen/Documents/RPMxDemo3/scripts/run_agent.py po_match`
6. `uvicorn api.main:app --reload --port 8000`
7. `cd frontend && npm install && npm run dev`

Open [http://localhost:5173](http://localhost:5173).

## Verification Commands

- `python3 scripts/reset_demo.py`
- `python3 scripts/run_agent.py po_match`
- `python3 scripts/reliability_check.py --runs 5`
- `python3 -m pytest -q`
- `python3 -m uvicorn api.main:app --reload --port 8000`

## Enable Real AI (OpenRouter)

1. Add to `.env`:
   - `USE_REAL_LLM=true`
   - `OPENROUTER_API_KEY=...`
   - `OPENROUTER_MODEL=anthropic/claude-3.7-sonnet` (or another OpenRouter model id)
2. Start API and check:
   - `curl http://localhost:8000/api/health`
   - Confirm `"real_llm_enabled":"true"`
3. Run `PO Match Agent` again.

The runtime is now model-only: agent decisions are produced by the configured OpenRouter model.  
If `USE_REAL_LLM` is false or `OPENROUTER_API_KEY` is missing, agent runs fail by design.
