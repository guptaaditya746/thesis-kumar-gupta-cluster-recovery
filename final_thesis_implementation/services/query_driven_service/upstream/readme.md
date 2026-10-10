# Query-Driven Multimodal GraphRAG: Dynamic Local Knowledge Graph Construction for Online Reasoning

This is our implementation for the paper titled **Query-Driven Multimodal GraphRAG: Dynamic Local Knowledge Graph Construction for Online Reasoning**

**Abstract**: An increasing adoption of Large Language Models (LLMs) in complex reasoning tasks necessitates their  interpretability and reliability. 
Recent advances to that end include retrieval-augmented generation (RAG) and knowledge graph-enhanced RAG (GraphRAG), whereas they are constrained by static knowledge bases and ineffective multimodal data integration. In response, we propose a Query-Driven Multimodal GraphRAG framework that dynamically constructs local knowledge graphs tailored to query semantics. Our approach 1) derives graph patterns from query semantics to guide knowledge extraction, 2) employs a multi-path retrieval strategy to pinpoint core knowledge, and 3) supplements missing multimodal information ad hoc. Experimental results on the MultimodalQA and WebQA datasets demonstrate that our framework achieves the state-of-the-art performance among unsupervised competitors, particularly excelling in cross-modal understanding of complex queries.

## Framework

![Framework](./image/main_framework.png)


##   Environment Settings

### Dependencies

```
- python==3.8
- pytorch==2.4.0
```

### Files

This is the code structure of the repository. It mainly includes the following files, with corresponding explanations of their functionalities:


- eval # This file is used for operations to obtain metrics on the MutimodalQA dataset.
  - common_utils.py
  - evaluate.py
- util #For managing network requests
  - request.py
- result # our results in webqa and multimodalqa.
  - webqa_result.json
  - multimodalqa_result.json
- construct.py # For Retrieval Graph construction.
- extraction.py # For relational extraction.
- pattern.py # For Graph pattern construction.
- inference.py # For inference
- pattern.py # For Graph pattern construction.
- prompt.py 
- README.md # This file provides documentation and instructions on how to use the codebase.


##   Run Steps

To execute this program properly, follow the sequence: pattern.py, extraction.py, construct.py, inference.py, and evaluate.py.

## Our Results

MutimodalQA result:

![Framework](./image/MutimodalQA.png)

WebQA result:

![Framework](./image/WebQA.png)

### Datasets

[MutimodalQA](https://github.com/allenai/multimodalqa)

[WebQA](https://github.com/WebQnA/WebQA)

## Citation

If you find this work useful, please cite our paper:

```bibtex
@inproceedings{bu-etal-2025-query,
    title = "Query-Driven Multimodal {G}raph{RAG}: Dynamic Local Knowledge Graph Construction for Online Reasoning",
    author = "Bu, Chenyang and Chang, Guojie and Chen, Zihao and Dang, CunYuan and Wu, Zhize and He, Yi and Wu, Xindong",
    booktitle = "Findings of the Association for Computational Linguistics: ACL 2025",
    year = "2025",
    url = "https://aclanthology.org/2025.findings-acl.1100/",
    doi = "10.18653/v1/2025.findings-acl.1100",
    pages = "21360--21380"
}
```