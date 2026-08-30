# 📑 사내 SQL 가이드라인 및 재사용 쿼리 템플릿 (SQL Style Guide & Templates)

본 문서는 사내 데이터 스터디(4개월)의 결과물로, PM, 디자이너, 마케터 등 비개발 직군 구성원들이 사내 스키마 구조를 이해하고 Self-Serve로 데이터를 활용할 수 있도록 돕기 위해 작성된 가이드북입니다.

---

## 🚨 사내 데이터를 다룰 때 꼭 지켜야 할 3가지 핵심 규칙

사내 데이터 웨어하우스(Snowflake)에서 데이터를 추출할 때, 아래의 3가지 규칙을 누락하면 환각(Hallucination) 데이터나 잘못된 매출 집계가 발생하므로 반드시 숙지해야 합니다.

### 규칙 1: 타임존(Timezone) 변환 금지 (KST 기준 적재)
- 사내 커머스 주문 및 수거 신청 관련 주요 타임스탬프 컬럼(`CREATED_DATETIME`, `CREATED_AT` 등)은 **이미 UTC+9(KST) 기준으로 변환되어 적재**되어 있습니다.
- 일반적인 데이터베이스 습관처럼 `CONVERT_TIMEZONE`이나 `DATEADD`를 통해 9시간을 더하는 연산을 수행하면 데이터가 왜곡되므로 원본 시간 컬럼을 그대로 사용해야 합니다.

### 규칙 2: 비정상 및 취소 데이터 필터링 아웃 필수
- 실적 및 주문 건수를 집계할 때, 단순 이탈이나 비정상 건을 걸러내야 정합성이 맞습니다.
- **수거 신청 원장(`WASH` 테이블계열):** `WHERE STATUS NOT IN (4, 17)` 조건을 무조건 추가하여 취소 및 미수거 건을 필터링해야 합니다.
- **스토어 주문 원장:** `WHERE order_status = 'COMPLETED'` 조건을 통해 정상 완료된 건만 집계해야 합니다.

### 규칙 3: 외부 연동 채널 데이터 제외
- 순수한 자사 프로동 프로모션 및 매출을 집계할 때는 외부 제휴 채널을 통한 유입을 발라내야 합니다.
- 쿼리 작성 시 `WHERE laundry_pgi IS NULL` 조건을 습관적으로 결합해 주어야 정확한 자사 실적이 도출됩니다.

---

## 💻 실무 활용용 마스킹 쿼리 템플릿 (E-Commerce & Subscription)

> **🔒 Security Notice:**
> 본 쿼리는 구성원들의 SQL 자생력을 높이기 위해 배포된 재사용 템플릿입니다. 사내 데이터 보안 및 거버넌스 규정에 따라 실제 스키마 명칭 및 세부 조건문은 **가상의 더미(Dummy) 이커머스 및 구독 요금제 서비스 형태**로 전면 추상화 및 가명 처리되었습니다. 
> 
> 하지만 **WITH절(CTE)을 활용한 다단계 집계 구조와 주석을 통한 가이드라인 작성 스타일**은 실제 배포된 프로덕션 포맷과 100% 동일합니다.

### 🎯 템플릿 주제: 특정 기간 고객 주문 및 멤버십 결제 내역 추출
- **사용 가이드:** 데이터 추출이 필요할 때 `{{start_date}}`와 `{{end_date}}` 부분에 분석하고자 하는 기간(예: `'2026-01-01'`)을 직접 입력 후 실행해 주세요.

```sql
-- =============================================================================
-- [TEMPLATE] 특정 기간 고객 주문 및 멤버십 결제 내역 추출
-- 💡 가이드: 데이터 추출이 필요할 때 {{start_date}}와 {{end_date}} 부분에 
--            분석하고자 하는 기간(YYYY-MM-DD)을 직접 입력 후 실행해 주세요.
-- =============================================================================

WITH store_purchase AS (
    -- [STEP 1] 스토어 상품 구매 내역 집계 (위의 규칙 2 반영: 취소 건 제외)
    SELECT
        user_id,
        order_id,
        SUM(pay_amount - cancel_amount) AS net_pay_amount
    FROM dummy_store_order_table
    WHERE order_status = 'COMPLETED'
      -- 👇 날짜 수정 포인트 1
      AND DATE(created_at) BETWEEN {{start_date}} AND {{end_date}}
    GROUP BY 1, 2
    HAVING net_pay_amount > 0
)

-- [STEP 2] 메인 주문 데이터와 스토어 결제 내역 결합
SELECT 
    DATE(o.created_at)                                      AS "주문 일자"
    , o.order_id                                            AS "주문 번호"
    , o.user_id                                             AS "고객 번호"
    , COALESCE(m.membership_price, '정기결제 차감')            AS "멤버십 이용 금액"
    , COALESCE(s.net_pay_amount, 0)                         AS "스토어 결제 금액"
    , IF(o.is_first_order = TRUE, '첫이용', '기존이용')          AS "첫 이용 여부"
FROM dummy_main_order_table o
    LEFT JOIN store_purchase s ON o.order_id = s.order_id
    LEFT JOIN dummy_membership_table m ON o.order_id = m.order_id
WHERE 1=1
    -- 🚨 규칙 2 적용: 비정상 건(취소, 환불 등)은 실적에서 제외하기 위한 필수 필터링입니다. 삭제하지 마세요.
    AND o.status NOT IN ('CANCELLED', 'REFUNDED')
    
    -- 🚨 규칙 3 적용: 외부 채널 연동 데이터 제외 필터
    AND o.external_channel_pgi IS NULL
    
    -- 👇 날짜 수정 포인트 2
    AND o.created_at BETWEEN {{start_date}} AND {{end_date}};
