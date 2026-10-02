with products as (
    select * from {{ ref('stg_products') }}
),

order_items as (
    select * from {{ ref('stg_order_items') }}
),

reviews as (
    select * from {{ ref('stg_product_reviews') }}
),

product_sales as (
    select
        product_id,
        count(distinct order_id) as order_count,
        sum(quantity) as units_sold,
        sum(line_total) as total_revenue,
        avg(unit_price) as avg_selling_price

    from order_items
    group by 1
),

product_reviews_agg as (
    select
        product_id,
        count(*) as review_count,
        avg(rating) as avg_rating,
        sum(case when sentiment_bucket = 'positive' then 1 else 0 end) as positive_reviews,
        sum(case when sentiment_bucket = 'negative' then 1 else 0 end) as negative_reviews

    from reviews
    group by 1
),

product_metrics as (
    select
        p.product_id,
        p.product_name,
        p.category,
        p.price as base_price,
        p.stock_quantity,

        coalesce(ps.order_count, 0) as order_count,
        coalesce(ps.units_sold, 0) as units_sold,
        coalesce(ps.total_revenue, 0) as total_revenue,
        ps.avg_selling_price,

        coalesce(pr.review_count, 0) as review_count,
        pr.avg_rating,
        coalesce(pr.positive_reviews, 0) as positive_reviews,
        coalesce(pr.negative_reviews, 0) as negative_reviews

    from products p
    left join product_sales ps on p.product_id = ps.product_id
    left join product_reviews_agg pr on p.product_id = pr.product_id
)

select * from product_metrics
