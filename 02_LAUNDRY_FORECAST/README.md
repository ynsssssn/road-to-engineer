# 🧺 세탁 물량 수요 예측 자동화 파이프라인 (Laundry Volume Forecast Pipeline)

날씨 변화(기온, 강수량)와 사내 물량 데이터를 결합하여 **향후 60일간의 세탁 수요를 예측하고 대시보드(Google Sheets)에 자동 연동하는 End-to-End 머신러닝 파이프라인**입니다. AWS Lambda와 Docker를 활용해 서버리스(Serverless) 환경에서 매일 새벽 자동으로 구동되도록 구축했습니다.

---

## 💡 Business Background & Problem Solving (비즈니스 배경 및 문제 해결의 고민)

기술(Tech)을 적용하기에 앞서, **'왜 이 프로젝트가 필요한가?'** 그리고 **'수많은 모델 중 왜 이 방법이 최선인가?'** 에 대한 치열한 고민을 바탕으로 파이프라인을 설계했습니다.

### 1. 프로젝트 추진 배경: "직관의 영역을 숫자의 영역으로"
- **인력 운용의 딜레마:** 매번 성수기가 도래할 때마다 팩토리(세탁 공장)의 인력 운용 최적화가 필수적이었습니다. 인력이 과잉되면 비용이 낭비되고, 부족하면 내부 오피스 인원들까지 현장에 투입되어 본업에 차질을 빚는 비효율이 반복되었습니다.
- **날씨 변수의 정량화:** 세탁업의 특성상 성수기와 비수기의 전환점은 '날씨'에 의해 결정됩니다. 실무자들이 매주 날씨를 확인하며 직관적으로 대비하던 것을, 기상청의 중단기 예보 데이터를 모델의 변수로 직접 포함하여 **직관적 예상을 정량적인 숫자(예측치)로 변환**하고자 했습니다.

### 2. 예측 모델 선정 과정: "한정된 데이터 환경에서의 최적점 찾기"
약 1,000건 수준의 일별 데이터 환경에서, 무조건 복잡한 모델을 쓰는 것보다 **Overfitting을 방지하고 거시적 추세와 계절성을 잘 잡아내는 벤치마크 모델**이 필요했습니다.

* **단순 전년 동기 대비(YoY)를 배제한 이유:** 23~25년의 성장세는 Linear하지 않았습니다. (23->24년은 10% 이상 성장했으나, 24->25년은 단가 인상 외 물량 성장이 정체되었고 25년 하반기부터 다시 반등). 따라서 팩토리 인력 배치 기준을 세우기 위해서는 단순 과거 평균보다는 **비수기 시점의 최근 3개월 이하 단기 흐름에 가중치를 줄 수 있는 유연한 모델**이 필요했습니다.
* **전통 통계 모델(ARIMA)을 배제한 이유:** 비즈니스의 성장이 꺾이거나 반등하는 추세 변화점(Changepoints) 대응에 취약하며, 명절 등 세탁 물량이 급변하는 공휴일 효과를 직관적으로 반영하기가 매우 까다롭습니다.
* **일반 머신러닝 (XGBoost, LightGBM)을 배제한 이유:** 쿠폰, 프로모션 등 마케팅 대조군 데이터가 부족한 상황에서 무리하게 피처를 쪼개어 학습시키면, 모델이 엉뚱한 가중치를 학습하여 오히려 미래 예측 성능이 떨어질 위험이 높았습니다.
* **딥러닝 (LSTM)을 배제한 이유:** 시퀀스 추정에 용이하나, 1,000개 수준의 스몰 데이터로는 모델의 파라미터를 제대로 학습하지 못하고 노이즈까지 통째로 외워버리는 극단적인 오버피팅이 발생합니다.
* **최종 선택 (Prophet):** 복잡한 외부 변수 추가를 최소화하고, **전체적인 Seasonality에 단기적 기상 변화만 외부 변수로 결합하여 추세를 그리는 데 가장 우수**한 Prophet을 최종 채택했습니다. (물론 향후 데이터가 누적되고 더 적합한 방법론이 검증된다면 유연하게 변경할 수 있도록 모듈화하였습니다.)

### 3. 프로젝트 성과 (Impact)
결과적으로 복잡한 변수들을 욱여넣는 대신 본질적인 트렌드와 단기 날씨 흐름에 집중한 결과 예측 정확도가 비약적으로 상승했습니다.
- **예측 오차(MAE) 약 70% 감소:** 2025년 상반기 기준 일 평균 240건이던 예측 오차를, 2025년 4분기~2026년 1분기 기준 **일 평균 76건**으로 대폭 축소하는 데 성공했습니다.
- 이를 통한 팩토리 인건비 최적화 및 재무적 개선 효과를 창출했습니다. (구체적 재무 임팩트는 대외비)

---

## 🏗️ Architecture & Workflow (기술 워크플로우)

1. **Data Extraction (데이터 수집)**
   - **Snowflake:** 사내 데이터 웨어하우스에서 요금제별(월정액/자유) 과거 세탁 주문량 집계
   - **기상청 API :** 주요 타겟 지역(서울, 인천, 수원, 동두천)의 과거 기온 및 강수량 데이터 수집
   - **AWS Secrets Manager:** DB 접속 정보 및 API Key 등 민감 정보 안전하게 로드
2. **Feature Engineering (파생 변수 생성)**
   - 단순 과거 날씨를 쓰는 것이 아니라, Prophet을 이용해 **미래 60일의 기온을 선제적으로 예측**
   - 전주 대비 기온이 1도/2도/3도 급변하는 시점을 포착하여 **다중 임계값 Trigger 변수** 생성
3. **Modeling (시계열 예측)**
   - **Facebook Prophet** 적용 (휴일 효과, 월/주간 계절성 반영)
   - 앞서 생성한 기온 급변 Trigger를 외부 회귀 변수(Regressor)로 추가하여 최종 물량 예측
4. **Deploy & Automation (배포 및 자동화)**
   - 코드를 Docker Container 이미지로 빌드하여 AWS ECR에 푸시
   - **AWS Lambda + EventBridge**를 연동하여 매일 지정된 시간에 자동 실행
5. **Visualization (시각화 연동)**
   - 예측 결과를 Google Apps Script(GAS) Webhook을 통해 Google Sheets `raw_data` 시트에 전송
   - 전사 공유 대시보드 시트에서 `XLOOKUP`을 통해 최신 예측값을 안전하게 매핑 및 누적

## 🛠️ Tech Stack
- **Language:** Python 3.8
- **Machine Learning:** Prophet (`pystan` backend), Pandas, Numpy
- **Data Warehouse:** Snowflake
- **Cloud Infrastructure:** AWS Lambda, AWS ECR, AWS Secrets Manager, EventBridge
- **Containerization:** Docker
- **Integration:** REST API (KMA), Google Apps Script (Webhook)

---

## 🔥 Engineering Troubleshooting (엔지니어링 트러블슈팅)

이 프로젝트를 진행하며 클라우드 환경(AWS Lambda)에서 무거운 머신러닝 라이브러리(Prophet)를 서빙할 때 발생하는 다양한 인프라적 한계점들을 경험하고 해결했습니다.

### 1. AWS Lambda Init Timeout (10초 부팅 제한) 에러
- **Issue:** Lambda는 컨테이너가 처음 부팅될 때(Init Phase) 10초 내에 준비를 마쳐야 함. 하지만 `prophet`, `snowflake-connector`, `boto3`(Secrets Manager 호출) 등 무거운 라이브러리를 전역(Global)에서 한 번에 로드하다 보니 10초를 초과하여 프로세스가 강제 종료되는 문제 발생.
- **Resolution (Lazy Loading 적용):** 무거운 라이브러리의 `import`문과 Secrets Manager 호출 로직을 전역 공간이 아닌 메인 함수(`lambda_handler`) 내부와 각 개별 함수 내부로 이동. Lambda의 Invoke 단계에서 로드되도록 지연시켜(Lazy Loading) 부팅 타임아웃 문제를 완벽히 회피함.

### 2. Prophet과 Lambda의 Read-only 환경 충돌 (`stan_backend` 에러)
- **Issue:** 최신 버전의 Prophet(1.1.x 이상)은 `cmdstanpy` 백엔드를 사용하며, 실행 과정에서 임시 컴파일 파일 생성 및 `makefile` 검증 등 디렉토리 쓰기(Write) 작업을 요구함. 하지만 AWS Lambda의 코드 경로(`/var/task`)는 **철저한 읽기 전용(Read-only)** 정책을 따르기 때문에 엔진이 구동되지 않고 뻗어버리는 크리티컬 이슈 발생.
- **Resolution (환경 최적화 및 엔진 다운그레이드):**
  - 처음에는 Lambda에서 유일하게 쓰기가 허용된 `/tmp` 디렉토리로 환경 변수(`CMDSTAN_WRITE_PATH`)를 우회하고, Docker 빌드 시 `chmod -R 777`로 권한을 부여하는 방식을 시도했으나 환경 의존성 문제가 지속됨.
  - 최종적으로 AWS Lambda 환경에서 가장 안정성이 검증된 **Python 3.8 베이스 이미지 + Prophet 1.1.1 + `pystan 2.19.1.1`** 조합으로 스택을 전면 개편. Docker 빌드 단계에서 `gcc-c++`를 통해 미리 컴파일을 완료하여, Lambda 런타임 시에는 디렉토리 쓰기 없이 메모리 위에서만 가볍게 동작하도록 아키텍처를 최적화함.

### 3. Mac(M1/M2) Docker Build와 AWS Lambda Architecture 불일치
- **Issue:** Apple Silicon(ARM64) 환경에서 기본적으로 빌드된 Docker 이미지를 AWS ECR에 올렸을 때, Lambda(x86_64 기반)에서 `Runtime.InvalidEntrypoint` 에러를 뱉으며 실행 거부.
- **Resolution:** Docker 빌드 시 `--platform linux/amd64` 옵션을 명시적으로 추가하여 크로스 컴파일(Cross-compile)을 진행하고, Lambda 구성 환경도 x86_64로 통일하여 아키텍처 충돌 해결.

### 4. 대시보드 데이터 덮어쓰기(Overwrite) vs 누적(Append) 문제
- **Issue:** 배치가 돌 때마다 60일치 예측값이 통째로 갱신되므로, 전사가 보는 공유 시트의 과거 데이터가 휘발되는 현상 발생. 단순 Append를 하면 데이터가 중복해서 아래로 쌓이는 문제 존재.
- **Resolution:** 데이터베이스와 뷰(View)의 개념을 분리.
  - Lambda는 빈 시트(`raw_data`)에 매일 최신 60일치 데이터만 덮어쓰도록 처리.
  - 전사가 보는 대시보드 시트에는 날짜를 Key값으로 삼아 `=XLOOKUP()` 함수를 걸어두어, 최신 배치 결과만 동적으로 매핑.
  - 매주 월요일 아침, Google Apps Script의 시간 기반 트리거를 이용해 "지난주 수식을 실제 데이터로 고정"하는 매크로를 돌려 과거 데이터를 안전하게 보존함.

---

## 🔒 Security
- 본 레포지토리에 업로드된 파이썬 스크립트(.py)는 사내 보안 규정에 따라 DB 계정, URL, 시크릿 키 등이 **마스킹 처리된 버전**입니다.
- 실제 운영 환경에서는 모든 민감 정보가 소스 코드 내에 하드코딩되지 않고 **AWS Secrets Manager**를 통해 암호화되어 관리됩니다.
