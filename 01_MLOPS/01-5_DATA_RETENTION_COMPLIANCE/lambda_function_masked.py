import json
import logging
from datetime import datetime
import boto3
import pymysql
import requests
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ==========================================
# 1. AWS Secrets Manager & Configuration
# ==========================================
AWS_REGION = "ap-northeast-2"
SECRET_NAME = "[MASKED_SECRET_NAME]"  # Security: 마스킹 처리
BATCH_SIZE = 1000  # Bulk 처리 단위


def get_secret(secret_name, region_name=AWS_REGION):
    """AWS Secrets Manager에서 자격 증명 JSON 수집"""
    client = boto3.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logging.error(f"❌ Secrets Manager 수집 실패 ({secret_name}): {e}")
        raise e

    if 'SecretString' in response:
        return json.loads(response['SecretString'])
    else:
        raise ValueError("시크릿 데이터가 String 형태가 아닙니다.")


def send_slack_alert(webhook_url, message, is_error=False):
    """Slack Webhook으로 배치 진행 상황 및 결과를 전송합니다."""
    if not webhook_url:
        logging.warning("⚠️ Slack Webhook URL이 설정되지 않아 알림을 건너뜁니다.")
        return

    emoji = "🚨" if is_error else "✅"
    payload = {"text": f"{emoji} [개인정보 보존기간 관리 배치] {message}"}

    try:
        resp = requests.post(webhook_url, data=json.dumps(payload), timeout=10)
        if resp.status_code != 200:
            logging.warning(f"⚠️ Slack 알림 전송 실패: status={resp.status_code}, body={resp.text}")
    except Exception as e:
        # Slack 알림 자체의 실패가 메인 배치를 죽이지 않도록 방어
        logging.warning(f"⚠️ Slack 알림 전송 중 예외 발생: {str(e)}")


def connect_db(host, secret, db_name):
    """PyMySQL 연결을 생성합니다."""
    if not db_name:
        raise ValueError(
            "DB 스키마 이름이 비어 있습니다. Secrets Manager에 'dbname1'(메인), "
            "'dbname2'(보존 전용 DB) 키를 추가했는지 확인하세요."
        )
    return pymysql.connect(
        host=host,
        port=int(secret.get('port', 3306)),
        user=secret.get('username'),
        password=secret.get('password'),
        database=db_name,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def transfer_data(main_conn, retention_conn, base_time):
    """
    [STEP 1] 메인 DB -> 보존 전용 DB (최근 5년간 탈퇴 유저 결제 내역 이관)

    [Security Notice] 실제 테이블/컬럼명 일부는 마스킹 처리했습니다.
    """
    logging.info("🚀 [STEP 1] 최근 5년간 탈퇴 회원 결제 내역 이관 시작...")

    with main_conn.cursor() as main_cursor, retention_conn.cursor() as retention_cursor:
        select_sql = """
            SELECT sp.*
            FROM [MASKED_USER_TABLE] u
            JOIN [MASKED_PAYMENT_TABLE] sp ON u.id = sp.user_id
            WHERE u.deleted_at IS NOT NULL
              AND sp.created_at >= DATE_SUB(%s, INTERVAL 5 YEAR)
        """

        main_cursor.execute(select_sql, (base_time,))
        total_transferred = 0

        while True:
            rows = main_cursor.fetchmany(BATCH_SIZE)
            if not rows:
                break

            columns = list(rows[0].keys())
            col_names = ", ".join([f"`{col}`" for col in columns])
            placeholders = ", ".join(["%s"] * len(columns))

            # 이미 이관된 건은 건너뛰도록 ON DUPLICATE KEY UPDATE로 멱등성 확보
            insert_sql = f"""
                INSERT INTO [MASKED_RETENTION_TABLE] ({col_names})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE id=id
            """

            values_list = [tuple(row[col] for col in columns) for row in rows]

            retention_cursor.executemany(insert_sql, values_list)
            retention_conn.commit()

            total_transferred += len(rows)
            logging.info(f"   - 현재까지 {total_transferred:,}건 이관 처리 완료...")

        logging.info(f"✅ [STEP 1 완료] 총 {total_transferred:,}건 이관 완료!")
        return total_transferred


def mask_expired_data_main(main_conn, base_time):
    """
    [STEP 2] 메인 DB의 결제 테이블 중, 탈퇴회원이면서 5년이 지난 결제내역의
    개인정보(이름/이메일/전화번호)를 마스킹합니다.
    (탈퇴회원 건만 대상으로 함 - 현역 회원 데이터는 절대 건드리지 않음)
    """
    logging.info("🧹 [STEP 2] 메인 DB에서 탈퇴회원의 5년 지난 데이터 마스킹 시작...")

    with main_conn.cursor() as main_cursor:
        # user_email은 UUID()로 행마다 서로 다른 무작위 값을 생성해 고유성 제약을 유지
        mask_sql = """
            UPDATE [MASKED_PAYMENT_TABLE] sp
            JOIN [MASKED_USER_TABLE] u ON u.id = sp.user_id
            SET
                sp.user_name = '탈퇴회원',
                sp.user_email = UUID(),
                sp.user_phone_number = '01000000000'
            WHERE u.deleted_at IS NOT NULL
              AND sp.created_at < DATE_SUB(%s, INTERVAL 5 YEAR)
              AND sp.user_name != '탈퇴회원'
        """

        affected_rows = main_cursor.execute(mask_sql, (base_time,))
        main_conn.commit()

        logging.info(f"✅ [STEP 2 완료] 메인 DB 탈퇴회원 5년 경과 데이터 총 {affected_rows:,}건 마스킹 완료!")
        return affected_rows


def mask_expired_data_retention(retention_conn, base_time):
    """
    [STEP 3] 보존 전용 DB 내 5년이 지난 데이터의 개인정보(이름/이메일/전화번호)를 마스킹합니다.
    (행 자체는 삭제하지 않고 남겨서 결제금액 등 거래 기록은 그대로 보관)
    """
    logging.info("🧹 [STEP 3] 보존 전용 DB에서 5년 지난 데이터 마스킹 시작...")

    with retention_conn.cursor() as retention_cursor:
        mask_sql = """
            UPDATE [MASKED_RETENTION_TABLE]
            SET
                user_name = '탈퇴회원',
                user_email = UUID(),
                user_phone_number = '01000000000'
            WHERE created_at < DATE_SUB(%s, INTERVAL 5 YEAR)
              AND user_name != '탈퇴회원'
        """

        affected_rows = retention_cursor.execute(mask_sql, (base_time,))
        retention_conn.commit()

        logging.info(f"✅ [STEP 3 완료] 5년 경과 데이터 총 {affected_rows:,}건 마스킹 완료!")
        return affected_rows


def run_batch():
    """
    ISMS 인증 심사 대응을 위한 개인정보 보존기간(5년) 관리 배치의 메인 실행 함수.
    탈퇴 회원의 결제 내역을 보존 전용 DB로 이관하고, 양쪽 DB에서 보존기간이
    지난 데이터의 개인정보만 마스킹 처리합니다(거래 기록 자체는 삭제하지 않음).
    """
    main_conn = None
    retention_conn = None
    execution_now = datetime.now()
    logging.info(f"⏰ 배치 실행 기준 시각: {execution_now}")

    slack_webhook_url = None

    try:
        db_secret = get_secret(SECRET_NAME)
        slack_webhook_url = db_secret.get('SLACK_WEBHOOK_URL')

        send_slack_alert(
            slack_webhook_url,
            f"배치 작업을 시작합니다. (기준시각: {execution_now.strftime('%Y-%m-%d %H:%M:%S')})",
            is_error=False
        )

        main_host = db_secret.get('host1')
        retention_host = db_secret.get('host2')
        main_db_name = db_secret.get('dbname1')
        retention_db_name = db_secret.get('dbname2')

        main_conn = connect_db(main_host, db_secret, main_db_name)
        retention_conn = connect_db(retention_host, db_secret, retention_db_name)

        transferred_count = transfer_data(main_conn, retention_conn, execution_now)
        main_masked_count = mask_expired_data_main(main_conn, execution_now)
        retention_masked_count = mask_expired_data_retention(retention_conn, execution_now)

        success_message = (
            f"배치 작업이 성공적으로 종료되었습니다! 🎉\n"
            f"- 최근 5년 이관 건수: `{transferred_count:,}` 건\n"
            f"- 메인 DB 탈퇴회원 5년 초과 마스킹 건수: `{main_masked_count:,}` 건\n"
            f"- 보존 전용 DB 5년 초과 마스킹 건수: `{retention_masked_count:,}` 건"
        )
        send_slack_alert(slack_webhook_url, success_message, is_error=False)

    except Exception as e:
        error_msg = f"배치 작업 중 오류가 발생했습니다! 💥\n- 에러 내용: `{str(e)}`"
        logging.error(f"❌ {error_msg}")

        if main_conn:
            main_conn.rollback()
        if retention_conn:
            retention_conn.rollback()

        send_slack_alert(slack_webhook_url, error_msg, is_error=True)

    finally:
        if main_conn:
            main_conn.close()
        if retention_conn:
            retention_conn.close()
        logging.info("DB 연결 정리 완료.")


def lambda_handler(event, context):
    """AWS Lambda 진입점"""
    run_batch()
    return {"statusCode": 200, "body": "batch finished"}


if __name__ == '__main__':
    run_batch()
