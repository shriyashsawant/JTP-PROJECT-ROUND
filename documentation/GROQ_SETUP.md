# AuraMatch AI - Groq LLM Setup & Configuration Guide

AuraMatch AI features a fail-safe, optional LLM re-ranking and explanation enrichment layer. When a Groq API key is configured, the backend sends the top semantic search results to Groq (specifically Llama 3) to generate natural language explanations and match-checklist validations. 

If no Groq key is configured, or if the Groq API times out or fails (safeguarded by a custom circuit breaker), the application gracefully degrades to deterministic matching with zero user-facing latency.

---

## 1. Obtaining a Groq API Key

To get a Groq API key:
1. Go directly to the [Groq API Keys page](https://console.groq.com/keys).
2. Create an account or sign in if prompted.
3. Click **Create API Key**, give it a name (e.g., `AuraMatch-Dev`), and copy the generated key (starts with `gsk_`).

---

## 2. Configuration Options

The Python backend is configured using Pydantic Settings and loads configurations from environment variables or a `.env` file.

### Option A: Via `.env` File (Recommended)

1. **Locate the Project Root Directory**: Ensure you are in the main project workspace directory (`JTP-PROJECT-ROUND/`), which contains `docker-compose.yml`, `backend/`, and `frontend/`.
2. **Create/Edit the File**:
   * **Exact Name**: `.env` (it must start with a dot, with no other prefix or extension like `.env.txt`).
   * **Exact Path**: `JTP-PROJECT-ROUND/.env`
3. **Configure the Key**: Add your Groq API key inside the `.env` file:
   ```env
   GROQ_API_KEY=gsk_your_actual_groq_api_key_here
   ```

When you start the application using Docker Compose, the `backend` service is configured to automatically pass the host's `GROQ_API_KEY` environment variable (which Docker Compose reads from `.env` by default) into the container:

```yaml
# In docker-compose.yml
backend:
  environment:
    GROQ_API_KEY: ${GROQ_API_KEY:-}
```

### Option B: Via Host Environment Variables

If you do not want to use a `.env` file, you can set the environment variable directly in your terminal session before starting the containers:

* **Windows PowerShell**:
  ```powershell
  $env:GROQ_API_KEY="gsk_your_actual_groq_api_key_here"
  docker compose up -d
  ```
* **Linux / macOS**:
  ```bash
  export GROQ_API_KEY="gsk_your_actual_groq_api_key_here"
  docker compose up -d
  ```

---

## 3. Verifying the Integration

Once the application is running with the Groq API key set, you can verify that the LLM re-ranking layer is active:

1. **Verify via Logs**: 
   Inspect the backend logs. If a search query is submitted, you should see logs showing prompts being built and sent to Groq:
   ```bash
   docker compose logs backend
   ```
2. **Verify via Admin Dashboard**:
   Go to [http://localhost:3000/admin](http://localhost:3000/admin). Under the Circuit Breakers section, you can monitor the health and state of the Groq API circuit breaker.
   * `CLOSED`: The breaker is healthy and routing requests to Groq.
   * `OPEN`: Groq has experienced 5 consecutive failures and is temporarily disabled (auto-degraded).
3. **Verify via Prometheus Metrics**:
   Query the `/metrics` endpoint at [http://localhost:8000/metrics](http://localhost:8000/metrics) and look for the `auramatch_circuit_breaker_state` gauge:
   * `auramatch_circuit_breaker_state{breaker="groq"} 0` indicates the connection is active and healthy.
