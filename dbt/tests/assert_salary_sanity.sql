{{ config(severity = 'warn') }}

-- Singular test (WARN): annual salaries outside a sane US-remote band
-- ($20k–$600k), inverted bounds, or a width > 4x almost always indicate
-- mis-scraped salary text (equity numbers, hourly rates parsed as annual,
-- monthly-annual confusion). Warn so the mart keeps flowing while the
-- parsing rules are hardened.
select job_key, title, salary_min_usd, salary_max_usd
from {{ ref('fct_job_postings') }}
where (salary_min_usd is not null or salary_max_usd is not null)
  and (
        salary_min_usd < 20000 or salary_max_usd > 600000
        or salary_min_usd > salary_max_usd
        or salary_max_usd > 4 * salary_min_usd
      )
