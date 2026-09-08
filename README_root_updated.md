# 🛠️ road-to-engineer

Data Analyst로 커리어를 시작해, 파이프라인 자동화·MLOps·Analytics Engineering으로
영역을 넓혀온 과정을 기록한 리포지토리입니다. "숫자를 분석하는 일"에서 "숫자가
믿을 수 있게 만들어지는 구조를 설계하는 일"로 관심이 옮겨가면서, 각 시점에 실제로
겪었던 문제와 그걸 풀어간 과정을 프로젝트 단위로 정리했습니다.

---

## 🗺️ 프로젝트 지도

### [01. MLOps](./01_MLOPS) — 서버리스 ML 파이프라인 구축 및 신뢰성 확보
사내 두 가지 ML 파이프라인(유저 클러스터링, 수요 예측)을 AWS Lambda로 자동화하고,
그 결과를 서빙한 뒤, 마지막으로 "제대로 돌았는지"를 사람이 매번 확인하지 않아도 되도록
자동 감지 체계까지 구축했습니다. 이후 분석·엔지니어링을 넘어 DBA·개인정보보호 영역까지
업무 범위를 넓혔습니다.

| 하위 프로젝트 | 핵심 키워드 |
|---|---|
| [01-1. User Clustering](./01_MLOPS/01-1_USER_CLUSTERING) | GMM, AIC 기반 K 자동탐색, CRM 연동 |
| [01-2. Laundry Forecast](./01_MLOPS/01-2_LAUNDRY_FORECAST) | Prophet, 외부 API 결합, 시계열 예측 |
| [01-3. GAS Data Pipeline](./01_MLOPS/01-3_GAS_DATA_PIPELINE) | AWS Lambda, Google Apps Script, 비용 절감 |
| [01-4. Pipeline Alert Monitoring](./01_MLOPS/01-4_PIPELINE_ALERT_MONITORING) | Slack Webhook, 사전 감지형 DQ 모니터링 |
| [01-5. Data Retention Compliance](./01_MLOPS/01-5_DATA_RETENTION_COMPLIANCE) | PyMySQL, 개인정보보호, ISMS |

### [02. DataOps & Text-to-SQL](./02_DataOps-Text-to-SQL-Project) — 사내 데이터 리터러시 향상
1인 분석가 체제의 병목을 해결하기 위해 "교육 → 프로세스 → AI 자동화" 3단계로
Self-Serve Analytics 환경을 구축했습니다. SQL 스터디부터 Snowflake Intelligence
기반 Text-to-SQL 에이전트까지 이어지는 과정을 담았습니다.

### [03. dbt Analytics Engineering](./03_DBT_ANALYTICS_ENGINEERING) — Semantic Layer 실전 구축
반복적으로 갱신해야 했던 시맨틱 모델(YAML) 문서를, 코드로 검증 가능한 dbt 파이프라인으로
전환했습니다. 실제 운영 데이터에서 정합성 이슈(순 결제액 계산 버그 등)를 발견하고
원인을 단계적으로 추적·해결한 과정을 담았습니다.

### [04. dbt 실전 적용](./04_DBT_LIVE_VALIDATION) — 병행 검증 및 레거시 자산 되살리기
03번에서 만든 dbt 모델을 sandbox에 가둬두지 않고, 실제 운영 지표와 병행 검증하며
정확도를 맞춰나간 과정입니다. 이 과정에서 사내에 이미 존재했지만 "정합성 확인 후
재배포 예정" 상태로 방치되어 있던 레거시 dbt 프로젝트를 발견해, 처음부터 새로 만드는
대신 그 자산에 자동 검증 계층을 추가해 되살렸습니다.

---

## 📖 프로젝트를 관통하는 문제의식

각 프로젝트는 독립적으로 보이지만, 사실 하나의 흐름으로 이어집니다.

1. **01 MLOps**: 처음엔 "모델을 서비스에 붙이는 것" 자체가 과제였습니다.
2. **01-4 Alert Monitoring**: 모델을 붙이고 나니, "에러 없이 실행됨"과 "결과가 정상임"이
   다르다는 걸 운영하며 깨달았고, 이를 감지하는 체계가 필요했습니다.
3. **01-5 Data Retention Compliance**: 여기서 더 나아가, ISMS 인증 심사 대응처럼
   분석·엔지니어링 범위를 넘어서는 DBA·개인정보보호 영역의 문제도 직접 맡아 해결했습니다.
4. **02 DataOps**: 혼자 감당하기 버거운 데이터 요청 병목을 풀려면, 조직 전체의 데이터
   리터러시를 끌어올려야 한다는 결론에 도달했습니다.
5. **03 dbt**: 그 과정에서 만든 시맨틱 모델(YAML)이 매번 손으로 갱신해야 하고, 실제와
   맞는지 검증할 수 없다는 한계에 부딪혔고, 이를 코드로 강제되는 구조로 바꾸는 방법을
   찾다가 dbt를 실습하게 됐습니다.
6. **04 dbt 실전 적용**: sandbox 실습에 그치지 않고 실제 운영 데이터와 병행 검증하며
   정확도를 좁혀갔고, 그 과정에서 방치되어 있던 사내 레거시 dbt 자산을 발견해 되살렸습니다.

각 프로젝트 README에는 "왜 이걸 시작했나"부터 "어떤 트러블슈팅을 거쳤나"까지
동일한 구조로 정리해두었습니다.

---

## 🛠️ Tech Stack

`AWS Lambda` `Docker` `Snowflake` `dbt` `Prophet` `scikit-learn` `Google Apps Script` `Slack API` `Python` `SQL` `PyMySQL`

---

## 📬 Contact

궁금하신 점이나 협업 제안은 언제든 편하게 연락해주세요.
