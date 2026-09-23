# Factory AI Prototype

This repository contains a local prototype for technical document analysis using LlamaIndex, Ollama, Qdrant, and Gradio.

## Quick start

1. Create the project folder and place your PDF/DOCX/TXT docs under `data/docs/`.
2. Start the stack:

   ```bash
   docker compose up -d --build
   ```

3. Pull the LLM model inside the Ollama container:

   ```bash
   docker exec -it factory_ai_prototype-ollama-1 ollama pull qwen2.5:1.5b
   ```

4. Open the Gradio UI at:

   http://localhost:7860

## Share with a curator

Clone the repository, install Docker Desktop, then run the Quick start commands above. Add documents through the UI; local documents and model storage are intentionally excluded from Git.

The default CPU-friendly model is `qwen2.5:1.5b`. The embedding model is `nomic-embed-text`.

## Notes

- The system is designed for an isolated enterprise environment, with services connected through a Docker bridge network.
- For fully closed networks, enable `internal: true` in the Compose network section.
- Data remains local to the deployment; no external API keys are required for the local mode.
