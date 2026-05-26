# 📊 데이터 Ops 및 사내 데이터 리터러시 향상 프로젝트 (Self-Serve Analytics & DataOps)

사내 유일한 데이터 분석가로서 발생하는 쿼리 추출 병목 현상을 해결하고, 전사 구성원의 데이터 리터러시를 향상시키기 위한 DataOps 프로젝트입니다. 
**"아날로그(교육) ➔ 프로세스(가이드) ➔ AI 자동화(Text-to-SQL)"** 3단계 빌드업을 통해 구성원 스스로 데이터를 분석하는 Self-Serve Analytics 환경을 구축했습니다.

---

## 🗺️ Project Architecture (데이터 분석 파이프라인 진화도)

이 프로젝트를 통해 과거 분석가에게 집중되던 병목 구조(As-Is)를, AI 에이전트와 시맨틱 모델 기반의 자생적 구조(To-Be)로 혁신했습니다.

```mermaid
graph TD
    subgraph "Phase 3: Text-to-SQL AI 자동화 구축 (TO-BE)"
        C[현업 부서] -->|자연어 질문 입력| D{Snowflake Intelligence}
        D -->|SQL 자동 생성 및 데이터 추출| C
        E[데이터 분석가] -->|YAML 데이터 명세서 작성<br/>도메인 룰 및 필터 주입| D
        D -->|쿼리 실행| F[(사내 데이터 웨어하우스)]
    end

    subgraph "Phase 1 & 2: 아날로그 교육 및 프로세스화 (AS-IS)"
        A[현업 부서] -->|단순 쿼리 요청| B(데이터 분석가 병목 발생)
        B -.->|SQL 스터디 및 템플릿 제공| A
    end

