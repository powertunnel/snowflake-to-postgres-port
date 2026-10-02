with product_metrics as (
    select * from {{ ref('int_product_metrics') }}
),

ranked_products as (
    select
        product_id,
        product_name,
        category,
        base_price,
        stock_quantity,

        order_count,
        units_sold,
        total_revenue,
        avg_selling_price,

        review_count,
        avg_rating,
        positive_reviews,
        negative_reviews,

        -- Performance rankings
        row_number() over (order by total_revenue desc) as revenue_rank,
        row_number() over (partition by category order by total_revenue desc) as category_revenue_rank,
        row_number() over (order by units_sold desc) as volume_rank,

        -- Performance tiers
        case
            when total_revenue = 0 then 'no_sales'
            when percent_rank() over (order by total_revenue) >= 0.9 then 'top_10_pct'
            when percent_rank() over (order by total_revenue) >= 0.75 then 'top_25_pct'
            when percent_rank() over (order by total_revenue) >= 0.5 then 'top_50_pct'
            else 'bottom_50_pct'
        end as revenue_tier,

        -- Rating tier
        case
            when avg_rating is null then 'no_reviews'
            when avg_rating >= 4.5 then 'excellent'
            when avg_rating >= 4.0 then 'good'
            when avg_rating >= 3.0 then 'average'
            else 'poor'
        end as rating_tier,

        -- Inventory status
        case
            when stock_quantity = 0 then 'out_of_stock'
            when stock_quantity < 10 then 'low_stock'
            when stock_quantity < 50 then 'normal_stock'
            else 'high_stock'
        end as inventory_status

    from product_metrics
)

select * from ranked_products
