{{ config(materialized='incremental', unique_key=['business_date', 'site_id']) }}

SELECT
    business_date,
    site_id,
    SUM(gross_margin) AS gross_margin,
FROM {{ ref('stg_site_transactions') }}
{% if is_incremental() %}
WHERE business_date >= (SELECT MAX(business_date) FROM {{ this }}) - 3
{% endif %}
GROUP BY business_date, site_id
