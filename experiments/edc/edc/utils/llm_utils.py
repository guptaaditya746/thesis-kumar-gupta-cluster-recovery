import os
import time
import ast
from typing import List
import gc
import logging

logger = logging.getLogger(__name__)

def free_model(model=None, tokenizer=None):
    """
    Free local torch/HuggingFace models when possible.
    API client wrappers do not need GPU cleanup.
    """
    try:
        if model is not None and hasattr(model, "cpu"):
            model.cpu()

        if model is not None:
            del model

        if tokenizer is not None:
            del tokenizer

        gc.collect()

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    except Exception as e:
        logger.warning(e)

def get_embedding_e5mistral(model, tokenizer, sentence, task=None):
    model.eval()
    device = model.device

    if task != None:
        # It's a query to be embed
        sentence = get_detailed_instruct(task, sentence)

    sentence = [sentence]

    max_length = 4096
    # Tokenize the input texts
    batch_dict = tokenizer(
        sentence, max_length=max_length - 1, return_attention_mask=False, padding=False, truncation=True
    )
    # append eos_token_id to every input_ids
    batch_dict["input_ids"] = [input_ids + [tokenizer.eos_token_id] for input_ids in batch_dict["input_ids"]]
    batch_dict = tokenizer.pad(batch_dict, padding=True, return_attention_mask=True, return_tensors="pt")

    batch_dict.to(device)

    embeddings = model(**batch_dict).detach().cpu()

    assert len(embeddings) == 1

    return embeddings[0]


def get_detailed_instruct(task_description: str, query: str) -> str:
    return f"Instruct: {task_description}\nQuery: {query}"


def get_embedding_sts(model, text: str, prompt_name=None, prompt=None):
    embedding = model.encode(text, prompt_name=prompt_name, prompt=prompt)
    return embedding


def parse_raw_entities(raw_entities: str):
    parsed_entities = []
    left_bracket_idx = raw_entities.index("[")
    right_bracket_idx = raw_entities.index("]")
    try:
        parsed_entities = ast.literal_eval(raw_entities[left_bracket_idx : right_bracket_idx + 1])
    except Exception as e:
        pass
    logging.debug(f"Entities {raw_entities} parsed as {parsed_entities}")
    return parsed_entities


def parse_raw_triplets(raw_triplets: str):
    # Look for enclosing brackets
    unmatched_left_bracket_indices = []
    matched_bracket_pairs = []

    collected_triples = []
    for c_idx, c in enumerate(raw_triplets):
        if c == "[":
            unmatched_left_bracket_indices.append(c_idx)
        if c == "]":
            if len(unmatched_left_bracket_indices) == 0:
                continue
            # Found a right bracket, match to the last found left bracket
            matched_left_bracket_idx = unmatched_left_bracket_indices.pop()
            matched_bracket_pairs.append((matched_left_bracket_idx, c_idx))
    for l, r in matched_bracket_pairs:
        bracketed_str = raw_triplets[l : r + 1]
        try:
            parsed_triple = ast.literal_eval(bracketed_str)
            if len(parsed_triple) == 3 and all([isinstance(t, str) for t in parsed_triple]):
                if all([e != "" and e != "_" for e in parsed_triple]):
                    collected_triples.append(parsed_triple)
            elif not all([type(x) == type(parsed_triple[0]) for x in parsed_triple]):
                for e_idx, e in enumerate(parsed_triple):
                    if isinstance(e, list):
                        parsed_triple[e_idx] = ", ".join(e)
                collected_triples.append(parsed_triple)
        except Exception as e:
            pass
    logger.debug(f"Triplets {raw_triplets} parsed as {collected_triples}")
    return collected_triples

def parse_relation_definition(raw_definitions: str):
    descriptions = raw_definitions.split("\n")
    relation_definition_dict = {}

    for description in descriptions:
        if ":" not in description:
            continue
        index_of_colon = description.index(":")
        relation = description[:index_of_colon].strip()

        relation_description = description[index_of_colon + 1 :].strip()

        if relation == "Answer":
            continue

        relation_definition_dict[relation] = relation_description
    logger.debug(f"Relation Definitions {raw_definitions} parsed as {relation_definition_dict}")
    return relation_definition_dict



def is_model_openai(model_name):
    """
    Treat these model names as OpenAI-compatible API models.

    Examples:
    - gpt-4
    - openai/qwen-chat
    - openai/qwen-embed
    - vllm/qwen-chat
    - vllm/qwen-embed
    """
    if model_name is None:
        return False

    model_name = model_name.lower()

    return (
        "gpt" in model_name
        or model_name.startswith("openai/")
        or model_name.startswith("vllm/")
    )


def strip_openai_compatible_prefix(model_name: str) -> str:
    """
    EDC may receive 'openai/qwen-chat', but vLLM expects 'qwen-chat'.
    """
    if model_name.startswith("openai/"):
        return model_name.replace("openai/", "", 1)
    if model_name.startswith("vllm/"):
        return model_name.replace("vllm/", "", 1)
    return model_name


class OpenAICompatibleEmbeddingClient:
    """
    Adapter so an OpenAI-compatible embedding endpoint behaves like
    SentenceTransformer.

    EDC expects:
        embedder.encode(text)
        embedder.prompts
    """

    def __init__(self, model_name: str):
        from openai import OpenAI
        import math

        self.model_name = strip_openai_compatible_prefix(model_name)

        api_key = (
            os.environ.get("OPENAI_EMBEDDING_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENAI_KEY")
        )

        base_url = (
            os.environ.get("OPENAI_EMBEDDING_BASE_URL")
            or os.environ.get("OPENAI_EMBEDDING_API_BASE")
            or os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("OPENAI_API_BASE")
        )

        if api_key is None:
            raise RuntimeError(
                "Missing API key. Set OPENAI_EMBEDDING_KEY or OPENAI_API_KEY."
            )

        if base_url is None:
            raise RuntimeError(
                "Missing embedding base URL. Set OPENAI_EMBEDDING_BASE_URL."
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        # EDC checks this in schema_canonicalization.py:
        # if "sts_query" in self.embedder.prompts
        self.prompts = {}

        self._math = math

    def _normalize(self, vector):
        norm = self._math.sqrt(sum(float(x) * float(x) for x in vector))
        if norm == 0:
            return vector
        return [float(x) / norm for x in vector]

    def encode(self, text, prompt_name=None, prompt=None):
        """
        Compatible with SentenceTransformer.encode().
        Accepts either a single string or a list of strings.
        """
        is_single_input = isinstance(text, str)

        if is_single_input:
            inputs = [text]
        else:
            inputs = list(text)

        if prompt is not None:
            inputs = [prompt + item for item in inputs]

        response = self.client.embeddings.create(
            model=self.model_name,
            input=inputs,
        )

        embeddings = [self._normalize(item.embedding) for item in response.data]

        if is_single_input:
            return embeddings[0]

        return embeddings

def generate_completion_transformers(
    input: list,
    model,
    tokenizer,
    max_new_token=256,
    answer_prepend="",
):
    from transformers import GenerationConfig
    device = model.device
    tokenizer.pad_token = tokenizer.eos_token

    messages = tokenizer.apply_chat_template(input, add_generation_prompt=True, tokenize=False) + answer_prepend

    model_inputs = tokenizer(messages, return_tensors="pt", padding=True, add_special_tokens=False).to(device)

    generation_config = GenerationConfig(
        do_sample=False,
        max_new_tokens=max_new_token,
        pad_token_id=tokenizer.eos_token_id,
        return_dict_in_generate=True,
    )

    generation = model.generate(**model_inputs, generation_config=generation_config)
    sequences = generation["sequences"]
    generated_ids = sequences[:, model_inputs["input_ids"].shape[1] :]
    generated_texts = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

    logging.debug(f"Prompt:\n {messages}\n Result: {generated_texts}")
    return generated_texts

def openai_chat_completion(model, system_prompt, history, temperature=0, max_tokens=512):
    from openai import OpenAI

    api_key = (
        os.environ.get("OPENAI_CHAT_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENAI_KEY")
    )

    base_url = (
        os.environ.get("OPENAI_CHAT_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_API_BASE")
    )

    if api_key is None:
        raise RuntimeError("Missing API key. Set OPENAI_CHAT_KEY or OPENAI_API_KEY.")

    if base_url is None:
        raise RuntimeError("Missing chat base URL. Set OPENAI_CHAT_BASE_URL.")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    model = strip_openai_compatible_prefix(model)

    if system_prompt is not None:
        messages = [{"role": "system", "content": system_prompt}] + history
    else:
        messages = history

    last_error = None

    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            logging.debug(
                f"Model: {model}\nPrompt:\n {messages}\n Result: {response.choices[0].message.content}"
            )

            return response.choices[0].message.content

        except Exception as e:
            last_error = e
            logging.warning(
                f"OpenAI-compatible chat call failed. Attempt {attempt + 1}/5. Error: {e}"
            )
            time.sleep(5)

    raise RuntimeError(f"OpenAI-compatible chat call failed after 5 attempts: {last_error}")
