-- mart: agg_skill_demand
-- Grain: one row per skill. Demand = share of currently-active postings
-- mentioning it; salary signal = median midpoint of postings that mention it.

select
    m.skill,
    m.skill_category,
    count(*)                                                        as n_jobs,
    round(100.0 * count(*) / max(tot.total_active), 1)              as share_of_active_pct,
    round(quantile_cont(m.salary_mid_usd, 0.5), 0)                  as median_salary_mid_usd,
    countif(m.salary_mid_usd is not null)                           as n_with_salary
from {{ ref('fct_skill_mentions') }} m
cross join (select count(*) as total_active
            from {{ ref('fct_job_postings') }} where is_active) tot
where m.is_active
group by m.skill, m.skill_category
having count(*) >= 2
order by n_jobs desc
