-- [SECURITY NOTICE] 실제 컬럼/필터 조건 일부는 사내 정책상 마스킹 처리했습니다.

select
    id                          as payment_id,
    new_subscription_order_id,
    old_subscription_order_id,
    subscription_order_id,
    user_id,
    wash_id,
    laundrygo_receipt_order_id,
    payment_type,               -- 0: 결제, 1/2: 취소
    payment_reason_type,
    order_name,
    order_price,
    paid_price,
    point_price,
    coupon_price,
    total_paid_price,
    succeeded,
    cancelled,
    approved_at,                -- 정산 비교 시 기준이 되는 결제 승인 시각
    created_at,
    created_date
from {{ source('laundrygo_live', 'subscription_payment') }}
where succeeded = 1
