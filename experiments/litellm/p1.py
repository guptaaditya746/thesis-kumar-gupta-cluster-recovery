import litellm

messages = [{"role": "user", "content": "Explain Slurm in 100 sentence."}]

response = litellm.completion(
    model="hosted_vllm/Qwen/Qwen2.5-3B-Instruct",
    messages=messages,
    api_base="http://localhost:42048/v1",  # your vLLM port
    temperature=0.2,
    max_tokens=80,
)

print(response.choices[0].message.content)


import litellm

emb = litellm.embedding(
    model="hosted_vllm/Qwen/Qwen3-Embedding-0.6B",
    input=["hello", "world"],
    api_base="http://localhost:42049/v1",  # replace
)
print(len(emb.data[0]["embedding"]))
