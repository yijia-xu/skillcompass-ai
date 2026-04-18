import json
import ssl
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import certifi

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"

CURATED_RESOURCES = {
    "python": [
        {"title": "Python Docs", "url": "https://docs.python.org/3/", "source": "official"},
    ],
    "sql": [
        {"title": "SQLBolt", "url": "https://sqlbolt.com/", "source": "course"},
        {"title": "PostgreSQL Docs", "url": "https://www.postgresql.org/docs/", "source": "official"},
    ],
    "airflow": [
        {
            "title": "Apache Airflow Docs",
            "url": "https://airflow.apache.org/docs/",
            "source": "official",
        }
    ],
    "dbt": [{"title": "dbt Learn", "url": "https://courses.getdbt.com/", "source": "course"}],
    "spark": [
        {
            "title": "Apache Spark Docs",
            "url": "https://spark.apache.org/docs/latest/",
            "source": "official",
        }
    ],
    "kafka": [
        {
            "title": "Apache Kafka Docs",
            "url": "https://kafka.apache.org/documentation/",
            "source": "official",
        }
    ],
}


def _fetch_github_roadmaps(skill: str, github_token: str = "", limit: int = 2) -> list[dict]:
    query = quote_plus(f"{skill} roadmap in:name,description stars:>20")
    url = f"{GITHUB_SEARCH_API}?q={query}&sort=stars&order=desc&per_page={limit}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GapSolverAI/0.1",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    request = Request(url, headers=headers)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(request, timeout=15, context=ssl_context) as response:
        payload = json.loads(response.read().decode("utf-8"))
    items = payload.get("items", [])
    return [
        {
            "title": item.get("full_name", "unknown_repo"),
            "url": item.get("html_url", ""),
            "source": "github_roadmap",
        }
        for item in items
        if item.get("html_url")
    ]


def discover_learning_resources(skills: list[str], github_token: str = "") -> dict[str, list[dict]]:
    resources: dict[str, list[dict]] = {}
    for skill in skills:
        normalized = skill.strip().lower()
        if not normalized:
            continue

        merged = list(CURATED_RESOURCES.get(normalized, []))
        try:
            merged.extend(_fetch_github_roadmaps(normalized, github_token=github_token))
        except Exception:
            # Keep planning robust even if GitHub API is unavailable/rate-limited.
            pass

        dedup = []
        seen = set()
        for item in merged:
            key = item["url"]
            if key in seen:
                continue
            seen.add(key)
            dedup.append(item)
        resources[normalized] = dedup[:4]
    return resources
