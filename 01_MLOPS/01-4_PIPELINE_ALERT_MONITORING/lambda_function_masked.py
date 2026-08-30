import os
import json
import requests
import pandas as pd
from datetime import datetime
import boto3

# =========================================================
# [1] Security & Credentials Management (AWS Secrets Manager)
# =========================================================
secrets_cache = None

def get_secret():
    """AWS Secrets Manager에서 DB 접속 정보 및 Slack Webhook URL을 안전하게 로드합니다."""
    secret_name = "[MASKED_SECRET_NAME]"  # Security: 마스킹 처리
    region_name = "ap-northeast-2"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])


# =========================================================
# [2] Slack 알림: 파이프라인 상태 전송
# =========================================================
def send_slack_alert(webhook_url, message, is_error=True):
    """Slack Webhook으로 파이프라인 상태 알림을 전송합니다."""
    if not webhook_url:
        print("[WARNING] Slack Webhook URL이 설정되지 않아 알림을 건너뜁니다.")
        return

    emoji = "🚨" if is_error else "✅"
    payload = {"text": f"{emoji} [Pipeline Alert] {message}"}

    try:
        resp = requests.post(webhook_url, data=json.dumps(payload), timeout=10)
        if resp.status_code != 200:
            print(f"[WARNING] Slack 알림 전송 실패: status={resp.status_code}, body={resp.text}")
    except Exception as e:
        # [핵심 설계] Slack 알림 자체의 실패가 메인 파이프라인을 죽이지 않도록 별도 방어
        print(f"[WARNING] Slack 알림 전송 중 예외 발생: {str(e)}")


# =========================================================
# [3] Data Quality: '성공'과 '정상'을 구분하는 최소 검증 로직
# =========================================================
# [Security Notice] 실제 임계값 및 지표 컬럼명은 사내 비즈니스 로직으로
# 보안 규정상 마스킹 처리하였습니다.
MIN_EXPECTED_ROWS = {
    "[MASKED_TARGET_1]": 1,
    "[MASKED_TARGET_2]": 1,
    "[MASKED_TARGET_3]": 1,
}


def check_data_quality(target, df):
    """
    row 수 및 핵심 지표 값 기반의 최소한의 이상치 감지.
    - row가 0건: 원본 데이터 소스나 필터 조건에 문제가 있을 가능성
    - row 수가 기대 최소치보다 적음: 부분 실패 또는 원본 API/DB 이슈 가능성
    - 핵심 지표 컬럼에 비정상 값(0 이하 등) 포함: 계산 로직 이상 신호
    반환값: (is_healthy: bool, message: str)
    """
    row_count = len(df)
    expected_min = MIN_EXPECTED_ROWS.get(target, 1)

    if row_count == 0:
        return False, f"target='{target}' 결과가 0건입니다. 원본 데이터 또는 필터 조건을 확인해주세요."

    if row_count < expected_min:
        return False, f"target='{target}' row 수({row_count}건)가 기대 최소치({expected_min}건)보다 적습니다."

    # [MASKED] 실제 핵심 지표 컬럼명 및 임계값 조건은 보안 규정상 생략
    # if "[MASKED_METRIC_COLUMN]" in df.columns and (df["[MASKED_METRIC_COLUMN]"] <= 0).any():
    #     return False, f"target='{target}' 핵심 지표에 비정상 값이 포함되어 있습니다."

    return True, f"target='{target}' 정상 ({row_count}건)"


# =========================================================
# [4] Data Extraction (마스킹)
# =========================================================
def fetch_data(target, sn_user, sn_pass):
    """
    [Security Notice]
    사내 의사결정에 필요한 데이터 추출 쿼리이며,
    보안 규정상 상세 코드는 생략/마스킹 처리합니다.
    """
    import snowflake.connector as snow

    query = "-- [MASKED QUERY] 실제 비즈니스 로직 생략"

    conn = snow.connect(
        account="[MASKED_ACCOUNT]",
        user=sn_user,
        password=sn_pass,
        database="[MASKED_DB]",
        schema="PUBLIC"
    )
    cur = conn.cursor()
    cur.execute(query)
    df = pd.DataFrame(cur.fetchall(), columns=[col[0] for col in cur.description])
    cur.close()
    conn.close()
    return df


# =========================================================
# [5] Main Execution: AWS Lambda Handler
# =========================================================
def lambda_handler(event, context):
    """
    AWS Lambda 엔트리포인트.

    설계 포인트:
    1) target 단위로 개별 try/except 처리 → 하나가 실패해도 나머지는 계속 진행
    2) row 수·핵심 지표 기반 사전 이상치 감지 → '성공'과 '정상'을 구분
    3) 에러/이상치 발생 시 즉시 Slack 알림 + 전체 실행 결과 요약 리포트
    """
    global secrets_cache
    try:
        if secrets_cache is None:
            secrets_cache = get_secret()

        sn_user = secrets_cache['user']
        sn_pass = secrets_cache['password']
        slack_webhook_url = secrets_cache.get('SLACK_WEBHOOK_URL', os.environ.get('SLACK_WEBHOOK_URL'))
        gas_url = secrets_cache.get('GAS_WEB_URL', "[MASKED_GAS_URL]")

        target = event.get('target', 'all')
        targets_to_run = list(MIN_EXPECTED_ROWS.keys()) if target == 'all' else [target]

        run_summary = []

        for t in targets_to_run:
            try:
                df = fetch_data(t, sn_user, sn_pass)

                # --- 사전 감지: row 수 / 값 기반 이상치 체크 ---
                is_healthy, dq_message = check_data_quality(t, df)
                if not is_healthy:
                    print(f"[WARNING] {dq_message}")
                    send_slack_alert(slack_webhook_url, dq_message, is_error=True)
                    run_summary.append(f"⚠️ {t}: 데이터 이상치 감지 ({len(df)}건)")
                    continue

                payload = {"target": t, "data": json.loads(df.to_json(orient='records', date_format='iso'))}
                resp = requests.post(gas_url, data=json.dumps(payload), timeout=120)

                if resp.status_code != 200:
                    raise RuntimeError(f"GAS 응답 실패: status={resp.status_code}")

                run_summary.append(f"✅ {t}: 정상 완료 ({len(df)}건)")

            except Exception as target_error:
                error_message = f"target='{t}' 처리 중 오류: {str(target_error)}"
                print(f"[ERROR] {error_message}")
                send_slack_alert(slack_webhook_url, error_message, is_error=True)
                run_summary.append(f"🚨 {t}: 실패 - {str(target_error)}")

        summary_text = "\n".join(run_summary)
        send_slack_alert(
            slack_webhook_url,
            f"파이프라인 실행 완료 ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n{summary_text}",
            is_error=any("🚨" in line or "⚠️" in line for line in run_summary)
        )

        return {'statusCode': 200, 'body': json.dumps(f"Result: {run_summary}")}

    except Exception as e:
        error_message = f"파이프라인 치명적 오류: {str(e)}"
        print(f"[ERROR] {error_message}")
        try:
            fallback_webhook = os.environ.get('SLACK_WEBHOOK_URL')
            send_slack_alert(fallback_webhook, error_message, is_error=True)
        except Exception:
            pass
        return {'statusCode': 500, 'body': json.dumps(f"Process failed: {str(e)}")}
