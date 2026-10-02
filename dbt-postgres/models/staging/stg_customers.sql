-- Staging layer for customers
-- Lightweight transformations, data type casting, basic cleaning

with source as (
    select * from {{ source('raw', 'customers') }}
),

staged as (
    select
        customer_id,
        first_name || ' ' || last_name as customer_name,
        email,
        phone,
        address,
        city,
        state,
        zip_code,
        registration_date as signup_date,
        customer_segment,
        
        -- Derived fields
        datediff('day', registration_date, current_date) as days_since_signup,
        date_trunc('month', registration_date) as signup_month,
        date_trunc('year', registration_date) as signup_year
        
    from source
)

select * from staged
