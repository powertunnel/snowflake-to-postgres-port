-- Customer Segmentation using RFM and behavioral patterns
-- Groups customers into actionable segments

with clv as (
    select * from {{ ref('customer_lifetime_value') }}
),

segmentation as (
    select
        customer_id,
        customer_name,
        customer_segment,
        signup_date,
        
        -- RFM metrics
        recency_score,
        frequency_score,
        monetary_score,
        rfm_score,
        
        -- Value metrics
        total_revenue,
        total_orders,
        avg_order_value,
        value_tier,
        customer_status,
        
        -- Behavioral segment based on RFM
        case
            when recency_score >= 8 and frequency_score >= 8 and monetary_score >= 8 
                then 'champions'
            when recency_score >= 6 and frequency_score >= 6 and monetary_score >= 6 
                then 'loyal_customers'
            when recency_score >= 8 and frequency_score <= 4 and monetary_score >= 6 
                then 'potential_loyalists'
            when recency_score >= 6 and frequency_score <= 4 and monetary_score <= 4 
                then 'promising'
            when recency_score <= 4 and frequency_score >= 6 and monetary_score >= 6 
                then 'at_risk'
            when recency_score <= 2 and frequency_score >= 6 and monetary_score >= 6 
                then 'cant_lose_them'
            when recency_score <= 4 and frequency_score <= 4 and monetary_score >= 6 
                then 'hibernating_high_value'
            when recency_score <= 2 and frequency_score <= 4 and monetary_score <= 4 
                then 'lost'
            when recency_score >= 6 and frequency_score <= 2 and monetary_score <= 4 
                then 'new_customers'
            else 'needs_attention'
        end as behavioral_segment,
        
        -- Recommended action
        case
            when recency_score >= 8 and frequency_score >= 8 and monetary_score >= 8 
                then 'Reward and retain with VIP benefits'
            when recency_score >= 6 and frequency_score >= 6 and monetary_score >= 6 
                then 'Upsell and cross-sell opportunities'
            when recency_score >= 8 and frequency_score <= 4 and monetary_score >= 6 
                then 'Engage with loyalty program'
            when recency_score >= 6 and frequency_score <= 4 and monetary_score <= 4 
                then 'Nurture with targeted offers'
            when recency_score <= 4 and frequency_score >= 6 and monetary_score >= 6 
                then 'Win back with personalized campaigns'
            when recency_score <= 2 and frequency_score >= 6 and monetary_score >= 6 
                then 'Aggressive retention strategy required'
            when recency_score <= 4 and frequency_score <= 4 and monetary_score >= 6 
                then 'Reactivation campaign'
            when recency_score <= 2 and frequency_score <= 4 and monetary_score <= 4 
                then 'Low priority - minimal investment'
            when recency_score >= 6 and frequency_score <= 2 and monetary_score <= 4 
                then 'Onboarding and education'
            else 'Analyze and segment further'
        end as recommended_action

    from clv
),

prioritized as (
    select
        *,
        -- Segment priority (for marketing resource allocation)
        -- NOTE (postgres port): references behavioral_segment, so it must live in a
        -- separate select — Postgres has no Snowflake-style lateral column aliasing.
        case
            when behavioral_segment in ('champions', 'loyal_customers') then 1
            when behavioral_segment in ('at_risk', 'cant_lose_them') then 2
            when behavioral_segment in ('potential_loyalists', 'hibernating_high_value') then 3
            when behavioral_segment in ('promising', 'new_customers') then 4
            else 5
        end as segment_priority

    from segmentation
)

select * from prioritized
