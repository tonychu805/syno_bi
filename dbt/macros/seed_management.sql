{% macro cleanup_seed_relations(schema, relations) %}
  {#-
    Drop legacy seed relations before loading fresh files.
    Keeps Postgres system catalog free of lingering type names
    that collide with numeric identifiers.
  -#}
  {% set relation_list = relations or [] %}

  {% if relation_list | length == 0 %}
    {{ log("No seed relations requested for cleanup.", info=True) }}
  {% else %}
    {% set database = target.database %}

    {% for identifier in relation_list %}
      {% set relation = adapter.get_relation(database=database, schema=schema, identifier=identifier) %}
      {% if relation %}
        {{ log("Dropping existing seed relation " ~ relation, info=True) }}
        {{ adapter.drop_relation(relation) }}
      {% else %}
        {{ log("Seed relation " ~ schema ~ "." ~ identifier ~ " not found; skipping.", info=True) }}
      {% endif %}
    {% endfor %}
  {% endif %}
{% endmacro %}
