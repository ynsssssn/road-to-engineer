# 🚀 Data & ML Pipeline Project

> 사내 유일의 데이터 담당자로서 데이터 추출, ML 모델링, MLOps 파이프라인 및 DW 인프라를 독자 구축하고 운영한 기록입니다.

### 🛠️ Tech Stacks

<img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white"/> <img src="https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white"/> <img src="https://img.shields.io/badge/TensorFlow-FF6F00?style=flat-square&logo=tensorflow&logoColor=white"/> <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white"/>

### ☁️ Data Tools
<img src="https://img.shields.io/badge/AWS-232F3E?style=flat-square&logo=amazon-aws&logoColor=white"/> <img src="https://img.shields.io/badge/AWS%20Lambda-FF9900?style=flat-square&logo=aws-lambda&logoColor=white"/> <img src="https://img.shields.io/badge/AWS%20RDS-527FFF?style=flat-square&logo=amazon-rds&logoColor=white"/> <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white"/> <img src="https://img.shields.io/badge/Snowflake-29B5E8?style=flat-square&logo=snowflake&logoColor=white"/> <img src="https://img.shields.io/badge/Airbyte-FF4500?style=flat-square&logo=airbyte&logoColor=white"/> <img src="https://img.shields.io/badge/Apache%20Airflow-017CEE?style=flat-square&logo=apache-airflow&logoColor=white"/>

## 📊 Core Business Impacts
| 프로젝트 | 주요 수행 업무 | 정량적 성과 |
| :--- | :--- | :--- |
| **유저 클러스터링 구현** | 유저 그룹화 마케팅 연동 및 팩토리 공유  | **VIP 유저 이탈률 5% 감소** |
| **수요 예측 자동화 구현** | 물량 예측 파이프라인 구축 | **일평균 오차 68% 감소** |
| **사내 데이터 AI Agent 구현** | 데이터 추출/분석 자동화 시스템 도입 | **단순 데이터 요청 빈도 75% 감소** |


## 🏗️ System Architecture
```mermaid

graph LR
    %% 데이터 소스 및 서빙 아키텍처
    A[Snowflake DW] -->|1. Cortex Analyst| B(AI Agent)
    B -->|2. 유저의 AI기반 분석 활용| B_User[사내 비개발 직군]

    %% 분석 및 배치 파이프라인
    A -->|3. 예측 대상 및 물량 추출| C[AWS Lambda]
    
    %% subgraph 오류 수정 (따옴표 활용 및 컴팩트한 ID)
    subgraph Container_Env ["서버리스 실행 환경"]
        C -->|4. ML 모델 및 배치 실행| D[Docker Engine]
    end
    
    D -->|5. 세그먼트/물량 결과 적재| E[S3 Storage]
    
    %% 최종 비즈니스 활용
    E -->|6. 예측 서빙/자동 트리거| F[Braze 및 사내 시스템]
    F -->|7. 맞춤형 마케팅/출고 공정 활용| F_Biz[비즈니스 현장]

    %% 스타일링 (시각적 구분)
    style B_User fill:#f9f,stroke:#333,stroke-width:2px
    style F_Biz fill:#bbf,stroke:#333,stroke-width:2px
