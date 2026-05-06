"""Hard gates: drop JD/marketing fluff; keep plausible technical vocabulary."""

from src.services.skill_normalization import BASE_NOISE_TERMS
from src.services.skill_normalization import NON_SKILL_TERMS

# Common JD copy verbs/nouns/adjectives — not teachable tooling (extend as needed).
FLUFF_REJECT: frozenset[str] = frozenset({
    "across", "ability", "able", "actively", "agile", "all", "also", "analyst", "analytics",
    "based", "best", "better", "build", "building", "built", "business", "candidate", "capabilities",
    "career", "challenging", "collaborate", "collaboration", "collaborative", "complex", "confidence",
    "confident", "consulting", "contribute", "contributor", "core", "create", "creative", "critical",
    "culture", "cutting", "cutting-edge", "cuttingedge", "deliver", "deliverables", "delivery",
    "delivery-focused", "depth", "design", "development", "direct", "digital", "diverse",
    "drive", "driven", "dynamic", "edge", "energetic", "engagement", "enjoy", "enterprise",
    "environment", "environments", "established", "excellent", "excited",
    "experience", "experienced", "expertise", "exposure", "fast", "fast-paced", "feature",
    "features", "first", "focus", "focused", "forward", "framework", "frameworks",
    "fully", "function", "functions", "fun", "global", "globa", "goals", "great", "growing",
    "growth", "hands-on", "handson", "health", "help", "helps", "high", "impact", "impacts",
    "implement", "implementation", "inclusive", "industry", "innovative", "insights", "intelligent",
    "interdisciplinary", "interpersonal", "key", "knowledge", "leading", "lean", "level",
    "levels", "leverage", "like", "long", "maintain", "make", "making", "managing", "mark",
    "meaningful", "mission", "modeling", "more", "multidisciplinary", "must", "new", "next",
    "non-data", "notable", "objectives", "opportunity", "optional", "organization", "organizations",
    "other", "outcomes", "outstanding", "over", "own", "pace", "passion", "passionate", "patterns",
    "people", "play", "plays", "plus", "pod", "presence", "problems", "process", "processes",
    "product", "products", "program", "programme", "practices", "practical", "problem",
    "professional", "proven", "provider", "pride", "quality", "range", "readiness", "real",
    "recommend", "regulations", "regulated", "regulated-by-design", "resource", "responsible",
    "roadmap", "robust", "role", "role-based", "root", "scale", "scaled", "scales",
    "scalable", "scientists", "seeking", "senior", "serve", "serves", "service", "services",
    "shape", "sits", "skilled", "skillset", "smarter", "social", "softer", "software",
    "solution", "solutioning", "solutions", "some", "solve", "solving", "sophisticated", "spirit",
    "standards", "stakeholder", "stakeholders", "strategic", "strategy", "strong", "strongly",
    "structure", "success", "support", "supporting", "systems", "system", "talent", "team",
    "teams", "technologies", "technology", "thorough", "thrives", "through", "title", "today",
    "together", "top", "transformation", "transform", "trends", "understand", "understanding",
    "unique", "user", "using", "value", "vendor", "vendors", "vision", "work", "world",
    "world-class", "write", "writing", "year", "years", "young", "yours",
})

KNOWN_TECH_TERMS: frozenset[str] = frozenset({
    # languages
    "python", "java", "scala", "kotlin", "golang", "go", "rust", "swift", "ruby", "php", "perl",
    "r", "c", "c++", "c#", "javascript", "typescript", "julia", "matlab",
    # web / mobile
    "html", "css", "react", "next.js", "angular", "vue", "django", "flask", "fastapi",
    "node.js", "express", "spring", ".net",
    # data / ML
    "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow", "keras", "xgboost", "lightgbm",
    "spark", "hadoop", "hive", "presto", "trino", "flink", "kafka", "pulsar",
    "airflow", "luigi", "prefect", "dagster",
    "dbt", "snowflake", "bigquery", "redshift", "databricks",
    "llm", "llms", "langchain", "llamaindex", "vectordb", "vector_database", "mlops",
    "jupyter", "mlflow",
    # databases / stores
    "postgresql", "postgres", "mysql", "mongodb", "redis", "cassandra", "dynamodb", "elasticsearch",
    "sqlite", "neo4j",
    # cloud / infra
    "aws", "amazon", "amazon s3", "amazon ec2", "lambda", "azure", "gcp",
    "google cloud platform", "kubernetes", "k8s", "docker", "terraform", "ansible", "helm",
    "jenkins", "github actions", "gitlab ci", "ci cd",
    # protocols / apis
    "graphql", "grpc", "rest", "http", "https", "oauth", "jwt", "tcp", "udp", "dns", "vpc",
    "sdlc", "etl", "elt",
    # security / tooling
    "linux", "bash", "bash scripting", "shell", "powershell", "git",
    # misc common
    "sql", "nosql", "openapi", "protobuf", "regex", "oop", "tdd",
})


TECH_HINT_TERMS: frozenset[str] = frozenset({
    "api", "sdk", "sql", "aws", "gcp", "azure", "k8s", "ml", "ai", "nlp", "etl",
    "elt", "iac", "ui", "ux", "cli", "ssd", "gpu", "ci", "cd", "cdn", "orm", "crud",
})


TECH_SUFFIX_ALLOW: tuple[str, ...] = (
    "sql",
    ".js",
    ".ts",
    ".py",
    ".rb",
    ".go",
    "api",
    "sdk",
)


def _single_token_signals(token: str) -> bool:
    if any(ch.isdigit() for ch in token):
        return True
    if any(sym in token for sym in "+#/.-"):
        return True
    lower = token.lower()
    if any(lower.endswith(suf) for suf in TECH_SUFFIX_ALLOW):
        return True
    return False


def is_technical_skill(term: str) -> bool:
    """Hard filter: rejects generic JD language; permits known tooling and structured tokens."""
    t = term.strip().lower()
    if not t or len(t) < 2 or len(t) > 72:
        return False
    if t in BASE_NOISE_TERMS or t in NON_SKILL_TERMS:
        return False
    if t in FLUFF_REJECT:
        return False
    if t in KNOWN_TECH_TERMS:
        return True
    parts = t.split()
    if len(parts) > 1:
        if any(p in KNOWN_TECH_TERMS or p in TECH_HINT_TERMS for p in parts):
            return True
        if any(_single_token_signals(p) for p in parts):
            return True
        return False
    if _single_token_signals(t):
        return True
    if t in TECH_HINT_TERMS:
        return True
    return False


def filter_technical_skills(skills: list[str], limit: int | None = None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for s in skills:
        normalized = s.strip().lower()
        if not normalized or normalized in seen:
            continue
        if not is_technical_skill(normalized):
            continue
        seen.add(normalized)
        ordered.append(normalized)
        if limit is not None and len(ordered) >= limit:
            break
    return ordered
