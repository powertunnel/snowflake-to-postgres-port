with customers as (
    select * from {{ ref('stg_customers') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

order_items as (
    select * from {{ ref('stg_order_items') }}
),

order_summary as (
    select
        o.order_id,
        o.customer_id,
        o.order_date,
        o.order_status,
        o.total_amount,
        count(oi.order_item_id) as item_count,
        sum(oi.quantity) as total_units

    from orders o
    left join order_items oi on o.order_id = oi.order_id
    group by 1, 2, 3, 4, 5
),

customer_orders as (
    select
        c.customer_id,
        c.customer_name,
        c.email,
        c.customer_segment,
        c.signup_date,
        c.days_since_signup,

        count(os.order_id) as total_orders,
        sum(os.total_amount) as lifetime_revenue,
        avg(os.total_amount) as avg_order_value,
        sum(os.total_units) as lifetime_units,
        min(os.order_date) as first_order_date,
        max(os.order_date) as last_order_date,
        datediff('day', max(os.order_date), current_date) as days_since_last_order

    from customers c
    left join order_summary os on c.customer_id = os.customer_id
    group by 1, 2, 3, 4, 5, 6
)

select * from customer_orders
