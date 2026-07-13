# 🚀 Road to Engineer: Data & ML Pipeline Project

> 사내 유일의 데이터 담당자로서 데이터 추출, ML 모델링, MLOps 파이프라인 및 DW 인프라를 독자 구축하고 운영한 기록입니다.

## 🛠️ Tech Stacks
*(여기에 Shields.io 배지 나열)*

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
