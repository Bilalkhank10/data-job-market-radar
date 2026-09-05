-- mart: fct_job_postings
-- Grain: one row per job (latest version) + lifecycle across snapshots.
--
-- Lifecycle: because the raw layer appends one row per job per snapshot,
-- first_seen / last_seen / days_listed derive posting longevity — a proxy
-- for how fast roles fill. Meaningful once the pipeline has run >= 2 weeks.

with latest as (
    select * from {{ ref('int_jobs_latest') }}
),

lifecycle as (
    select
        job_key,
        min(snapshot_date)                                  as first_seen_date,
        max(snapshot_date)                                  as last_seen_date,
        count(distinct snapshot_date)                       as snapshots_present
    from {{ ref('stg_jobs') }}
    group by job_key
),

bounds as (
    select max(snapshot_date) as market_snapshot from {{ ref('stg_jobs') }}
)

select
    l.job_key,
    l.source, l.external_id, l.title, l.company, l.location_text,
    l.seniority, l.role_family,
    l.salary_min_usd, l.salary_max_usd, l.salary_source,
    round((l.salary_min_usd + l.salary_max_usd) / 2.0, 0)   as salary_mid_usd,
    l.globally_remote, l.mentions_pakistan,
    l.posted_at, l.url,
    l.tags, l.skills,
    lc.first_seen_date, lc.last_seen_date, lc.snapshots_present,
    greatest(lc.last_seen_date - lc.first_seen_date, 0)     as days_listed_observed,
    lc.last_seen_date = (select market_snapshot from bounds) as is_active
from latest l
join lifecycle lc using (job_key)
