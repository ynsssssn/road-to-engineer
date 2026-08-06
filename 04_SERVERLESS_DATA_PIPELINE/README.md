# 📊 Snowflake - AWS Lambda - Google Sheets 서버리스 데이터 파이프라인 구축

Snowflake 데이터 웨어하우스의 비즈니스 지표 및 코호트 리텐션 데이터를 AWS Lambda 서버리스 파이프라인과 Google Apps Script를 통해 Google Sheets에 실시간/자동으로 적재하는 파이프라인 프로젝트입니다. 

외부 유료 커넥터(SaaS) 도입 비용을 100% 절감(연 1,400만 원 이상)하고, 매월/매주 수작업으로 진행되던 대용량 데이터 추출 프로세스를 자동화했습니다.

---

## 💡 비즈니스 배경 및 성과

### 1. 해결하고자 한 문제
* **비싼 외부 SaaS 커넥터 비용:** Snowflake 데이터를 구글 시트에 연동하기 위한 유료 커넥터(Coefficient 등) 도입 시, 엔터프라이즈 Tier 가입 필수 조건으로 인해 **연간 약 $10,000 USD (한화 약 1,380만 원)** 이상의 고정 비용이 발생하였습니다.
* **비효율적인 수작업 노가다:** 매주/매월 리텐션 분석을 위해 대용량 SQL을 직접 수행하고 결과를 엑셀/구글 시트로 복사-붙여넣기하는 번거로운 반복 작업이 이어졌습니다.

### 2. 서버리스 파이프라인 구축을 통한 해결
* **AWS Lambda + GAS 조합:** 서버리스 아키텍처를 도입하여 추가 인프라 구축 비용 없이 **AWS Free Tier 내에서 $0 비용**으로 완전 자동화를 달성했습니다.
* **유연한 타겟 파라미터 제어:** 하나의 Lambda 함수에서 `target` 파라미터 분기 처리를 통해 개별 지표 탭 updates 및 전체 탭 통합 updates를 유연하게 제어하도록 구현했습니다.

### 3. 프로젝트 성과
* **구독 비용 100% 절감:** 외부 SaaS 도입 비용 **연간 약 1,380만 원 절감 (ROI 100% 달성)**
* **업무 자동화 및 리텐션 지표 제공:** 구독/자유 유저별 클래식 및 갱신 리텐션 6종 지표가 구글 시트 대시보드에 자동 업데이트되어 타 팀과의 데이터 공유 편의성이 극대화되었습니다.

---

## 🏗️ 시스템 아키텍처

```mermaid
graph LR
    %% 1. 데이터 소스 및 보안
    A[(Snowflake DW)] -->|SQL 쿼리 데이터 추출| C(AWS Lambda)
    B[AWS Secrets Manager] -->|DB 계정 및 WebApp URL 전달| C
    
    %% 2. 서버리스 파이프라인
    subgraph Serverless Pipeline
        C -->|target 분기 처리 & JSON 변환| D(Google Apps Script)
    end
    
    %% 3. 서빙 및 리포팅
    D -->|doPost 수신기 매핑| E[Google Sheets]
    E -->|대시보드 자동화| F[비용 $0 달성 & 연 1,400만 원 절감]

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style Serverless Pipeline fill:#bbf,stroke:#333,stroke-width:2px
    style F fill:#bfb,stroke:#333,stroke-width:2px
