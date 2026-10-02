{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- 
        Override default schema generation to use exact schema names
        
        Default dbt behavior:
        - dev: <target_schema>_<custom_schema>  (e.g., dbt_staging_dbt_staging)
        - prod: <custom_schema>                  (e.g., dbt_staging)
        
        Our behavior:
        - Always use <custom_schema> if specified
        - Fall back to <target_schema> if no custom schema
    -#}
    
    {%- set default_schema = target.schema -%}
    
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
