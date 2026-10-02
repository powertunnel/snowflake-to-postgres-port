with source as (
    select * from {{ source('raw', 'support_tickets') }}
),

staged as (
    select
        ticket_id,
        customer_id,
        subject,
        category,
        description,
        status,
        priority,
        resolution,
        ticket_date,

        -- Derived fields
        case
            when status = 'Resolved' then true
            else false
        end as is_resolved,
        date_trunc('month', ticket_date) as ticket_month

    from source
)

select * from staged
