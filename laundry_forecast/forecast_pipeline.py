import os
import json
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

# -----------------------------------------------------------------------------
# [1] Configuration & Constants
# -----------------------------------------------------------------------------
# Lambda 환경에서 매번 Secret을 호출하지 않도록 캐싱 처리
secrets_cache = None

# 예측 대상이 되는 주요 지역 기상관측소 코드 (서울, 인천, 수원, 동두천)
TARGET_STATIONS = {'108': '서울', '112': '인천', '119': '수원', '98': '동두천'}

# 예측 수행 기간 (60일)
PREDICT_DAYS = 60

# Prophet 모델에 반영할 휴일(명절, 대체공휴일, 선거일 등) 데이터프레임
HOLIDAYS_DF = pd.DataFrame({
    'holiday': '대체',
    'ds': pd.to_datetime([
        '2022-03-09', '2022-05-09', '2022-06-01', '2022-09-12',
        '2023-05-29', '2023-10-02', '2024-04-10', '2024-05-06',
        '2025-03-03', '2025-05-06', '2025-06-03', '2025-10-08',
        '2026-03-02', '2026-05-25', '2026-08-17', '2026-10-05'
    ]),
    'lower_window': -1,  # 휴일 전날의 영향 반영
    'upper_window': 1    # 휴일 다음날의 영향 반영
})

def get_secret():
    """AWS Secrets Manager에서 API 키 및 DB 접속 정보 등 민감 데이터를 가져옵니다."""
    secret_name = "***_Connection" # [MASKING] 시크릿 이름 마스킹
    region_name = "ap-northeast-2"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# -----------------------------------------------------------------------------
# [2] 기상청 API 날씨 데이터 수집
# -----------------------------------------------------------------------------
def fetch_weather_data(kma_api_key):
    """
    기상청 종관기상관측(ASOS) API를 호출하여 과거부터 어제까지의 기상 데이터를 수집합니다.
    - 수집 항목: 평균기온, 일강수량, 일최대강수량
    """
    print("[INFO] 기상청 API 일자료 수집 시작")
    url = 'https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    
    # API 호출 시 데이터 건수 제한을 피하기 위해 연도별로 나누어 호출
    year_ranges = [
        ('20230101', '20231231'), ('20240101', '20241231'),
        ('20250101', '20251231'), ('20260101', yesterday_str)
    ]
    all_weather_data = []

    for stn_id, stn_name in TARGET_STATIONS.items():
        for start_date, end_date in year_ranges:
            params = {
                'ServiceKey': kma_api_key, 'pageNo': '1', 'numOfRows': '999',
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
                                '날짜': item.get('tm', ''), 
                                '지역명': stn_name,
                                '평균기온': item.get('avgTa', ''),
                                '일강수량(총량)': item.get('sumRn', '') or '0.0',
                                '일최대강수량(1hr)': item.get('max1hrRn', '') or '0.0'
                            })
                # API 호출 속도 제한(Rate Limit) 방지를 위한 대기
                time.sleep(0.5)
            except Exception as e:
                pass

    # 수집된 데이터를 DataFrame으로 변환 및 타입 캐스팅
    df_weather = pd.DataFrame(all_weather_data)
    df_weather['날짜'] = pd.to_datetime(df_weather['날짜'], format='%Y-%m-%d')
    for col in ['평균기온', '일강수량(총량)', '일최대강수량(1hr)']:
        df_weather[col] = pd.to_numeric(df_weather[col], errors='coerce')

    return df_weather.sort_values(['날짜', '지역명']).reset_index(drop=True)

# -----------------------------------------------------------------------------
# [3] Snowflake 내부 물량 데이터 수집
# -----------------------------------------------------------------------------
def fetch_volume_data(sn_user, sn_pass):
    """
    Snowflake 데이터 웨어하우스에 접속하여 일자별/요금제별(월정액/자유) 물량 데이터를 집계합니다.
    """
    print("[INFO] Snowflake 물량 데이터 수집 시작")
    import snowflake.connector as snow 
    
    # 쿼리 가독성을 위해 CTE 구조 사용 및 팀 컨벤션 적용
    query = """
    with count_wash_eda as (
        -- 23년 이후 정상 상태인 주문 건에 대해 요금제 타입(subscription_type)을 분류
        select
            a.real_collection_date as base_date
            , iff(a.laundry24_pgi is null, iff(c.laundry_plan_type = 0, 0, iff(d.laundrette_use_yn = 1, 1, 2)), 3) as subscription_type
        from wash a
            inner join subscription_order b on a.subscription_order_id = b.id
            inner join subscription c on b.subscription_id = c.id
            inner join laundry_plan d on c.laundry_plan_id = d.id
        where 1=1
            and a.created_date >= '2023-01-01' 
            and a.status not in (4, 17)
    )

    , count_wash as (
        -- 일자별(base_date)로 월정액(0)과 자유요금제(1, 2) 물량을 각각 카운트
        select 
            base_date
            , count(iff(subscription_type = 0, 1, null)) as "월정액"
            , count(iff(subscription_type in (1, 2), 1, null)) as "자유"
        from count_wash_eda 
        group by base_date
    )
    
    select * from count_wash order by base_date
    """
    
    # [MASKING] 계정 및 DB명 마스킹 처리
    conn = snow.connect(
        account="***.ap-northeast-2.aws", user=sn_user, password=sn_pass,
        database="***", schema="PUBLIC"
    )
    cur = conn.cursor()
    cur.execute(query)
    df_wash = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    cur.close()
    conn.close()
    
    # Prophet 모델 입력을 위해 컬럼명을 'ds'(날짜)와 'y'(예측값)로 변경
    df_wash['BASE_DATE'] = pd.to_datetime(df_wash['BASE_DATE'])
    df_wash.columns = ['ds', 'subs', 'free']
    
    return df_wash[['ds', 'subs']].rename(columns={'subs': 'y'}), df_wash[['ds', 'free']].rename(columns={'free': 'y'})

# -----------------------------------------------------------------------------
# [4] 기온 예측 및 다중 임계값 Trigger 생성
# -----------------------------------------------------------------------------
def generate_weather_triggers(df_weather, predict_days):
    """
    Prophet을 활용하여 향후 기온을 선제적으로 예측하고, 
    급격한 기온 변화(전주 대비 1도, 2도, 3도 차이)를 감지하는 Trigger(파생 변수)를 생성합니다.
    """
    print("[INFO] 기온 60일 예측 및 1,2,3도 파생 변수(Trigger) 생성")
    from prophet import Prophet
    
    future_weather_dict = {}
    
    # 각 관측소별로 기온 예측 모델 피팅
    for region in TARGET_STATIONS.values():
        df_temp = df_weather[df_weather['지역명'] == region][['날짜', '평균기온']].rename(columns={'날짜': 'ds', '평균기온': 'y'}).dropna()
        m_temp = Prophet(yearly_seasonality=True, daily_seasonality=False)
        m_temp.fit(df_temp)
        
        future_temp = m_temp.make_future_dataframe(periods=predict_days)
        forecast_temp = m_temp.predict(future_temp)
        # 과거 실제 데이터와 미래 예측 데이터를 결합
        future_weather_dict[region] = df_temp.set_index('ds')['y'].combine_first(forecast_temp.set_index('ds')['yhat'])

    # 전주(7일 전) 대비 기온의 절대적 변화량 계산
    df_temp_diff = pd.DataFrame(future_weather_dict).diff(periods=7).abs()
    
    # 4개 관측소 중 2곳 이상에서 임계값(1,2,3도) 이상의 기온 변화가 발생하면 Trigger = 1 부여
    return pd.DataFrame({
        'temp_trigger_1deg': ((df_temp_diff >= 1.0).sum(axis=1) >= 2).astype(int),
        'temp_trigger_2deg': ((df_temp_diff >= 2.0).sum(axis=1) >= 2).astype(int),
        'temp_trigger_3deg': ((df_temp_diff >= 3.0).sum(axis=1) >= 2).astype(int)
    }).reset_index()

# -----------------------------------------------------------------------------
# [5] 물량 예측 파이프라인 (Prophet 모델링)
# -----------------------------------------------------------------------------
def train_and_forecast(df_target, df_trigger, predict_days):
    """
    기본 물량 시계열 데이터에 기온 변화 Trigger 변수를 추가(Regressor)하여 
    최종 물량을 예측하는 Prophet 모델을 학습시키고 결과를 반환합니다.
    """
    from prophet import Prophet
    
    # 종속 변수(물량)와 독립 변수(날씨 Trigger) 결합
    df_train = pd.merge(df_target, df_trigger, on='ds', how='inner')
    
    # 월(Month) 주기성 추가 및 휴일 효과 반영
    model = Prophet(holidays=HOLIDAYS_DF, changepoint_prior_scale=0.1,
                    daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
    model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
    
    # 외부 회귀 변수로 기온 변화 Trigger 추가
    model.add_regressor('temp_trigger_1deg') 
    model.add_regressor('temp_trigger_2deg') 
    model.add_regressor('temp_trigger_3deg') 
    model.fit(df_train)
    
    # 미래 날짜에 대한 DataFrame 생성 및 Trigger 매핑
    future_with_trigger = pd.merge(model.make_future_dataframe(periods=predict_days), df_trigger, on='ds', how='left').fillna(0)
    return model.predict(future_with_trigger)

# -----------------------------------------------------------------------------
# [6] 메인 핸들러 (AWS Lambda 진입점)
# -----------------------------------------------------------------------------
def lambda_handler(event, context):
    """
    Lambda 실행 시 가장 먼저 호출되는 메인 함수입니다.
    수집 -> 피처 엔지니어링 -> 학습/예측 -> 결과 적재(Google Sheets)의 흐름을 제어합니다.
    """
    global secrets_cache
    try:
        # 1. 시크릿 매니저에서 인증 정보 로드
        if secrets_cache is None:
            secrets_cache = get_secret()
            
        kma_api_key = secrets_cache['KMA_API_KEY']
        # [MASKING] Google App Script 웹훅 URL 마스킹
        gas_url = secrets_cache.get('GAS_WEB_URL', "https://script.google.com/macros/s/***/exec") 
        sn_user = secrets_cache['user']
        sn_pass = secrets_cache['password']

        # 2. 데이터 수집 및 전처리
        df_weather = fetch_weather_data(kma_api_key)
        df_subs, df_free = fetch_volume_data(sn_user, sn_pass)
        df_trigger = generate_weather_triggers(df_weather, PREDICT_DAYS)
        
        # 3. 요금제별 물량 예측 모델링
        forecast_subs = train_and_forecast(df_subs, df_trigger, PREDICT_DAYS)
        forecast_free = train_and_forecast(df_free, df_trigger, PREDICT_DAYS)
        
        # 4. 결과 통합 (월정액 + 자유 요금제 물량 합산)
        final_subs = forecast_subs[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(PREDICT_DAYS)
        final_free = forecast_free[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(PREDICT_DAYS)
        
        final_result_sum = pd.DataFrame({
            'ds': final_subs['ds'],
            'total_yhat': (final_subs['yhat'] + final_free['yhat']).astype(int),
            'total_lower': (final_subs['yhat_lower'] + final_free['yhat_lower']).astype(int),
            'total_upper': (final_subs['yhat_upper'] + final_free['yhat_upper']).astype(int)
        })
        
        # 5. Google Sheets로 데이터 전송 (JSON 포맷)
        final_result_sum["ds"] = final_result_sum["ds"].dt.strftime("%Y. %-m. %-d")
        data_json = final_result_sum.to_json(orient='records', date_format='iso')
        requests.post(gas_url, data=json.dumps(json.loads(data_json)))
        
        print("✅ [SUCCESS] 오리지널 Prophet 기반 물량 예측 및 구글 시트 전송 완료!")
        return {'statusCode': 200, 'body': json.dumps("Success")}
        
    except Exception as e:
        print(f"[ERROR] 파이프라인 에러: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps(f"Process failed: {str(e)}")}