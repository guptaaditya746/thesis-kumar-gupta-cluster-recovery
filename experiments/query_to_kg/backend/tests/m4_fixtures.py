QUESTION = "Which paper proposes a reinforcement-learning approach for knowledge graph construction?"
LIGHTRAG_QUESTION = "Which paper argues that graph structures improve retrieval by capturing relationships between entities?"
MIND_THE_QUERY_QUESTION = "Which paper discusses validation of generated graph queries?"


def autograph_patch() -> dict:
    return {
        "nodes": [
            {
                "id": "paper:autograph_r1",
                "type": "Paper",
                "label": "AutoGraph-R1",
                "properties": {
                    "name": "AutoGraph-R1",
                    "title": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                },
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_preamble_0001",
                    "text_span": "## AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "paper_title": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "section_title": "Preamble",
                },
            },
            {
                "id": "method:autograph_r1",
                "type": "Method",
                "label": "AutoGraph-R1",
                "properties": {
                    "name": "AutoGraph-R1",
                    "description": "An end-to-end reinforcement learning framework for knowledge graph construction.",
                },
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "we introduce AutoGraph-R1, the first framework to directly optimize KG construction for task performance using Reinforcement Learning (RL).",
                    "paper_title": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "section_title": "Abstract",
                },
            },
            {
                "id": "task:knowledge_graph_construction",
                "type": "Task",
                "label": "Knowledge graph construction",
                "properties": {
                    "name": "Knowledge graph construction",
                },
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "we introduce AutoGraph-R1, the first framework to directly optimize KG construction for task performance using Reinforcement Learning (RL).",
                    "paper_title": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "section_title": "Abstract",
                },
            },
            {
                "id": "evidence:autograph_r1_abstract_0001",
                "type": "Evidence",
                "label": "AutoGraph-R1 RL evidence",
                "properties": {
                    "text": "AutoGraph-R1 trains an LLM constructor by framing graph generation as a policy learning problem, where the reward is derived from the graph's functional utility in a RAG pipeline.",
                },
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "AutoGraph-R1 trains an LLM constructor by framing graph generation as a policy learning problem, where the reward is derived from the graph's functional utility in a RAG pipeline.",
                    "paper_title": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "section_title": "Abstract",
                },
            },
        ],
        "edges": [
            {
                "source": "paper:autograph_r1",
                "target": "method:autograph_r1",
                "type": "PROPOSES",
                "properties": {},
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "we introduce AutoGraph-R1, the first framework to directly optimize KG construction for task performance using Reinforcement Learning (RL).",
                    "paper_title": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "section_title": "Abstract",
                },
            },
            {
                "source": "method:autograph_r1",
                "target": "task:knowledge_graph_construction",
                "type": "ADDRESSES_TASK",
                "properties": {},
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "we introduce AutoGraph-R1, the first framework to directly optimize KG construction for task performance using Reinforcement Learning (RL).",
                    "paper_title": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "section_title": "Abstract",
                },
            },
            {
                "source": "method:autograph_r1",
                "target": "evidence:autograph_r1_abstract_0001",
                "type": "SUPPORTED_BY",
                "properties": {},
                "provenance": {
                    "paper_id": "autograph_r1",
                    "chunk_id": "autograph_r1_abstract_0001",
                    "text_span": "AutoGraph-R1 trains an LLM constructor by framing graph generation as a policy learning problem, where the reward is derived from the graph's functional utility in a RAG pipeline.",
                    "paper_title": "AutoGraph-R1: End-to-End Reinforcement Learning for Knowledge Graph Construction",
                    "section_title": "Abstract",
                },
            },
        ],
    }


def lightrag_patch() -> dict:
    return {
        "nodes": [
            {
                "id": "paper:lightrag",
                "type": "Paper",
                "label": "LightRAG",
                "properties": {
                    "name": "LightRAG",
                    "title": "LightRAG",
                },
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "lightrag_preamble_0001",
                    "text_span": "## LIGHTRAG: SIMPLE AND FAST RETRIEVAL-AUGMENTED GENERATION",
                    "paper_title": "LightRAG",
                    "section_title": "Preamble",
                },
            },
            {
                "id": "claim:lightrag_retrieval",
                "type": "Claim",
                "label": "Graph structures improve retrieval",
                "properties": {
                    "text": "Additionally, the integration of graph structures with vector representations facilitates efficient retrieval of related entities and their relationships, significantly improving response times while maintaining contextual relevance.",
                },
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "lightrag_abstract_0001",
                    "text_span": "Additionally, the integration of graph structures with vector representations facilitates efficient retrieval of related entities and their relationships, significantly improving response times while maintaining contextual relevance.",
                    "paper_title": "LightRAG",
                    "section_title": "Abstract",
                },
            },
            {
                "id": "evidence:lightrag_intro_0001",
                "type": "Evidence",
                "label": "LightRAG relationships evidence",
                "properties": {
                    "text": "Graphs are particularly effective at representing the interdependencies among different entities, which enables a more nuanced understanding of relationships.",
                },
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "lightrag_introduction_0001",
                    "text_span": "Graphs are particularly effective at representing the interdependencies among different entities, which enables a more nuanced understanding of relationships.",
                    "paper_title": "LightRAG",
                    "section_title": "Introduction",
                },
            },
        ],
        "edges": [
            {
                "source": "paper:lightrag",
                "target": "claim:lightrag_retrieval",
                "type": "MAKES_CLAIM",
                "properties": {},
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "lightrag_abstract_0001",
                    "text_span": "To address these challenges, we propose LightRAG, which incorporates graph structures into text indexing and retrieval processes.",
                    "paper_title": "LightRAG",
                    "section_title": "Abstract",
                },
            },
            {
                "source": "claim:lightrag_retrieval",
                "target": "evidence:lightrag_intro_0001",
                "type": "SUPPORTED_BY",
                "properties": {},
                "provenance": {
                    "paper_id": "lightrag",
                    "chunk_id": "lightrag_introduction_0001",
                    "text_span": "Graphs are particularly effective at representing the interdependencies among different entities, which enables a more nuanced understanding of relationships.",
                    "paper_title": "LightRAG",
                    "section_title": "Introduction",
                },
            },
        ],
    }


def mind_the_query_patch() -> dict:
    return {
        "nodes": [
            {
                "id": "paper:mind_the_query",
                "type": "Paper",
                "label": "Mind the Query",
                "properties": {
                    "name": "Mind the Query",
                    "title": "Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                },
                "provenance": {
                    "paper_id": "mind_the_query",
                    "chunk_id": "mind_the_query_preamble_0001",
                    "text_span": "## Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                    "paper_title": "Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                    "section_title": "Preamble",
                },
            },
            {
                "id": "claim:mind_the_query_validation",
                "type": "Claim",
                "label": "Graph query validation guidance",
                "properties": {
                    "text": "Validation of generated graph queries depends on schema fidelity, exact value matching, logical correctness, and runtime compatibility.",
                },
                "provenance": {
                    "paper_id": "mind_the_query",
                    "chunk_id": "mind_the_query_limitations_0001",
                    "text_span": "Boosted fidelity to schema structure and values.",
                    "paper_title": "Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                    "section_title": "Limitations",
                },
            },
            {
                "id": "benchmark:mind_the_query_text2cypher",
                "type": "Benchmark",
                "label": "Text2Cypher benchmark dataset",
                "properties": {
                    "name": "Text2Cypher benchmark dataset",
                    "description": "A multi-domain benchmark dataset for natural language to Cypher generation.",
                },
                "provenance": {
                    "paper_id": "mind_the_query",
                    "chunk_id": "mind_the_query_abstract_0001",
                    "text_span": "We present a high-quality, multi-domain dataset for the Text2Cypher task which is enabling the translation of natural language (NL) questions into executable Cypher queries over graph databases.",
                    "paper_title": "Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                    "section_title": "Abstract",
                },
            },
            {
                "id": "evidence:mind_the_query_limitations_0001",
                "type": "Evidence",
                "label": "Mind the Query validation evidence",
                "properties": {
                    "text": "Prevented runtime mismatch errors during execution.",
                },
                "provenance": {
                    "paper_id": "mind_the_query",
                    "chunk_id": "mind_the_query_limitations_0001",
                    "text_span": "Prevented runtime mismatch errors during execution.",
                    "paper_title": "Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                    "section_title": "Limitations",
                },
            },
        ],
        "edges": [
            {
                "source": "paper:mind_the_query",
                "target": "claim:mind_the_query_validation",
                "type": "DESCRIBES",
                "properties": {},
                "provenance": {
                    "paper_id": "mind_the_query",
                    "chunk_id": "mind_the_query_limitations_0001",
                    "text_span": "Boosted fidelity to schema structure and values.",
                    "paper_title": "Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                    "section_title": "Limitations",
                },
            },
            {
                "source": "claim:mind_the_query_validation",
                "target": "evidence:mind_the_query_limitations_0001",
                "type": "SUPPORTED_BY",
                "properties": {},
                "provenance": {
                    "paper_id": "mind_the_query",
                    "chunk_id": "mind_the_query_limitations_0001",
                    "text_span": "Prevented runtime mismatch errors during execution.",
                    "paper_title": "Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                    "section_title": "Limitations",
                },
            },
            {
                "source": "paper:mind_the_query",
                "target": "benchmark:mind_the_query_text2cypher",
                "type": "EVALUATES_ON",
                "properties": {},
                "provenance": {
                    "paper_id": "mind_the_query",
                    "chunk_id": "mind_the_query_abstract_0001",
                    "text_span": "The dataset comprises 27,529 NL queries and corresponding Cyphers spanning across 11 real-world graph datasets,",
                    "paper_title": "Mind the Query: A Benchmark Dataset towards Text2Cypher Task",
                    "section_title": "Abstract",
                },
            },
        ],
    }


DEMO_CASES = [
    (
        "autograph",
        QUESTION,
        autograph_patch,
        ["AutoGraph-R1", "reinforcement"],
    ),
    (
        "lightrag",
        LIGHTRAG_QUESTION,
        lightrag_patch,
        ["LightRAG", "relationship"],
    ),
    (
        "mind_the_query",
        MIND_THE_QUERY_QUESTION,
        mind_the_query_patch,
        ["Mind the Query", "runtime"],
    ),
]
