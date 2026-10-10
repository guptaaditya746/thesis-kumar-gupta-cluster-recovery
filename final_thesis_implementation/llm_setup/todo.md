30B-A3B 

- check how to turn off its thinking , FOR Grade we dont require thinking
- its MOE model , so would be fast
-
-

- [ ] Marco-DeepResearch-8B: server and generation respond, but reasoning is mixed into `message.content` and the short test ended with `finish_reason: length`. Re-test with the model-specific reasoning parser/chat-template configuration before using it.


- [ ] DR-Venus-4B-RL: mark FAILED for agentic RAG. The qwen3 reasoning parser produced a `reasoning` field, but final content was malformed, repeated, leaked `</think>` tags, and ended due to the token limit. Re-test with the model-specific chat template/parser only if needed.


- [ ] Qwen2.5-32B-Instruct-AWQ: user requested FAILED status; capture the exact server/chat error before attempting a repair.


- [ ] DeepSeek-R1 Distill Qwen-32B AWQ: user requested FAILED status; capture the exact server/chat error before attempting a repair. Tool calling was not validated.


- [ ] Gemma-4 E4B-it: CHAT_FAILED. Basic chat timed out after 180 seconds with zero response bytes. Inspect server logs before attempting a parser/backend correction.


- [ ] Cohere Command R7B: accept access conditions, download, test 65K chat, then identify the correct vLLM 0.21 tool parser.
- [ ] Thinking Machines Lab Inkling: unsupported on one A100 40GB; Inkling-Small is 266B and Inkling-Small-NVFP4 is 156B.

