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
secrets_cache = None

# [MASKING] 실제 타겟 관측소 코드 및 지역명은 알파벳과 더미 코드로 추상화
TARGET_STATIONS = {'001': 'Region_A', '002': 'Region_B', '003': 'Region_C', '004': 'Region_D'}
PREDICT_DAYS = 60

# [MASKING] 사내 프로모션/휴무일 패턴이 유추되지 않도록 임의의 날짜(일반 국경일 예시)로 마스킹
HOLIDAYS_DF = pd.DataFrame({
    'holiday': 'event',
    'ds': pd.to_datetime([
        '2023-01-01', '2023-05-05', '2023-12-25',
        '2024-01-01', '2024-05-05', '2024-12-25',
        '2025-01-01', '2025-05-05', '2025-12-25'
    ]),
    'lower_window': -1,
    'upper_window': 1
})

def get_secret():
    # [MASKING] 시크릿 이름 마스킹
    secret_name = "***_Connection" 
    region_name = "ap-northeast-2"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# -----------------------------------------------------------------------------
# [2] 외부 API 날씨 데이터 수집
# -----------------------------------------------------------------------------
def fetch_weather_data(api_key):
    print("[INFO] 기상청 API 일자료 수집 시작")
    url = 'https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    
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
                time.sleep(0.5)
            except Exception as e:
                pass

    df_weather = pd.DataFrame(all_weather_data)
    df_weather['날짜'] = pd.to_datetime(df_weather['날짜'], format='%Y-%m-%d')
    for col in ['평균기온', '일강수량(총량)', '일최대강수량(1hr)']:
        df_weather[col] = pd.to_numeric(df_weather[col], errors='coerce')

    return df_weather.sort_values(['날짜', '지역명']).reset_index(drop=True)

# -----------------------------------------------------------------------------
# [3] 내부 데이터 웨어하우스 물량 수집
# -----------------------------------------------------------------------------
def fetch_volume_data(sn_user, sn_pass):
    print("[INFO] 내부 DB 물량 데이터 수집 시작")
    import snowflake.connector as snow 
    
    # [MASKING] 실제 비즈니스 테이블명(wash, subscription 등)과 요금제 명칭을 추상화된 이름(Plan_A, Plan_B)으로 마스킹
    query = """
    with count_order_eda as (
        select
            a.target_date as base_date
            , iff(c.plan_type_code = 0, 0, 1) as product_type
        from order_master a
            inner join plan_master c on a.plan_id = c.id
        where 1=1
            and a.created_date >= '2023-01-01' 
            and a.status_code = 'ACTIVE'
    )

    , count_order as (
        select 
            base_date
            , count(iff(product_type = 0, 1, null)) as "Plan_A"
            , count(iff(product_type = 1, 1, null)) as "Plan_B"
        from count_order_eda 
        group by base_date
    )
    
    select * from count_order order by base_date
    """
    
    # [MASKING] 계정 및 DB명 마스킹 처리
    conn = snow.connect(
        account="***.ap-northeast-2.aws", user=sn_user, password=sn_pass,
        database="***", schema="PUBLIC"
    )
    cur = conn.cursor()
    cur.execute(query)
    df_volume = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    cur.close()
    conn.close()
    
    df_volume['BASE_DATE'] = pd.to_datetime(df_volume['BASE_DATE'])
    
    # 변수명도 도메인 종속적인 단어(subs, free)에서 범용적인 명칭으로 변경
    df_volume.columns = ['ds', 'plan_a', 'plan_b']
    return df_volume[['ds', 'plan_a']].rename(columns={'plan_a': 'y'}), df_volume[['ds', 'plan_b']].rename(columns={'plan_b': 'y'})

# -----------------------------------------------------------------------------
# [4] 기온 예측 및 다중 임계값 Trigger 생성
# -----------------------------------------------------------------------------
def generate_weather_triggers(df_weather, predict_days):
    print("[INFO] 기온 예측 및 온도 변화 트리거 파생 변수 생성")
    from prophet import Prophet
    
    future_weather_dict = {}
    for region in TARGET_STATIONS.values():
        df_temp = df_weather[df_weather['지역명'] == region][['날짜', '평균기온']].rename(columns={'날짜': 'ds', '평균기온': 'y'}).dropna()
        m_temp = Prophet(yearly_seasonality=True, daily_seasonality=False)
        m_temp.fit(df_temp)
        future_temp = m_temp.make_future_dataframe(periods=predict_days)
        forecast_temp = m_temp.predict(future_temp)
        future_weather_dict[region] = df_temp.set_index('ds')['y'].combine_first(forecast_temp.set_index('ds')['yhat'])

    df_temp_diff = pd.DataFrame(future_weather_dict).diff(periods=7).abs()
    return pd.DataFrame({
        'temp_trigger_1deg': ((df_temp_diff >= 1.0).sum(axis=1) >= 2).astype(int),
        'temp_trigger_2deg': ((df_temp_diff >= 2.0).sum(axis=1) >= 2).astype(int),
        'temp_trigger_3deg': ((df_temp_diff >= 3.0).sum(axis=1) >= 2).astype(int)
    }).reset_index()

# -----------------------------------------------------------------------------
# [5] 물량 예측 파이프라인
# -----------------------------------------------------------------------------
def train_and_forecast(df_target, df_trigger, predict_days):
    from prophet import Prophet
    
    df_train = pd.merge(df_target, df_trigger, on='ds', how='inner')
    model = Prophet(holidays=HOLIDAYS_DF, changepoint_prior_scale=0.1,
                    daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
    model.add_seasonality(name='monthly', period=30.5, fourier_order=5)
    model.add_regressor('temp_trigger_1deg') 
    model.add_regressor('temp_trigger_2deg') 
    model.add_regressor('temp_trigger_3deg') 
    model.fit(df_train)
    future_with_trigger = pd.merge(model.make_future_dataframe(periods=predict_days), df_trigger, on='ds', how='left').fillna(0)
    return model.predict(future_with_trigger)

# -----------------------------------------------------------------------------
# [6] 메인 핸들러
# -----------------------------------------------------------------------------
def lambda_handler(event, context):
    global secrets_cache
    try:
        if secrets_cache is None:
            secrets_cache = get_secret()
            
        api_key = secrets_cache['API_KEY'] # [MASKING] API Key 변수명 일반화
        gas_url = secrets_cache.get('WEBHOOK_URL', "https://script.google.com/macros/s/***/exec") # [MASKING] 웹훅 URL
        sn_user = secrets_cache['user']
        sn_pass = secrets_cache['password']

        df_weather = fetch_weather_data(api_key)
        df_plan_a, df_plan_b = fetch_volume_data(sn_user, sn_pass) # 변수명 마스킹 반영
        df_trigger = generate_weather_triggers(df_weather, PREDICT_DAYS)
        
        forecast_plan_a = train_and_forecast(df_plan_a, df_trigger, PREDICT_DAYS)
        forecast_plan_b = train_and_forecast(df_plan_b, df_trigger, PREDICT_DAYS)
        
        final_plan_a = forecast_plan_a[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(PREDICT_DAYS)
        final_plan_b = forecast_plan_b[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(PREDICT_DAYS)
        
        final_result_sum = pd.DataFrame({
            'ds': final_plan_a['ds'],
            'total_yhat': (final_plan_a['yhat'] + final_plan_b['yhat']).astype(int),
            'total_lower': (final_plan_a['yhat_lower'] + final_plan_b['yhat_lower']).astype(int),
            'total_upper': (final_plan_a['yhat_upper'] + final_plan_b['yhat_upper']).astype(int)
        })
        final_result_sum["ds"] = final_result_sum["ds"].dt.strftime("%Y. %-m. %-d")
        data_json = final_result_sum.to_json(orient='records', date_format='iso')
        requests.post(gas_url, data=json.dumps(json.loads(data_json)))
        
        print("[SUCCESS] 시계열 예측 파이프라인 및 데이터 전송 완료!")
        return {'statusCode': 200, 'body': json.dumps("Success")}
        
    except Exception as e:
        print(f"[ERROR] 파이프라인 에러: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps(f"Process failed: {str(e)}")}
