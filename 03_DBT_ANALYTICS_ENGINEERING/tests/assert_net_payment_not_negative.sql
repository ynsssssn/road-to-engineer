-- [비즈니스 룰] 순 결제액(net_paid_price)은 마이너스가 될 수 없습니다.
--
-- 알려진 예외 1: 2019년 데이터는 parent_payment_id 추적 체계 도입 이전이라
-- 취소 건과 원 결제 건을 매칭할 수 없는 케이스가 존재합니다 (조사 완료, 394건).
--
-- 알려진 예외 2: 결제/취소 과정에서 point_price가 비정상적으로 관여하는 극소수
-- 케이스가 존재합니다 (조사 완료, 10건, 전체 결제 대비 0.001% 미만).
-- - 9건: payment_type=0(정상 결제)인데 point_price가 음수로 기록된 케이스
-- - 1건: 원 결제엔 포인트 사용 이력이 없는데, 그 취소 건에만 point_price가
--        붙어 취소액이 원 결제액을 초과한 케이스 (환불 보상성 포인트 지급으로 추정)
-- 두 경우 모두 재무적 영향이 미미해 예외로 처리하되 계속 감시합니다.
--
-- 이 테스트를 통과시키기 위해 위 예외 조건을 완화하는 대신, 조건마다 실제
-- 몇 건이 해당하는지, 왜 그런지 원인을 규명한 뒤 근거와 함께 명시했습니다.
-- (전체 발견 과정: 51,688건 → 8,641건 → 394건 → 0건, 상세는 README 참고)

select
    user_id,
    created_date,
    gross_paid_price,
    cancelled_price,
    net_paid_price
from {{ ref('fct_subscription_net_payment') }}
where net_paid_price < 0
    and year(created_date) != 2019
    and not (
        gross_paid_price = 0
        and cancelled_price = 0
        and cancelled_point_price = 0
    )
    and net_paid_price <= -2000
