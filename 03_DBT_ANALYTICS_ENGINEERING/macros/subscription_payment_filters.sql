-- SQL_GUIDE.md에 문서로만 존재하던 결제 필터 규칙을,
-- 여러 모델에서 재사용 가능한 코드로 전환한 macro입니다.

{% macro net_payment_filter() %}
    payment_type = 0
{% endmacro %}

{% macro cancelled_payment_filter() %}
    payment_type in (1, 2)
{% endmacro %}
