with customers as (
    select * from {{ ref('stg_customers') }}
),

tickets as (
    select * from {{ ref('stg_support_tickets') }}
),

ticket_summary as (
    select
        customer_id,
        count(*) as total_tickets,
        sum(case when is_resolved then 1 else 0 end) as resolved_tickets,
        sum(case when not is_resolved then 1 else 0 end) as open_tickets,
        sum(case when priority = 'High' then 1 else 0 end) as high_priority_tickets,
        min(ticket_date) as first_ticket_date,
        max(ticket_date) as last_ticket_date

    from tickets
    group by 1
),

customer_support as (
    select
        c.customer_id,
        c.customer_name,
        c.customer_segment,

        coalesce(ts.total_tickets, 0) as total_tickets,
        coalesce(ts.resolved_tickets, 0) as resolved_tickets,
        coalesce(ts.open_tickets, 0) as open_tickets,
        coalesce(ts.high_priority_tickets, 0) as high_priority_tickets,
        ts.first_ticket_date,
        ts.last_ticket_date,

        case
            when ts.total_tickets is null then 'no_tickets'
            when ts.total_tickets > 5 then 'high_contact'
            when ts.total_tickets > 2 then 'medium_contact'
            else 'low_contact'
        end as support_tier

    from customers c
    left join ticket_summary ts on c.customer_id = ts.customer_id
)

select * from customer_support
