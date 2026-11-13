# zuno

Local-first AI assistant (ZERO) built with React + Vite, Spring Boot, MySQL, and a local Python FastAPI + `llama.cpp` (`Qwen3-4B-Q4_K_M`) inference service.

## Architecture

- **Frontend (`frontend/`)**: React + Vite chat UI with real-time SSE streaming, adaptive modes (`Auto`, `Fast`, `Detailed`), `Web` search toggle, document attachment (`Attach doc`), and Stop cancellation.
- **Backend (`backend/`)**: Spring Boot REST + `SseEmitter` gateway (`8081`), JPA persistence in MySQL (`zuno_db`), conversation history, and persistent user memory extraction.
- **AI Service (`backend/ai-service/`)**: FastAPI (`8001`) running `Qwen3-4B-Q4_K_M.gguf` via `llama-cpp-python` (Config C: `N_THREADS=4`, `N_THREADS_BATCH=8`, `N_BATCH=256`, `N_CTX=2048`), document RAG (`rag_store.py`), calculator/time tools, and DuckDuckGo web search (`tools_layer.py`).

## Setup

1. **Model**: Place `Qwen3-4B-Q4_K_M.gguf` at `backend/models/Qwen3-4B/Qwen3-4B-Q4_K_M.gguf`.
2. **Backend config**: Copy `backend/src/main/resources/application.properties.example` to `backend/src/main/resources/application.properties` and set your MySQL password.
3. **Run services**:
   - Python AI service (`8001`): `cd backend/ai-service && pip install -r requirements.txt && python main.py`
   - Spring Boot (`8081`): `cd backend && ./mvnw spring-boot:run`
   - Frontend (`5173`): `cd frontend && npm install && npm run dev`

