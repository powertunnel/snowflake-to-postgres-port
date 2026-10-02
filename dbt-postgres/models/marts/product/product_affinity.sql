-- Product Affinity Analysis
-- Identifies which products are frequently purchased together

with order_items as (
    select
        order_id,
        product_id,
        product_name,
        product_category
    from {{ ref('stg_order_items') }}
),

-- Self-join to find product pairs in same order
product_pairs as (
    select
        oi1.product_id as product_a_id,
        oi1.product_name as product_a_name,
        oi1.product_category as product_a_category,
        oi2.product_id as product_b_id,
        oi2.product_name as product_b_name,
        oi2.product_category as product_b_category,
        oi1.order_id
    from order_items oi1
    join order_items oi2 
        on oi1.order_id = oi2.order_id
        and oi1.product_name < oi2.product_name  -- Avoid duplicates and self-pairs
),

-- Aggregate pair statistics
pair_statistics as (
    select
        product_a_id,
        product_a_name,
        product_a_category,
        product_b_id,
        product_b_name,
        product_b_category,
        count(distinct order_id) as times_bought_together,
        count(distinct order_id) * 1.0 as pair_frequency
    from product_pairs
    group by 
        product_a_id,
        product_a_name,
        product_a_category,
        product_b_id,
        product_b_name,
        product_b_category
),

-- Get individual product purchase counts
product_counts as (
    select
        product_name,
        count(distinct order_id) as total_orders
    from order_items
    group by product_name
),

-- Calculate affinity scores
affinity_scores as (
    select
        ps.*,
        pca.total_orders as product_a_total_orders,
        pcb.total_orders as product_b_total_orders,
        
        -- Confidence: P(B|A) = orders with both / orders with A
        ps.pair_frequency / nullif(pca.total_orders, 0) as confidence_a_to_b,
        
        -- Confidence: P(A|B) = orders with both / orders with B  
        ps.pair_frequency / nullif(pcb.total_orders, 0) as confidence_b_to_a,
        
        -- Lift: How much more likely to buy together than independently
        -- Lift = P(A,B) / (P(A) * P(B)) = (pair_freq/total) / ((A_orders/total) * (B_orders/total))
        (ps.pair_frequency * (select count(distinct order_id) from order_items)) / 
            (pca.total_orders * pcb.total_orders * 1.0) as lift,
        
        -- Support: % of all orders that contain this pair
        ps.pair_frequency / (select count(distinct order_id) from order_items) as support
        
    from pair_statistics ps
    join product_counts pca on ps.product_a_name = pca.product_name
    join product_counts pcb on ps.product_b_name = pcb.product_name
),

final as (
    select
        *,
        
        -- Affinity strength classification
        case
            when lift >= 3.0 and confidence_a_to_b >= 0.5 then 'very_strong'
            when lift >= 2.0 and confidence_a_to_b >= 0.3 then 'strong'
            when lift >= 1.5 and confidence_a_to_b >= 0.2 then 'moderate'
            when lift >= 1.2 then 'weak'
            else 'very_weak'
        end as affinity_strength,
        
        -- Recommendation priority
        case
            when lift >= 2.0 and times_bought_together >= 100 then 1
            when lift >= 1.5 and times_bought_together >= 50 then 2
            when lift >= 1.2 and times_bought_together >= 25 then 3
            else 4
        end as recommendation_priority
        
    from affinity_scores
    where lift >= 1.0  -- Only keep pairs bought together more than random chance
)

select * from final
order by lift desc, times_bought_together desc
