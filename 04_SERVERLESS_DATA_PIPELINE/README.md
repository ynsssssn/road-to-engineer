# 📊 Snowflake - AWS Lambda - GAS 데이터 파이프라인 자동화 및 비용 절감

> **"SaaS 연간 1,400만 원 구독 비용을 100% 절감하고, 리텐션/코호트 지표의 실시간 연동 파이프라인을 구축한 서버리스 프로젝트입니다."**

Snowflake DW의 비즈니스 지표 및 코호트 리텐션(Retention) 데이터를 AWS Lambda 서버리스 파이프라인과 Google Apps Script(GAS)를 연동하여 Google Sheets에 자동 적재하는 파이프라인 구축 프로젝트입니다.

---

## 💡 비즈니스 배경 및 핵심 성과

### 1. 해결하고자 한 문제
* **고비용 유료 커넥터(SaaS) 부담:** Snowflake 데이터를 Google Sheets로 실시간 연동하기 위한 유료 SaaS(Coefficient 등) 도입 시, 엔터프라이즈 요금제 필수 적용으로 인해 **연간 약 $10,000 USD (한화 약 1,400만 원)** 이상의 고정 인프라 비용이 요구되었습니다.
* **수작업 리포팅의 비효율성:** 주/월 단위 리텐션 분석을 위해 담당자가 대용량 SQL 쿼리를 직접 수행하고 수동으로 스프레드시트에 이동·가공하는 반복적인 공수가 발생했습니다.

### 2. 서버리스 아키텍처 도입을 통한 해결
* **AWS Lambda + GAS 서버리스 구성:** 추가 인프라 유지비 없는 완전 서버리스(Serverless) 아키텍처를 직접 설계하여 **AWS Free Tier 범위 내 $0 비용**으로 완전 자동화를 달성했습니다.
* **동적 Target 파라미터 분기:** 단일 Lambda 함수 내에서 `target` 파라미터 분기 처리를 구현하여, 특정 리텐션 지표 탭 개별 업데이트 및 전체 지표 일괄 업데이트를 유연하게 제어하도록 설계했습니다.

### 3. 프로젝트 주요 성과 (ROI)
* **💰 연 1,400만 원 비용 절감 (ROI 100% 증명):** 외부 유료 SaaS 도입 대비 인프라 구축 비용을 100% 절감하여 연간 1,400만 원의 고정비 다이어트를 성취했습니다.
* **⚡ 리텐션 지표 자동 업데이트 파이프라인 완성:** 구독/자유 유저별 클래식 및 갱신 리텐션 지표 6종이 매주 Google Sheets 대시보드로 자동 전송되어, 타 팀과의 데이터 공유 및 현황 파악 생산성이 크게 향상되었습니다.

---

## 🏗️ 시스템 아키텍처 (System Architecture)

```mermaid
graph LR
    %% 1. 데이터 소스 및 보안
    A[(Snowflake DW)] -->|SQL 쿼리 실행 & 데이터 추출| C(AWS Lambda)
    B[AWS Secrets Manager] -->|DB 계정 & WebApp URL 보안 전달| C
    
    %% 2. 서버리스 파이프라인
    subgraph Serverless Pipeline
        C -->|target 분기 처리 & JSON 직렬화| D(Google Apps Script)
    end
    
    %% 3. 서빙 및 활용
    D -->|doPost 수신기 매핑 & 시트 업데이트| E[Google Sheets]
    E -->|대시보드 리포팅 자동화| F[연 1,400만 원 절감 & ROI 증명]

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style Serverless Pipeline fill:#bbf,stroke:#333,stroke-width:2px
    style F fill:#bfb,stroke:#333,stroke-width:2px