#!/usr/bin/env bash

# Chat API Variables
export OPENAI_CHAT_KEY="sk-local-vllm"
export OPENAI_CHAT_BASE_URL="http://gammaweb07.medien.uni-weimar.de:8000/v1"

# Embedding API Variables
export OPENAI_EMBEDDING_KEY="sk-local-vllm"
export OPENAI_EMBEDDING_BASE_URL="http://gammaweb07.medien.uni-weimar.de:8001/v1"

echo "✅ vLLM remote environment variables loaded!"
