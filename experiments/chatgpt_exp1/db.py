# db.py
from neo4j import GraphDatabase

_driver = None

def get_driver(uri: str, user: str, password: str):
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(uri, auth=(user, password))
    return _driver

def ensure_constraints(driver, schema):
    with driver.session() as s:
        for nt in schema.nodes:
            s.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{nt.label}) REQUIRE n.{nt.key} IS UNIQUE")

def upsert_extraction(driver, ex, schema):
    label_key = {nt.label: nt.key for nt in schema.nodes}

    def schema_key(label: str) -> str:
        if label not in label_key:
            raise ValueError(f"Unknown label in extraction: {label}. Known: {list(label_key)}")
        return label_key[label]

    with driver.session() as s:
        # Nodes
        for n in ex.nodes:
            label = n.ref.label
            key = schema_key(label)          # <-- ALWAYS from schema
            value = n.ref.value
            props = dict(n.properties or {})
            props.setdefault(key, value)

            cypher = f"""
            MERGE (x:{label} {{{key}: $value}})
            SET x += $props
            """
            s.run(cypher, value=value, props=props)

        # Relationships
        for r in ex.relationships:
            fl = r.from_ref.label
            tl = r.to_ref.label

            fk = schema_key(fl)              # <-- ALWAYS from schema
            tk = schema_key(tl)              # <-- ALWAYS from schema

            fv = r.from_ref.value
            tv = r.to_ref.value

            rtype = r.type
            props = dict(r.properties or {})

            cypher = f"""
            MATCH (a:{fl} {{{fk}: $from_value}})
            MATCH (b:{tl} {{{tk}: $to_value}})
            MERGE (a)-[rel:{rtype}]->(b)
            SET rel += $props
            """
            s.run(cypher, from_value=fv, to_value=tv, props=props)


def run_cypher(driver, cypher: str, params: dict):
    with driver.session() as s:
        return [r.data() for r in s.run(cypher, **(params or {}))]
