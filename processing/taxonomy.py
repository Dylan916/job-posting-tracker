"""Curated skills taxonomy with compiled regex patterns for high-precision extraction."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    category: str
    pattern: re.Pattern[str]


SKILL_TAXONOMY: list[SkillDefinition] = [
    # 1. Programming Languages
    SkillDefinition("Python", "Languages", re.compile(r"\b(python|python3|pypy)\b", re.IGNORECASE)),
    SkillDefinition("Java", "Languages", re.compile(r"\bjava\b(?!script)", re.IGNORECASE)),
    SkillDefinition("C++", "Languages", re.compile(r"\b(c\+\+|cpp)\b", re.IGNORECASE)),
    SkillDefinition("C#", "Languages", re.compile(r"\b(c#|csharp|\.net)\b", re.IGNORECASE)),
    SkillDefinition("Go", "Languages", re.compile(r"\b(golang|go\s+developer|go\s+engineer|go\s+backend)\b|\bGo\b")),
    SkillDefinition("Rust", "Languages", re.compile(r"\brust\b", re.IGNORECASE)),
    SkillDefinition("TypeScript", "Languages", re.compile(r"\b(typescript|ts)\b", re.IGNORECASE)),
    SkillDefinition("JavaScript", "Languages", re.compile(r"\b(javascript|js|es6)\b", re.IGNORECASE)),
    SkillDefinition("SQL", "Languages", re.compile(r"\b(sql|pl/sql|t-sql)\b", re.IGNORECASE)),
    SkillDefinition("Kotlin", "Languages", re.compile(r"\bkotlin\b", re.IGNORECASE)),
    SkillDefinition("Swift", "Languages", re.compile(r"\bswift\b", re.IGNORECASE)),
    SkillDefinition("Scala", "Languages", re.compile(r"\bscala\b", re.IGNORECASE)),
    SkillDefinition("Ruby", "Languages", re.compile(r"\bruby(\s+on\s+rails)?\b", re.IGNORECASE)),
    SkillDefinition("R", "Languages", re.compile(r"\b(r\s+programming|r\s+language|r-studio)\b", re.IGNORECASE)),

    # 2. Cloud & DevOps
    SkillDefinition("AWS", "Cloud & DevOps", re.compile(r"\b(aws|amazon\s+web\s+services|ec2|s3|lambda|dynamodb)\b", re.IGNORECASE)),
    SkillDefinition("Azure", "Cloud & DevOps", re.compile(r"\b(azure|microsoft\s+azure)\b", re.IGNORECASE)),
    SkillDefinition("GCP", "Cloud & DevOps", re.compile(r"\b(gcp|google\s+cloud|bigquery)\b", re.IGNORECASE)),
    SkillDefinition("Docker", "Cloud & DevOps", re.compile(r"\bdocker\b", re.IGNORECASE)),
    SkillDefinition("Kubernetes", "Cloud & DevOps", re.compile(r"\b(kubernetes|k8s)\b", re.IGNORECASE)),
    SkillDefinition("Terraform", "Cloud & DevOps", re.compile(r"\bterraform\b", re.IGNORECASE)),
    SkillDefinition("Linux", "Cloud & DevOps", re.compile(r"\b(linux|unix|bash|shell\s+scripting)\b", re.IGNORECASE)),
    SkillDefinition("CI/CD", "Cloud & DevOps", re.compile(r"\b(ci/cd|github\s+actions|gitlab\s+ci|jenkins)\b", re.IGNORECASE)),
    SkillDefinition("Git", "Cloud & DevOps", re.compile(r"\b(git|github|gitlab)\b", re.IGNORECASE)),

    # 3. Data & AI/ML
    SkillDefinition("PyTorch", "Data & AI/ML", re.compile(r"\bpytorch\b", re.IGNORECASE)),
    SkillDefinition("TensorFlow", "Data & AI/ML", re.compile(r"\b(tensorflow|keras)\b", re.IGNORECASE)),
    SkillDefinition("Spark", "Data & AI/ML", re.compile(r"\b(apache\s+spark|pyspark|spark)\b", re.IGNORECASE)),
    SkillDefinition("Kafka", "Data & AI/ML", re.compile(r"\b(apache\s+kafka|kafka)\b", re.IGNORECASE)),
    SkillDefinition("Airflow", "Data & AI/ML", re.compile(r"\b(apache\s+airflow|airflow)\b", re.IGNORECASE)),
    SkillDefinition("Dagster", "Data & AI/ML", re.compile(r"\bdagster\b", re.IGNORECASE)),
    SkillDefinition("Snowflake", "Data & AI/ML", re.compile(r"\bsnowflake\b", re.IGNORECASE)),
    SkillDefinition("Databricks", "Data & AI/ML", re.compile(r"\bdatabricks\b", re.IGNORECASE)),
    SkillDefinition("dbt", "Data & AI/ML", re.compile(r"\b(dbt|data\s+build\s+tool)\b", re.IGNORECASE)),
    SkillDefinition("Pandas", "Data & AI/ML", re.compile(r"\b(pandas|numpy|scipy)\b", re.IGNORECASE)),
    SkillDefinition("LLMs / AI", "Data & AI/ML", re.compile(r"\b(llms?|large\s+language\s+models?|langchain|llamaindex|rag|generative\s+ai|genai)\b", re.IGNORECASE)),
    SkillDefinition("Computer Vision", "Data & AI/ML", re.compile(r"\b(computer\s+vision|opencv|yolo)\b", re.IGNORECASE)),
    SkillDefinition("NLP", "Data & AI/ML", re.compile(r"\b(nlp|natural\s+language\s+processing|bert|transformers)\b", re.IGNORECASE)),

    # 4. Web & Frameworks
    SkillDefinition("React", "Frameworks", re.compile(r"\b(react|react\.js|reactjs)\b", re.IGNORECASE)),
    SkillDefinition("Next.js", "Frameworks", re.compile(r"\b(next\.js|nextjs)\b", re.IGNORECASE)),
    SkillDefinition("Node.js", "Frameworks", re.compile(r"\b(node\.js|nodejs)\b", re.IGNORECASE)),
    SkillDefinition("FastAPI", "Frameworks", re.compile(r"\bfastapi\b", re.IGNORECASE)),
    SkillDefinition("Django", "Frameworks", re.compile(r"\bdjango\b", re.IGNORECASE)),
    SkillDefinition("Spring Boot", "Frameworks", re.compile(r"\b(spring\s+boot|spring\s+framework)\b", re.IGNORECASE)),
    SkillDefinition("GraphQL", "Frameworks", re.compile(r"\bgraphql\b", re.IGNORECASE)),
    SkillDefinition("REST APIs", "Frameworks", re.compile(r"\b(rest|restful|rest\s+apis?)\b", re.IGNORECASE)),

    # 5. Databases
    SkillDefinition("PostgreSQL", "Databases", re.compile(r"\b(postgresql|postgres)\b", re.IGNORECASE)),
    SkillDefinition("MySQL", "Databases", re.compile(r"\bmysql\b", re.IGNORECASE)),
    SkillDefinition("MongoDB", "Databases", re.compile(r"\b(mongodb|mongo)\b", re.IGNORECASE)),
    SkillDefinition("Redis", "Databases", re.compile(r"\bredis\b", re.IGNORECASE)),
    SkillDefinition("Elasticsearch", "Databases", re.compile(r"\b(elasticsearch|elastic\s+search)\b", re.IGNORECASE)),
    SkillDefinition("Vector DB", "Databases", re.compile(r"\b(pinecone|milvus|chromadb|weaviate|qdrant)\b", re.IGNORECASE)),
]
