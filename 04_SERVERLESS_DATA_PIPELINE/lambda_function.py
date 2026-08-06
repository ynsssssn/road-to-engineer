import os
import json
import requests
import pandas as pd
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

# =========================================================
# [1] Security & Credentials Management (AWS Secrets Manager)
# =========================================================
secrets_cache = None

def get_secret():
    """AWS Secrets Manager에서 DB 및 GAS 인증 정보를 안전하게 로드합니다."""
    # [Security] 실제 Secret Name 및 Region은 환경 변수 또는 마스킹 처리
    secret_name = os.environ.get("SECRET_NAME", "[YOUR_AWS_SECRET_NAME]")
    region_name = "ap-northeast-2"
    
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# =========================================================
# [2] Query Dictionary: 코호트 리텐션 SQL 쿼리 (마스킹 적용)
# =========================================================
QUERIES = {
    "구독_클래식_수거": """
    -- [SECURITY NOTICE] 사내 DB 스키마 및 세부 비즈니스 로직 마스킹 완료
    WITH subs_rd AS (
        SELECT user_id, real_collection_date AS wash_date
        FROM YOUR_DB.PUBLIC.wash_table
        WHERE 1=1 AND status = 'COMPLETED'
    ),
    first_sub AS (
        SELECT user_id, MIN(wash_date) AS first_wash_date
        FROM subs_rd GROUP BY user_id
    ),
    user_conv_dat AS (
        SELECT 
            TO_VARCHAR(fs.first_wash_date, 'YYYY-MM') AS cohort_month,
            rd.user_id,
            FLOOR(DATEDIFF(day, fs.first_wash_date, rd.wash_date) / 30.5) AS seq
        FROM subs_rd rd
        JOIN first_sub fs ON rd.user_id = fs.user_id
    )
    SELECT 
        cohort_month,
        COUNT(DISTINCT user_id) AS user_count,
        COUNT(DISTINCT IFF(seq = 0, user_id, NULL)) AS ret_0,
        COUNT(DISTINCT IFF(seq = 1, user_id, NULL)) AS ret_1
    FROM user_conv_dat
    GROUP BY 1 ORDER BY 1
    """,

    "자유_클래식_수거": """
    -- [SECURITY NOTICE] Dummy Query Template
    SELECT '2026-01' AS cohort_month, 1000 AS user_count, 1000 AS ret_0, 750 AS ret_1
    """,

    "구독자유_통합_수거": """
    -- [SECURITY NOTICE] Dummy Query Template
    SELECT '2026-01' AS cohort_month, 2000 AS user_count, 2000 AS ret_0, 1500 AS ret_1
    """
}

# =========================================================
# [3] Data Extraction: Snowflake 접속 및 데이터 Fetch
# =========================================================
def fetch_snowflake_data(target, sn_user, sn_pass):
    """
    Snowflake 데이터베이스에 접속하여 지정된 target의 SQL 쿼리를 실행하고
    Pandas DataFrame으로 변환합니다.
    """
    import snowflake.connector as snow
    
    if target not in QUERIES:
        raise ValueError(f"유효하지 않은 target 파라미터입니다: {target}")
        
    query = QUERIES[target]
    print(f"[INFO] Snowflake 쿼리 실행 시작: target={target}")
    
    # [Security] account, database 등 접속 정보 마스킹
    conn = snow.connect(
        account="[YOUR_ACCOUNT_ID].ap-northeast-2.aws",
        user=sn_user,
        password=sn_pass,
        database="[YOUR_DATABASE_NAME]",
        schema="PUBLIC"
    )
    cur = conn.cursor()
    cur.execute(query)
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    cur.close()
    conn.close()
    
    return df

# =========================================================
# [4] Main Execution: AWS Lambda Handler & Pipeline Engine
# =========================================================
def lambda_handler(event, context):
    """
    AWS Lambda 엔트리포인트 함수
    event를 통해 target을 수신하며, 구글 앱스 스크립트(GAS) Web App으로 
    JSON 직렬화된 데이터를 전송합니다.
    """
    global secrets_cache
    try:
        # Secrets Caching (Warm Start 최적화)
        if secrets_cache is None:
            secrets_cache = get_secret()
            
        sn_user = secrets_cache['user']
        sn_pass = secrets_cache['password']
        
        # [Security] 외부 노출 위험이 있는 Web App URL은 Secrets Manager 또는 환경변수 처리
        gas_url = secrets_cache.get('RET_GAS_WEB_URL', os.environ.get('RET_GAS_WEB_URL', "https://script.google.com/macros/s/YOUR_GAS_DEPLOYMENT_ID/exec"))

        # target 파라미터 분기 (기본값: 'all')
        target = event.get('target', 'all')
        targets_to_run = list(QUERIES.keys()) if target == 'all' else [target]

        print(f"[INFO] 실행 대상 target 목록: {targets_to_run}")

        for t in targets_to_run:
            print(f"[INFO] >>> 작업 시작: {t}")
            df = fetch_snowflake_data(t, sn_user, sn_pass)
            
            payload = {
                "target": t,
                "data": json.loads(df.to_json(orient='records', date_format='iso'))
            }
            
            # GAS WebApp으로 POST 데이터 전송
            print(f"[INFO] Google Apps Script로 전송 중... (Target: {t}, Rows: {len(df)})")
            resp = requests.post(gas_url, data=json.dumps(payload), timeout=120)
            print(f"✅ [SUCCESS] {t} 업데이트 완료! (GAS 응답: {resp.text})")

        return {'statusCode': 200, 'body': json.dumps(f"Retention Pipeline Success: {targets_to_run}")}
        
    except Exception as e:
        print(f"[ERROR] 파이프라인 오류: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps(f"Process failed: {str(e)}")}