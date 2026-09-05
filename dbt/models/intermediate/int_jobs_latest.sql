-- Latest observed version of each posting (dedupe across snapshots).
-- Grain: one row per job_key.
select *
from {{ ref('stg_jobs') }}
qualify row_number() over (
    partition by job_key
    order by fetched_at desc, snapshot_date desc
) = 1
