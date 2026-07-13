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
| **수요 예측 자동화 구현** | 물량 예측 파이프라인 구축 | **일평균 오차 240건 > 76건으로 68% 감소** |
| **사내 데이터 AI Agent 구현** | 데이터 추출/분석 자동화 시스템 도입 | **단순 데이터 요청 빈도 75% 감소** |


## 🏗️ System Architecture
```mermaid
graph LR
    A[Snowflake DW] -->|Cortex Analyst| B(AI Agent)
    A -->|Data Extraction| C[AWS Lambda]
    subgraph Container Environment
        C -->|Runtime Execution| D[Docker Engine]
    end
    D -->|Target Segments| E[S3 Storage]
    E -->|Trigger CRM| F[Braze / 현장 시스템]
