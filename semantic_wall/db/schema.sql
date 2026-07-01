-- Semantic Wall — Phase 1 schema.
-- Run this in the Supabase SQL editor (or via `supabase db push`) on a
-- fresh Supabase project before setting SUPABASE_URL/SUPABASE_KEY.

create extension if not exists vector;
create extension if not exists pgcrypto; -- provides gen_random_uuid() on Postgres < 13

create table if not exists memories (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    agent_id text not null default 'strategist',
    session_id text not null,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    embedding vector(3072) not null,
    topic_tags text[] not null default '{}',
    outcome_verified boolean,
    quality_score smallint check (quality_score between 1 and 5),
    created_at timestamptz not null default now()
);

create index if not exists memories_user_id_idx on memories (user_id);
create index if not exists memories_session_id_idx on memories (session_id);
-- ivfflat requires an ANALYZE after enough rows exist; fine to create empty.
create index if not exists memories_embedding_idx
    on memories using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create table if not exists checkins (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    session_id text not null,
    agent_id text not null,
    completed boolean not null,
    quality_rating smallint check (quality_rating between 1 and 5),
    improvement_note text,
    used_in_real_work boolean,
    willingness_to_pay text check (willingness_to_pay in ('yes', 'no', 'maybe')),
    price_point_cents integer,
    created_at timestamptz not null default now()
);

create index if not exists checkins_user_id_idx on checkins (user_id);
create index if not exists checkins_session_id_idx on checkins (session_id);

-- Row-level security: each row is only visible to its own user_id.
-- Phase 1 uses the Supabase service-role key server-side (RLS bypassed by
-- design, matching the blueprint's own "server enforces isolation" model)
-- but policies are defined now so client-side/anon access is safe by
-- default the moment it's introduced later.
alter table memories enable row level security;
alter table checkins enable row level security;

drop policy if exists memories_isolation on memories;
create policy memories_isolation on memories
    using (user_id = current_setting('request.jwt.claim.sub', true))
    with check (user_id = current_setting('request.jwt.claim.sub', true));

drop policy if exists checkins_isolation on checkins;
create policy checkins_isolation on checkins
    using (user_id = current_setting('request.jwt.claim.sub', true))
    with check (user_id = current_setting('request.jwt.claim.sub', true));

-- Top-K cosine similarity search, callable via client.rpc("match_memories", ...).
create or replace function match_memories(
    query_embedding vector(3072),
    match_user_id text,
    match_count int default 10
)
returns table (
    id uuid,
    agent_id text,
    session_id text,
    role text,
    content text,
    topic_tags text[],
    outcome_verified boolean,
    quality_score smallint,
    created_at timestamptz,
    similarity float
)
language sql stable
as $$
    select
        memories.id,
        memories.agent_id,
        memories.session_id,
        memories.role,
        memories.content,
        memories.topic_tags,
        memories.outcome_verified,
        memories.quality_score,
        memories.created_at,
        1 - (memories.embedding <=> query_embedding) as similarity
    from memories
    where memories.user_id = match_user_id
    order by memories.embedding <=> query_embedding
    limit match_count;
$$;
