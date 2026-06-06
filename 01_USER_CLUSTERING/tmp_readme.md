graph TD
    %% 데이터 수집 단계
    subgraph Storage [Data Warehouse]
        A[(Snowflake DB)] -->|User Behavior & RFM Data| B(Python Connector)
    end

    %% 데이터 전처리 및 수학적 가설 검증 단계
    subgraph Preprocessing [Feature Engineering & Scaling]
        B --> C{Skewed Distribution?}
        C -->|Yes: Right-Skewed 롱테일| D[np.log1p / np.sqrt 변환]
        D -->|다중 가우시안 정규성 충족| E[RobustScaler 적용]
    end

    %% 모델링 및 파인튜닝 단계
    subgraph ML_Engine [GMM Clustering Engine]
        E --> F[AIC/BIC Hyperparameter Tuning]
        F -->|최적 엘보우 포인트 K 자동 산출| G[Gaussian Mixture Model Fit]
        G -->|타원형 공분산 구조 적용| H[User Cluster Labeling]
    end

    %% 데이터 활용 및 서빙 단계
    subgraph Downstream [CRM & Activation]
        H --> I[MECE Waterfall 조건문 기반 자동 네이밍]
        I --> J[CSV Snapshot Export to AWS S3]
        J -->|Sync| K[Braze CRM Tool]
        K -->|Targeting Action| L[VIP 이탈률 5% 감소 달성]
    end

    %% 스타일 세팅
    style Storage fill:#f9f,stroke:#333,stroke-width:2px
    style Preprocessing fill:#bbf,stroke:#333,stroke-width:2px
    style ML_Engine fill:#ff9,stroke:#333,stroke-width:2px
    style Downstream fill:#bfb,stroke:#333,stroke-width:2px
