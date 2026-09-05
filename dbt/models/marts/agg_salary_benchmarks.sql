-- mart: agg_salary_benchmarks
-- Grain: one row per (role_family, seniority) · USD annual, remote market.

select
    role_family,
    seniority,
    count(*)                                  as n_postings,
    round(quantile_cont(salary_mid_usd, 0.25), 0)  as p25_usd,
    round(quantile_cont(salary_mid_usd, 0.5), 0)   as median_usd,
    round(quantile_cont(salary_mid_usd, 0.75), 0)  as p75_usd
from {{ ref('fct_job_postings') }}
where salary_mid_usd is not null
  and salary_mid_usd between 20000 and 600000    -- sanity band (test enforces raw)
group by role_family, seniority
having count(*) >= 2
order by median_usd desc
