-- Staging: typed postings at snapshot grain.
-- Grain: one row per (source, external_id, snapshot_date).
select
    md5(source || ':' || external_id)                       as job_key,
    source,
    external_id,
    trim(title)                                             as title,
    trim(company)                                           as company,
    coalesce(nullif(trim(location_text), ''), 'unknown')    as location_text,
    tags,
    description_text,
    skills,                                                  -- ';'-joined taxonomy hits
    seniority,
    role_family,
    cast(salary_min_usd as double)                          as salary_min_usd,
    cast(salary_max_usd as double)                          as salary_max_usd,
    salary_source,
    try_cast(posted_at as timestamp)                        as posted_at,
    url,
    cast(fetched_at as timestamp)                           as fetched_at,
    cast(snapshot_date as date)                             as snapshot_date,
    -- locations employers phrase as "worldwide / anywhere / global" are open
    -- to Pakistan-based applicants — the angle this project cares about
    regexp_matches(lower(location_text),
                   'world|anywhere|global|earth|remote')    as globally_remote,
    regexp_matches(lower(location_text), 'pakistan|\bpk\b') as mentions_pakistan
from {{ source('raw', 'raw_job_postings') }}
