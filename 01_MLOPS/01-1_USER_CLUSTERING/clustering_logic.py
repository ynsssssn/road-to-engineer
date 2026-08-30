import os
import json
import boto3
import traceback
from datetime import datetime
import numpy as np
import pandas as pd

import snowflake.connector
from snowflake.connector import Error
from sklearn.preprocessing import RobustScaler
from sklearn.mixture import GaussianMixture

# =========================================================
# [1] Data Extraction: Snowflake 데이터 추출
# =========================================================
CACHED_CREDS = None 

def get_snowflake_creds():
    """AWS Secrets Manager에서 Snowflake 접속 정보를 안전하게 로드합니다."""
    secret_name = "[MASKED_SECRET_NAME]" # Security: 마스킹 처리
    region_name = "ap-northeast-2"
    
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

def get_conn():
    """Snowflake 데이터베이스 커넥션을 생성합니다 (Lambda Warm Start 최적화)."""
    global CACHED_CREDS
    if CACHED_CREDS is None:
        CACHED_CREDS = get_snowflake_creds()
        
    connection = snowflake.connector.connect(
        user=CACHED_CREDS['user'],
        password=CACHED_CREDS['password'],
        account=CACHED_CREDS['account'],
        database=CACHED_CREDS.get('database', '[MASKED_DB]'),
        schema=CACHED_CREDS.get('schema', '[MASKED_SCHEMA]')
    )
    return connection

def fetch_data(target_date):
    """
    SQL Injection 및 Date 포맷 에러를 방지하고, 데이터를 추출합니다.
    """
    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid target_date format. Must be YYYY-MM-DD")

    # Security: 실제 비즈니스 추출 쿼리 마스킹
    query = f"""
    -- [SECURITY NOTICE] 
    -- 사내 RFM 및 유저 행동 지표를 집계하는 원본 쿼리 생략
    -- SELECT ... FROM user_behavior_table WHERE base_date = '{target_date}'
    """
    
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(query)
        # 데이터를 가져와서 DataFrame으로 변환
        df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
        return df
    finally:
        cur.close()
        conn.close()

# =========================================================
# [2] Data Preprocessing: 전처리 및 아웃라이어/분포 조정
# =========================================================
def data_scaler(data):
    """
    1. 결측치 0 처리 (파생 변수 역산 충돌 방지)
    2. np.log1p 로그 변환 (극단적인 우측 꼬리 분포를 가우시안 형태로 치환)
    3. RobustScaler (극단적 아웃라이어 방어)
    """
    scaled_data = data.copy()
    feature_cols = [col for col in scaled_data.columns if col != 'USER_ID']
    
    scaled_data[feature_cols] = scaled_data[feature_cols].fillna(0)
    
    # [핵심] 로그 변환: Right-Skewed 분포를 GMM 가우시안 가정에 맞게 변환
    scaled_data[feature_cols] = np.log1p(scaled_data[feature_cols])
    
    # 아웃라이어 방어용 RobustScaler 적용
    scaler = RobustScaler()
    scaled_data[feature_cols] = scaler.fit_transform(scaled_data[feature_cols])
    
    return scaled_data

# =========================================================
# [3] ML Fine Tuning: AIC 기반 최적 군집 수(K) 자동 탐색
# =========================================================
def find_best_k_by_aic_elbow(X, min_k=10, max_k=25):
    """
    AIC(Akaike Information Criterion) 지표의 2차 차분(기울기 변화량)을 계산하여 
    오버피팅을 방지하는 가장 최적의 엘보우 포인트(K)를 자동으로 탐색합니다.
    """
    print(f"🔍 AIC 기반 최적 군집 수(K) 자동 탐색 중... (범위: {min_k} ~ {max_k})")
    k_range = range(min_k, max_k + 1)
    aic_scores = []
    
    for k in k_range:
        # covariance_type='full': VVIP 등 넓게 퍼진 아웃라이어를 타원형으로 포용
        gmm = GaussianMixture(n_components=k, covariance_type='full', random_state=42)
        gmm.fit(X)
        aic_scores.append(gmm.aic(X))
        
    # 2차 차분을 통해 기울기가 가장 격하게 꺾이는 엘보우 지점 탐색
    aic_diff1 = np.diff(aic_scores)
    aic_diff2 = np.diff(aic_diff1)
    elbow_index = np.argmax(aic_diff2)
    best_k = k_range[elbow_index + 1]
    
    print(f"🎯 AIC 엘보우 포인트 발견: 최적의 K = {best_k}")
    return best_k

# =========================================================
# [4] Modeling: Gaussian Mixture Model (GMM) 클러스터링
# =========================================================
def user_clustering(scaled_data, count_of_cluster, raw_data):
    """최적의 K를 바탕으로 GMM 군집화를 수행하고 결과를 원본 데이터에 맵핑합니다."""
    print(f"GMM 클러스터링 수행 중... (K={count_of_cluster})")
    train_values = scaled_data.drop('USER_ID', axis=1, errors='ignore')
    
    clusterer = GaussianMixture(n_components=count_of_cluster, covariance_type='full', random_state=42)
    cluster_labels = clusterer.fit_predict(train_values)
    
    classification_raw = raw_data.copy()
    classification_raw['classification'] = cluster_labels
    
    # 비즈니스 해석 및 네이밍을 위해 '원본 데이터' 기준으로 군집별 평균(Mean) 산출
    summary_raw = classification_raw.groupby('classification').mean().reset_index()
    return classification_raw, summary_raw

# =========================================================
# [5] Business Logic: 타겟팅 세그먼트 네이밍 
# =========================================================
def get_automated_cluster_names(cluster_summary):
    """
    [Security Notice]
    사내 의사결정에 필요한 CRM 타겟팅 로직 및 핵심 비즈니스 임계값으로 구현하였으며, 
    보안 규정상 상세 코드는 생략/마스킹 처리합니다.
    """
    df = cluster_summary.reset_index(drop=True)
    results = []
    
    for _, row in df.iterrows():
        cid = row['classification']
        
        # -------------------------------------------------------------
        # 실제 환경에서는 RFM 수치, 방문 주기, 요금제 가입 여부 등을 
        # 폭포수(Waterfall) 형태의 조건문으로 검사하여 MECE한 태그를 할당함
        # -------------------------------------------------------------
        status_tag = "[MASKED_STATUS]"   # ex. 활성/휴면/이탈위험
        subs_tag = "[MASKED_SUBS]"       # ex. 월정액/자유/스윙보터
        feature_tag = "[MASKED_FEATURE]" # ex. VVIP/뉴비/체리피커
        
        results.append({
            'classification': cid, 
            'cluster 1': status_tag, 
            'cluster 2': subs_tag, 
            'cluster 3': feature_tag
        })
        
    return pd.DataFrame(results)

# =========================================================
# [6] Main Execution: End-to-End 파이프라인
# =========================================================
def run_pipeline(target_date, count_of_cluster=None):
    """
    데이터 추출부터 GMM 군집화, 네이밍까지 전체 파이프라인을 실행합니다.
    """
    print(f"[{target_date}] 유저 클러스터링 파이프라인 시작")
    
    # 1. 데이터 추출
    raw_data = fetch_data(target_date)
    if raw_data.empty:
        raise ValueError(f"{target_date}에 해당하는 데이터가 없습니다.")
        
    # 2. 데이터 스케일링 (Log1p + Robust)
    scaled_data = data_scaler(raw_data)
    train_values = scaled_data.drop('USER_ID', axis=1, errors='ignore')
    
    # 3. AIC 기반 최적 K 자동 탐색 
    if count_of_cluster is None:
        best_k = find_best_k_by_aic_elbow(train_values, min_k=10, max_k=25)
    else:
        best_k = count_of_cluster
        
    # 4. GMM 모델링 수행
    classification_raw, summary_raw = user_clustering(scaled_data, best_k, raw_data)
    
    # 5. 비즈니스 룰 기반 네이밍 병합
    cluster_names = get_automated_cluster_names(summary_raw)
    final_df = pd.merge(classification_raw, cluster_names, on='classification', how='left')
    
    print("✅ 모든 파이프라인 완료!")
    return final_df

# AWS Lambda Handler 예시
def lambda_handler(event, context):
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        target_date = event.get('target_date', today_str)
        
        # 파이프라인 실행
        final_result_df = run_pipeline(target_date)
        
        # S3 업로드 로직 (마스킹)
        # s3_client.upload_file(...)
        
        return {'statusCode': 200, 'body': json.dumps('Pipeline Success')}
    except Exception as e:
        traceback.print_exc()
        return {'statusCode': 500, 'body': json.dumps(f'Error: {str(e)}')}
