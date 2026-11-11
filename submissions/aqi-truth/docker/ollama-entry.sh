#!/bin/sh
# Start Ollama, wait for the GGUF files the setup job downloads, then register them as local models.
ollama serve &
until [ -f /models/granite-4.0-micro.gguf ] && [ -f /models/granite-embedding.gguf ]; do sleep 5; done
until ollama list >/dev/null 2>&1; do sleep 2; done
ollama list | grep -q granite4-micro || ollama create granite4-micro -f /modelfiles/Modelfile.granite
ollama list | grep -q granite-embed || ollama create granite-embed -f /modelfiles/Modelfile.embed
wait
