-- mart: fct_skill_mentions
-- Grain: one row per (job, skill) at the posting's latest version.

select
    s.mention_id,
    s.job_key,
    s.skill,
    s.skill_category,
    j.role_family,
    j.seniority,
    j.salary_mid_usd,
    j.globally_remote,
    j.is_active,
    j.first_seen_date
from {{ ref('int_skill_mentions') }} s
join {{ ref('fct_job_postings') }} j using (job_key)
