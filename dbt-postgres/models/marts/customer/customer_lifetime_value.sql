-- Customer Lifetime Value (CLV) calculation
-- Analytical model for customer value metrics

with customer_orders as (
    select
        c.customer_id,
        c.customer_name,
        c.customer_segment,
        c.signup_date,
        c.days_since_signup,
        
        -- Order metrics
        count(o.order_id) as total_orders,
        coalesce(sum(o.total_amount), 0) as total_revenue,
        coalesce(avg(o.total_amount), 0) as avg_order_value,
        coalesce(sum(o.total_quantity), 0) as total_items_purchased,
        
        -- Date metrics
        min(o.order_date) as first_order_date,
        max(o.order_date) as last_order_date,
        datediff('day', min(o.order_date), max(o.order_date)) as customer_lifespan_days,
        datediff('day', max(o.order_date), current_date) as days_since_last_order
        
    from {{ ref('stg_customers') }} c
    left join {{ ref('stg_orders') }} o 
        on c.customer_id = o.customer_id
        and o.order_status in ('Completed', 'Shipped')
    group by 
        c.customer_id,
        c.customer_name,
        c.customer_segment,
        c.signup_date,
        c.days_since_signup
),

clv_calculation as (
    select
        *,
        
        -- CLV calculations
        total_revenue / nullif(days_since_signup, 0) * 365 as estimated_annual_value,
        case 
            when customer_lifespan_days > 0 
            then total_revenue / nullif(customer_lifespan_days, 0) * 365
            else total_revenue / nullif(days_since_signup, 0) * 365
        end as historical_annual_value,
        
        -- Frequency metrics
        total_orders / nullif(customer_lifespan_days, 0) * 30 as orders_per_month,
        
        -- Recency score (0-10, higher is better)
        case
            when days_since_last_order is null then 0
            when days_since_last_order <= 30 then 10
            when days_since_last_order <= 60 then 8
            when days_since_last_order <= 90 then 6
            when days_since_last_order <= 180 then 4
            when days_since_last_order <= 365 then 2
            else 0
        end as recency_score,
        
        -- Frequency score (0-10)
        case
            when total_orders >= 20 then 10
            when total_orders >= 15 then 8
            when total_orders >= 10 then 6
            when total_orders >= 5 then 4
            when total_orders >= 1 then 2
            else 0
        end as frequency_score,
        
        -- Monetary score (0-10)
        case
            when total_revenue >= 5000 then 10
            when total_revenue >= 2000 then 8
            when total_revenue >= 1000 then 6
            when total_revenue >= 500 then 4
            when total_revenue >= 100 then 2
            else 0
        end as monetary_score
        
    from customer_orders
),

final as (
    select
        *,
        
        -- RFM composite score
        (recency_score + frequency_score + monetary_score) / 3.0 as rfm_score,
        
        -- Customer value tier
        case
            when total_revenue >= {{ var('high_value_threshold') }} then 'high_value'
            when total_revenue >= {{ var('high_value_threshold') }} / 2 then 'medium_value'
            when total_revenue > 0 then 'low_value'
            else 'no_purchases'
        end as value_tier,
        
        -- Customer status
        case
            when days_since_last_order is null then 'never_purchased'
            when days_since_last_order <= {{ var('active_customer_days') }} then 'active'
            when days_since_last_order <= {{ var('active_customer_days') }} * 2 then 'at_risk'
            else 'churned'
        end as customer_status
        
    from clv_calculation
)

select * from final
