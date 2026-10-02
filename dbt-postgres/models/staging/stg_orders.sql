-- Staging layer for orders
-- Joins order header with items, basic transformations

with orders as (
    select * from {{ source('raw', 'orders') }}
),

order_items as (
    select * from {{ source('raw', 'order_items') }}
),

aggregated as (
    select
        o.order_id,
        o.customer_id,
        o.order_date,
        o.order_status,
        o.total_amount,
        o.discount_percent,
        o.shipping_cost,
        
        -- Order item aggregations
        count(oi.order_item_id) as item_count,
        sum(oi.quantity) as total_quantity,
        sum(oi.line_total) as calculated_total,
        
        -- Derived fields
        date_trunc('day', o.order_date) as order_date_only,
        date_trunc('month', o.order_date) as order_month,
        date_trunc('year', o.order_date) as order_year,
        dayname(o.order_date) as order_day_of_week,
        hour(o.order_date) as order_hour
        
    from orders o
    left join order_items oi on o.order_id = oi.order_id
    group by 
        o.order_id,
        o.customer_id,
        o.order_date,
        o.order_status,
        o.total_amount,
        o.discount_percent,
        o.shipping_cost
)

select * from aggregated
