import re

BASE_NOISE_TERMS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "this",
    "that",
    "will",
    "into",
    "using",
    "used",
    "are",
    "our",
    "team",
    "work",
    "about",
    "have",
    "has",
    "job",
    "join",
    "experience",
    "responsible",
    "projects",
    "project",
}

NON_SKILL_TERMS = {
    "engineer",
    "engineering",
    "developer",
    "development",
    "software",
    "data",
    "role",
    "position",
    "company",
    "required",
    "preferred",
    "description",
    "expertise",
    "jobs",
    "looking",
    "application",
    "chance",
    "client",
    "clients",
    "business",
    "opportunity",
    "environment",
    "candidate",
    "responsibilities",
}

SKILL_ALIASES = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "node": "node.js",
    "nodejs": "node.js",
    "reactjs": "react",
    "nextjs": "next.js",
    "vuejs": "vue",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "k8s": "kubernetes",
    "gcp": "google cloud platform",
    "aws ec2": "amazon ec2",
    "aws s3": "amazon s3",
    "ci/cd": "ci cd",
    "ci-cd": "ci cd",
    "llms": "llm",
}

SPLIT_PATTERN = re.compile(r"[,;/\n]|(?:\s+\|\s+)|(?:\s+and\s+)")


def split_skill_phrases(value: str) -> list[str]:
    parts = [p.strip() for p in SPLIT_PATTERN.split(value) if p and p.strip()]
    return parts if parts else [value.strip()]


def normalize_skill(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    cleaned = re.sub(r"^[^a-z0-9+#.]+|[^a-z0-9+#.]+$", "", cleaned)
    if not cleaned or len(cleaned) < 2 or len(cleaned) > 64:
        return ""
    if "@" in cleaned or cleaned.startswith("http://") or cleaned.startswith("https://"):
        return ""
    if re.fullmatch(r"[0-9\W_]+", cleaned):
        return ""
    cleaned = SKILL_ALIASES.get(cleaned, cleaned)
    if cleaned in BASE_NOISE_TERMS or cleaned in NON_SKILL_TERMS:
        return ""
    return cleaned


def normalize_skills(values: list[str], limit: int = 50) -> list[str]:
    deduped: list[str] = []
    seen = set()
    for value in values:
        for piece in split_skill_phrases(value):
            normalized = normalize_skill(piece)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
            if len(deduped) >= limit:
                return deduped
    return deduped
