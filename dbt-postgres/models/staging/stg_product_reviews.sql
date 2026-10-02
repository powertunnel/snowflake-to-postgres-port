with source as (
    select * from {{ source('raw', 'product_reviews') }}
),

staged as (
    select
        review_id,
        customer_id,
        product_id,
        rating,
        review_title,
        review_text,
        review_date,
        verified_purchase,

        -- Derived fields
        case
            when rating >= 4 then 'positive'
            when rating = 3 then 'neutral'
            else 'negative'
        end as sentiment_bucket,
        date_trunc('month', review_date) as review_month

    from source
)

select * from staged
