-- mart: agg_skill_by_snapshot
-- Grain: one row per (snapshot_date, skill) — the trend series that weekly
-- runs accumulate. A skill counted for a snapshot if the posting was seen
-- in that snapshot (posting-version-agnostic on purpose: demand signal).

with exploded as (
    select
        s.snapshot_date,
        trim(unnest(string_split(s.skills, ';'))) as skill
    from {{ ref('stg_jobs') }} s
    where s.skills is not null and s.skills <> ''
)

select
    snapshot_date,
    skill,
    count(*) as n_jobs
from exploded
group by snapshot_date, skill
