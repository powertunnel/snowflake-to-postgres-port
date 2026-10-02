with customer_support as (
    select * from {{ ref('int_customer_support') }}
),

customer_orders as (
    select * from {{ ref('int_customer_orders') }}
),

support_with_value as (
    select
        cs.customer_id,
        cs.customer_name,
        cs.customer_segment,
        cs.total_tickets,
        cs.resolved_tickets,
        cs.open_tickets,
        cs.high_priority_tickets,
        cs.support_tier,
        cs.first_ticket_date,
        cs.last_ticket_date,

        co.total_orders,
        co.lifetime_revenue,
        co.avg_order_value,

        -- Support efficiency metrics
        case
            when cs.total_tickets > 0
            then round(cs.resolved_tickets::numeric / cs.total_tickets * 100, 1)
            else null
        end as resolution_rate_pct,

        -- Support cost vs value
        case
            when co.lifetime_revenue > 0 and cs.total_tickets > 0
            then round(co.lifetime_revenue / cs.total_tickets, 2)
            else null
        end as revenue_per_ticket,

        -- Customer health score (0-100)
        case
            when co.total_orders is null or co.total_orders = 0 then 0
            else greatest(0, least(100,
                50  -- base score
                + (case when co.lifetime_revenue > 1000 then 20 else co.lifetime_revenue / 50 end)
                - (cs.total_tickets * 5)
                - (cs.open_tickets * 10)
                + (case when cs.total_tickets > 0 then (cs.resolved_tickets::numeric / cs.total_tickets) * 20 else 0 end)
            ))
        end as customer_health_score

    from customer_support cs
    left join customer_orders co on cs.customer_id = co.customer_id
),

final as (
    select
        *,
        case
            when customer_health_score >= 80 then 'healthy'
            when customer_health_score >= 50 then 'at_risk'
            else 'critical'
        end as health_status

    from support_with_value
)

select * from final
