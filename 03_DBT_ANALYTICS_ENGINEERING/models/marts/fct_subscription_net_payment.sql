-- [비즈니스 룰] 순 결제액 = PAYMENT_TYPE=0(결제) 금액에서 PAYMENT_TYPE IN(1,2)(취소) 금액 차감
-- 취소는 원 결제와 날짜가 다를 수 있으므로(parent_payment_id 존재),
-- 날짜가 아니라 "원 결제 건" 단위로 묶어서 순액을 계산합니다.
-- 주의: parent_payment_id는 원 결제 건에서 null이 아니라 0으로 들어있음 (nullif로 처리)
-- 2026 지표 기준에 맞춰 충전/마케팅 포인트 구분 없이 point_price를 전체 포함하여 계산
--   (유상 포인트만 필터링 시도 → 실제 지표와 오차 확대되는 것을 확인 후 되돌림, 상세는 README 참고)

with payments as (
    select
        coalesce(nullif(parent_payment_id, 0), payment_id) as original_payment_id,
        user_id,
        min(created_date) as created_date,
        min(approved_at) as approved_at,
        sum(case when {{ net_payment_filter() }} then paid_price else 0 end) as gross_paid_price,
        sum(case when {{ net_payment_filter() }} then point_price else 0 end) as gross_point_price,
        sum(case when {{ cancelled_payment_filter() }} then paid_price else 0 end) as cancelled_price,
        sum(case when {{ cancelled_payment_filter() }} then point_price else 0 end) as cancelled_point_price
    from {{ ref('stg_subscription_payment') }}
    group by coalesce(nullif(parent_payment_id, 0), payment_id), user_id
)

select
    original_payment_id,
    user_id,
    created_date,
    approved_at,
    gross_paid_price,
    gross_point_price,
    cancelled_price,
    cancelled_point_price,
    (gross_paid_price + gross_point_price) - (cancelled_price + cancelled_point_price) as net_paid_price
from payments
