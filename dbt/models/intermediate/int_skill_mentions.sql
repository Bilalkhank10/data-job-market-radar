-- Explode the ';'-joined skill string into rows, joined to the taxonomy for
-- category. Latest version of each posting only — a skill reworded between
-- snapshots must not double-count.
-- Grain: one row per (job_key, skill).
with latest as (
    select job_key, skills from {{ ref('int_jobs_latest') }}
),

exploded as (
    select
        job_key,
        trim(unnest(string_split(skills, ';'))) as skill
    from latest
    where skills is not null and skills <> ''
)

select
    md5(e.job_key || '::' || e.skill)   as mention_id,
    e.job_key,
    e.skill,
    t.category                           as skill_category
from exploded e
join {{ ref('skill_taxonomy') }} t using (skill)
