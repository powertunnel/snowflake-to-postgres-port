-- Staging layer for products
-- Minimal transformations on product catalog

with source as (
    select * from {{ source('raw', 'product_catalog') }}
),

staged as (
    select
        product_id,
        product_name,
        description,
        product_category as category,
        product_category as subcategory,
        'Unknown' as brand,
        price,
        price * 0.6 as cost,
        stock_quantity,
        100 as reorder_level,
        null as supplier_id,
        current_date as created_date,
        current_date as last_updated,
        
        -- Derived fields (using inline calculations to avoid column reference issues)
        price - (price * 0.6) as margin,
        (price - (price * 0.6)) / nullif(price, 0) as margin_percent,
        case 
            when stock_quantity <= 100 then 'low'
            when stock_quantity <= 200 then 'medium'
            else 'adequate'
        end as stock_status
        
    from source
)

select * from staged
