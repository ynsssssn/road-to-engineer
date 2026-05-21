import os
import json
import time
import requests
import traceback
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import snowflake.connector as snow 


import boto3
from botocore.exceptions import ClientError

# =============================================================================
# [1] Configuration & Constants (환경 설정 및 상수)
# =============================================================================
# AWS Lambda 환경에서 Warm Start 시 인프라 호출 최소화를 위해 Secret 캐싱 처리
secrets_cache = None

# [MASKING] 실제 권역명은 Region_A~D로 추상화하되, 
# KMA(기상청) 공공 API의 정상 호출 및 실행 가능성 확보를 위해 표준 관측소 ID는 유지
TARGET_STATIONS = {
    '108': 'Region_A', 
    '112': 'Region_B', 
    '119': 'Region_C', 
    '98':  'Region_D'  
}
PREDICT_DAYS = 60

# [MASKING] 사내 프로모션 및 특수 휴무일 패턴이 노출되지 않도록 표준 공휴일 데이터 예시로 마스킹
HOLIDAYS_DF = pd.DataFrame({
    'holiday': 'event',
    'ds': pd.to_datetime([
        '2023-01-01', '2023-05-05', '2023-12-25',
        '2024-01-01', '2024-05-05', '2024-12-25',
        '2025-01-01', '2025-05-05', '2025-12-25',
        '2026-01-01', '2026-05-05', '2026-12-25'
    ]),
    'lower_window': -1,
    'upper_window': 1
})

def get_secret():
    """AWS Secrets Manager에서 자격 증명 정보를 안전하게 로드합니다."""
    # [MASKING] 사내 시크릿 매니저 키 명칭 보안 마스킹
    secret_name = "***_Connection" 
    region_name = "ap-northeast-2"
    
    try:
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"[ERROR] AWS Secrets Manager 로드 실패: {str(e)}")
        raise e

# =============================================================================
# [2] Data Extraction: 외부 API 날씨 데이터 수집 (기상청 ASOS)
# =============================================================================
def fetch_weather_data(api_key):
    """공공데이터포털 기상청 ASOS 일자료 API를 호출하여 과거 및 현재 기상 데이터를 수집합니다."""
    print("[INFO] 기상청 API 일자료 수집 시작")
    url = 'https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    
    # 모델 학습 효율화를 위한 거시적 시계열 기간 설정
    year_ranges = [
        ('20230101', '20231231'), ('20240101', '20241231'),
        ('20250101', '20251231'), ('20260101', yesterday_str)
    ]
    all_weather_data = []

    for stn_id, stn_name in TARGET_STATIONS.items():
        for start_date, end_date in year_ranges:
            params = {
                'ServiceKey': api_key, 'pageNo': '1', 'numOfRows': '999',
                'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'DAY',
                'startDt': start_date, 'endDt': end_date, 'stnIds': stn_id
            }
            try:
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if 'response' in data and 'header' in data['response'] and data['response']['header']['resultCode'] == '00':
                        items = data['response']['body']['items']['item']
                        for item in items:
                            all_weather_data.append({
                                '날짜': item.get('tm', ''), '지역명': stn_name,
                                '평균기온': item.get('avgTa', ''),
                                '일강수량(총량)': item.get('sumRn', '') or '0.0',
                                '일최대강수량(1hr)': item.get('max1hrRn', '') or '0.0'
                            })
                # API DDoS 방지 및 안정적인 커넥션을 위한 의도적 지연 시간 설정
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARNING] 기상청 API 호출 중 일시적 에러 건너뜀 (지역:{stn_name}): {str(e)}")
                pass

    df_weather = pd.DataFrame(all_weather_data)
    df_weather['날짜'] = pd.to_datetime(df_weather['날짜'], format='%Y-%m-%d')
    for col in ['평균기온', '일강수량(총량)', '일최대강수량(1hr)']:
        df_weather[col] = pd.to_numeric(df_weather[col], errors='coerce')

    return df_weather.sort_values(['날짜', '지역명']).reset_index(drop=True)

# =============================================================================
# [3] Data Extraction: 내부 데이터 웨어하우스(Snowflake) 물량 집계
# =============================================================================
def fetch_volume_data(sn_user, sn_pass):
    """Snowflake DW에 연결하여 요금제 제품군별 시계열 주문 데이터를 추출합니다."""
    print("[INFO] 내부 DB 물량 데이터 수집 시작")
    
    query = """

    [Security Notice]
    사내 의사결정에 필요한 물량 데이터 추출 쿼리이며,
    보안 규정상 상세 코드는 생략/마스킹 처리합니다.

    """
    
    # [MASKING] 계정 식별 호스트 및 데이터베이스 접속 정보 마스킹
    conn = snow.connect(
        account="***.ap-northeast-2.aws", user=sn_user, password=sn_pass,
        database="***", schema="PUBLIC"
    )
    try:
        cur = conn.cursor()
        cur.execute(query)
        df_volume = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    finally:
        cur.close()
        conn.close()
    
    df_volume['BASE_DATE'] = pd.to_datetime(df_volume['BASE_DATE'])
    df_volume.columns = ['ds', 'plan_a', 'plan_b']
    
    return df_volume[['ds', 'plan_a']].rename(columns={'plan_a': 'y'}), df_volume[['ds', 'plan_b']].rename(columns={'plan_b': 'y'})

# =============================================================================
# [4] Feature Engineering: 미래 기온 시뮬레이션 및 다중 임계값 Trigger 생성
# =============================================================================
def generate_weather_triggers(df_weather, predict_days):
    """
    1차 Prophet 모델을 이용해 향후 60일의 미래 기온을 권역별로 예측한 뒤, 
    전주 대비 기온 변화 수준(1도/2도/3도)에 따른 외부 회귀 Trigger 피처를 생성합니다.
    """
    print("[INFO] 기온 예측 및 온도 변화 트리거 파생 변수 생성")
    from prophet import Prophet
    
    future_weather_dict = {}
    for region in TARGET_STATIONS.values():
        df_temp = df_weather[df_weather['지역명'] == region][['날짜', '평균기온']].rename(columns={'날짜': 'ds', '평균기온': 'y'}).dropna()
        
        # 권역별 독자적인 계절성(Seasonality) 반영을 위한 독립 모델 적합
        m_temp = Prophet(yearly_seasonality=True, daily_seasonality=False)
        m_temp.fit(df_temp)
        
        future_temp = m_temp.make_future_dataframe(periods=predict_days)
        forecast_temp = m_temp.predict(future_temp)
        
        # 과거 실제 관측 기온 데이터와 미래 예측 yhat 결합
        future_weather_dict[region] = df_temp.set_index('ds')['y'].combine_first(forecast_temp.set_index('ds')['yhat'])

    # 전주 대비(7일 차분) 기온의 절대 변화량 계산
    df_temp_diff = pd.DataFrame(future_weather_dict).diff(periods=7).abs()
    
    # 비즈니스 도메인 지식을 반영한 다중 임계값(Threshold) 조건 처리
    # 타겟 지역 중 최소 2개 권역 이상에서 기온 급변 현상이 동시 포착될 때 시스템 트리거 작동
    return pd.DataFrame({
        'temp_trigger_1deg': ((df_temp_diff >= 1.0).sum(axis=1) >= 2).astype(int),
        'temp_trigger_2deg': ((df_temp_diff >= 2.0).sum(axis=1) >= 2).astype(int),
        'temp_trigger_3deg': ((df_temp_diff >= 3.0).sum(axis=1) >= 2).astype(int)
    }).reset_index()

# =============================================================================
# [5] Modeling: 제품군별 시계열 예측 파이프라인 (Prophet 외부 변수 결합)
# =============================================================================
def train_and_forecast(df_target, df_trigger, predict_days):
    """
    과거 주문 시계열 데이터와 공휴일 효과, 그리고 자체 생성한 날씨 트리거 외부 변수들을 
    결합하여 2차 메인 Prophet 모델을 학습시키고 미래 60일을 예측합니다.
    """
    from prophet import Prophet
    
    # 시계열 데이터와 날씨 파생 피처 결합
    df_train = pd.merge(df_target, df_trigger, on='ds', how='inner')
    
    # 최적의 베이지안 곡선 적합(Curve Fitting)을 위한 주요 파라미터 셋업
    model = Prophet(holidays=HOLIDAYS_DF, changepoint_prior_scale=0.1,
                    daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
    
    # 비즈니스 주기성을 반영하기 위한 커스텀 월간 계절성(Fourier Order 5) 주입
    model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
    
    # 단기 기상 충격 가중치 제어를 위한 다중 외부 회귀 변수(Regressor) 등록
    model.add_regressor('temp_trigger_1deg') 
    model.add_regressor('temp_trigger_2deg') 
    model.add_regressor('temp_trigger_3deg') 
    
    model.fit(df_train)
    
    # 미래 예측 프레임 생성 및 날씨 트리거 매핑
    future_with_trigger = pd.merge(model.make_future_dataframe(periods=predict_days), df_trigger, on='ds', how='left').fillna(0)
    return model.predict(future_with_trigger)

# =============================================================================
# [6] Main Automation Handler: AWS Lambda 진입점 및 대시보드 웹훅 연동
# =============================================================================
def lambda_handler(event, context):
    global secrets_cache
    try:
        # AWS Lambda의 Warm Start 메커니즘을 고려한 글로벌 캐시 스왑 기법 적용
        if secrets_cache is None:
            secrets_cache = get_secret()
            
        api_key = secrets_cache['API_KEY'] 
        gas_url = secrets_cache.get('WEBHOOK_URL', "https://script.google.com/macros/s/***/exec") # [MASKING] 웹훅 보안 처리
        sn_user = secrets_cache['user']
        sn_pass = secrets_cache['password']

        # 1. 외부 소스 엔티티 수집 및 전처리
        df_weather = fetch_weather_data(api_key)
        df_plan_a, df_plan_b = fetch_volume_data(sn_user, sn_pass) 
        df_trigger = generate_weather_triggers(df_weather, PREDICT_DAYS)
        
        # 2. 제품 스택별 핵심 모델 추론 연산
        forecast_plan_a = train_and_forecast(df_plan_a, df_trigger, PREDICT_DAYS)
        forecast_plan_b = train_and_forecast(df_plan_b, df_trigger, PREDICT_DAYS)
        
        # 3. 데이터 하이라이징 및 결과 통합 추출 (최근 미래 60일 관측 범위 제한)
        final_plan_a = forecast_plan_a[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(PREDICT_DAYS)
        final_plan_b = forecast_plan_b[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(PREDICT_DAYS)
        
        # 4. 전사 대시보드 공유를 위한 최종 합산 집계 DataFrame 생성
        final_result_sum = pd.DataFrame({
            'ds': final_plan_a['ds'],
            'total_yhat': (final_plan_a['yhat'] + final_plan_b['yhat']).astype(int),
            'total_lower': (final_plan_a['yhat_lower'] + final_plan_b['yhat_lower']).astype(int),
            'total_upper': (final_plan_a['yhat_upper'] + final_plan_b['yhat_upper']).astype(int)
        })
        
        # 대시보드(Google Sheets) 컴포넌트 규격에 최적화된 날짜 문자열 포맷팅 처리
        final_result_sum["ds"] = final_result_sum["ds"].dt.strftime("%Y. %-m. %-d")
        
        # 5. REST API를 활용한 Webhook 데이터 전송 (JSON 직렬화)
        data_json = final_result_sum.to_json(orient='records', date_format='iso')
        requests.post(gas_url, data=json.dumps(json.loads(data_json)))
        
        print("✅ [SUCCESS] 시계열 예측 파이프라인 및 데이터 전송 완료!")
        return {'statusCode': 200, 'body': json.dumps("Success")}
        
    except Exception as e:
        traceback.print_exc()
        print(f"[ERROR] 파이프라인 치명적 실패 에러: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps(f"Process failed: {str(e)}")}
