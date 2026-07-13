# 🚀 Road to Engineer: Data & ML Pipeline Project

> 사내 유일의 데이터 담당자로서 데이터 추출, ML 모델링, MLOps 파이프라인 및 DW 인프라를 독자 구축하고 운영한 기록입니다.

## 🛠️ Tech Stacks
*### ⚡ Tech Stack
<img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white"/> <img src="https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white"/> <img src="https://img.shields.io/badge/TensorFlow-FF6F00?style=flat-square&logo=tensorflow&logoColor=white"/> <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white"/>

### ☁️ Data Tools
<img src="https://img.shields.io/badge/AWS-232F3E?style=flat-square&logo=amazon-aws&logoColor=white"/> <img src="https://img.shields.io/badge/AWS%20Lambda-FF9900?style=flat-square&logo=aws-lambda&logoColor=white"/> <img src="https://img.shields.io/badge/AWS%20RDS-527FFF?style=flat-square&logo=amazon-rds&logoColor=white"/> <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white"/> <img src="https://img.shields.io/badge/Snowflake-29B5E8?style=flat-square&logo=snowflake&logoColor=white"/> <img src="https://img.shields.io/badge/Airbyte-FF4500?style=flat-square&logo=airbyte&logoColor=white"/> <img src="https://img.shields.io/badge/Apache%20Airflow-017CEE?style=flat-square&logo=apache-airflow&logoColor=white"/>*

## 📊 Core Business Impacts
| 핵심 프로젝트 | 주요 수행 업무 | 정량적 성과 |
| :--- | :--- | :--- |
| **GMM 유저 클러스터링** | RFM 데이터 전처리 및 CRM(Braze) 연동 | **VIP 유저 이탈률 5% 감소** |
| **수요 예측 자동화** | AWS Lambda + Docker 기반 서버리스 배치 구축 | **무중단 예측 파이프라인 국산화** |
| **Text-to-SQL AI 에이전트** | Snowflake Cortex 명세 설계 및 전사 교육 | **단순 데이터 요청 75% 절감** |

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
