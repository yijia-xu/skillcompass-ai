CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS job_postings (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    posted_at DATE NOT NULL,
    role_family TEXT NOT NULL,
    skills_text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_postings_role_family ON job_postings (role_family);
CREATE INDEX IF NOT EXISTS idx_job_postings_posted_at ON job_postings (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_postings_embedding
ON job_postings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY,
    target_role TEXT NOT NULL,
    resume_text TEXT NOT NULL,
    parsed_skills_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skill_taxonomy (
    skill_name TEXT PRIMARY KEY,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    category TEXT NOT NULL,
    prerequisites_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
