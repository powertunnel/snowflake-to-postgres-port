-- Product Recommendations
-- Generates product recommendations based on purchase patterns

with affinity as (
    select * from {{ ref('product_affinity') }}
    where affinity_strength in ('very_strong', 'strong', 'moderate')
),

-- Bi-directional recommendations
all_recommendations as (
    -- A -> B recommendations
    select
        product_a_id as source_product_id,
        product_a_name as source_product_name,
        product_a_category as source_category,
        product_b_id as recommended_product_id,
        product_b_name as recommended_product_name,
        product_b_category as recommended_category,
        confidence_a_to_b as confidence,
        lift,
        times_bought_together,
        affinity_strength,
        recommendation_priority
    from affinity
    
    union all
    
    -- B -> A recommendations
    select
        product_b_id as source_product_id,
        product_b_name as source_product_name,
        product_b_category as source_category,
        product_a_id as recommended_product_id,
        product_a_name as recommended_product_name,
        product_a_category as recommended_category,
        confidence_b_to_a as confidence,
        lift,
        times_bought_together,
        affinity_strength,
        recommendation_priority
    from affinity
),

-- Rank recommendations per product
ranked_recommendations as (
    select
        *,
        row_number() over (
            partition by source_product_id 
            order by lift desc, confidence desc, times_bought_together desc
        ) as recommendation_rank
    from all_recommendations
),

-- Recommendation rationale
final as (
    select
        *,
        
        -- Recommendation message
        case
            when affinity_strength = 'very_strong' 
                then 'Customers who bought ' || source_product_name || ' almost always buy ' || recommended_product_name
            when affinity_strength = 'strong' 
                then 'Customers who bought ' || source_product_name || ' frequently buy ' || recommended_product_name
            when affinity_strength = 'moderate' 
                then 'Customers who bought ' || source_product_name || ' often buy ' || recommended_product_name
            else 'Consider ' || recommended_product_name || ' with ' || source_product_name
        end as recommendation_message,
        
        -- Cross-category indicator
        case 
            when source_category != recommended_category then true 
            else false 
        end as is_cross_category,
        
        -- Confidence level for UI
        case
            when confidence >= 0.5 then 'high'
            when confidence >= 0.3 then 'medium'
            else 'low'
        end as confidence_level
        
    from ranked_recommendations
    where recommendation_rank <= 10  -- Top 10 recommendations per product
)

select * from final
order by source_product_id, recommendation_rank
