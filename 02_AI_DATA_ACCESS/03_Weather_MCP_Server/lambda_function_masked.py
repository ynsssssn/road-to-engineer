"""
사내 날씨 MCP 커넥터 (claude.ai 사용자 지정 커넥터용)

[Security Notice] 시크릿 이름 등 사내 식별 정보는 마스킹 처리했습니다.

- 기상청 단기예보 API(VilageFcstInfoService_2.0)를 감싸는 원격 MCP 서버
- AWS Lambda + 함수 URL(인증 NONE) · 주소: https://<url>/mcp
- 인증: 요청 헤더 `Authorization: Bearer <토큰>` 만 허용 (URL 경로·쿼리 토큰은 받지 않음)
- 표준 라이브러리 + boto3 만 사용 (패키지 설치 없이 zip 하나로 배포)

도구
  get_current_weather  : 서울·부산 현재 날씨 (초단기실황 · 매시간)
  get_short_forecast   : 서울·부산 단기 예보 (단기예보 · 하루 8번, 최대 3일)

시크릿 (정보보호팀 조건 — 키·토큰은 코드/환경변수에 두지 않음)
  [MASKED_SECRET_NAME] = {"KMA_API_KEY": "...", "MCP_TOKEN": "..."}

환경변수 (비밀값 없음)
  KMA_SECRET_NAME   : 위 시크릿 이름
  CACHE_MINUTES     : 같은 발표 시각 결과 재사용 시간 (기본 30)

로그: 키·토큰·요청 헤더·기상청 요청 URL 은 남기지 않습니다.
"""
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import boto3

KST = timezone(timedelta(hours=9))
BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"

# 기상청 격자 좌표 (nx, ny)
REGIONS = {
    "서울": (60, 127),   # 서울 중구
    "부산": (98, 76),    # 부산 중구
}

SKY_CODE = {"1": "맑음", "3": "구름많음", "4": "흐림"}
PTY_CODE = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기",
            "5": "빗방울", "6": "빗방울눈날림", "7": "눈날림"}

SERVER_INFO = {"name": "weather-mcp", "version": "1.0.0"}
SUPPORTED_PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]

_secret = None   # {"KMA_API_KEY": ..., "MCP_TOKEN": ...} — 컨테이너가 살아 있는 동안 재사용
_cache = {}      # (op, base_date, base_time, nx, ny) -> (stored_epoch, items)


# ---------------------------------------------------------------------------
# 시크릿
# ---------------------------------------------------------------------------
def get_secret():
    global _secret
    if _secret is None:
        sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))
        _secret = json.loads(sm.get_secret_value(SecretId=os.environ["KMA_SECRET_NAME"])["SecretString"])
    return _secret


def get_api_key():
    return get_secret()["KMA_API_KEY"]


def redact(text):
    """오류 메시지에 키·토큰이 섞여 나가지 않도록 가림 (로그·응답 공통)"""
    s = _secret or {}
    for v in (s.get("KMA_API_KEY"), s.get("MCP_TOKEN")):
        if v:
            text = text.replace(v, "***").replace(urllib.parse.quote(v, safe=""), "***")
    return text


def token_ok(headers):
    """Authorization: Bearer <토큰> 를 고정시간 비교로 확인"""
    expected = get_secret().get("MCP_TOKEN", "")
    got = headers.get("authorization", "")
    if not expected or not got.startswith("Bearer "):
        return False
    return hmac.compare_digest(got[len("Bearer "):].encode(), expected.encode())


# ---------------------------------------------------------------------------
# 기상청 호출
# ---------------------------------------------------------------------------


def kma_call(op, base_date, base_time, nx, ny, num_rows):
    key = (op, base_date, base_time, nx, ny)
    ttl = int(os.environ.get("CACHE_MINUTES", "30")) * 60
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1], hit[0]

    params = {
        "serviceKey": get_api_key(), "pageNo": "1", "numOfRows": str(num_rows),
        "dataType": "JSON", "base_date": base_date, "base_time": base_time,
        "nx": str(nx), "ny": str(ny),
    }
    url = f"{BASE_URL}/{op}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=8) as resp:
        raw = resp.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 키 오류 등은 XML 로 옵니다 (예: SERVICE_KEY_IS_NOT_REGISTERED_ERROR)
        raise RuntimeError(f"기상청 응답이 JSON 이 아닙니다: {raw[:200]}")

    header = data.get("response", {}).get("header", {})
    if header.get("resultCode") != "00":
        raise RuntimeError(f"기상청 오류 {header.get('resultCode')}: {header.get('resultMsg')}")
    items = data["response"]["body"]["items"]["item"]
    now = time.time()
    _cache[key] = (now, items)
    return items, now


def ncst_base(now):
    """초단기실황: 매시 정각 자료가 HH:40 이후 제공 → 여유 있게 45분 기준"""
    t = now - timedelta(minutes=45)
    return t.strftime("%Y%m%d"), t.strftime("%H00")


def fcst_base(now):
    """단기예보: 02·05·08·11·14·17·20·23시 발표, 발표 후 약 10분 뒤 제공 → 15분 기준"""
    t = now - timedelta(minutes=15)
    for h in (23, 20, 17, 14, 11, 8, 5, 2):
        if t.hour >= h:
            return t.strftime("%Y%m%d"), f"{h:02d}00"
    prev = t - timedelta(days=1)
    return prev.strftime("%Y%m%d"), "2300"


def to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 도구 구현
# ---------------------------------------------------------------------------
def current_weather(region):
    nx, ny = REGIONS[region]
    bd, bt = ncst_base(datetime.now(KST))
    items, stored = kma_call("getUltraSrtNcst", bd, bt, nx, ny, 20)
    v = {i["category"]: i["obsrValue"] for i in items}
    return {
        "region": region,
        "observed_at": f"{bd[:4]}-{bd[4:6]}-{bd[6:]} {bt[:2]}:00",
        "temperature_c": to_num(v.get("T1H")),
        "precip_1h_mm": to_num(v.get("RN1")),
        "precip_type": PTY_CODE.get(str(v.get("PTY")), v.get("PTY")),
        "humidity_pct": to_num(v.get("REH")),
        "wind_speed_ms": to_num(v.get("WSD")),
        "fetched_at": datetime.fromtimestamp(stored, KST).strftime("%Y-%m-%d %H:%M"),
    }


def short_forecast(region, hours):
    nx, ny = REGIONS[region]
    bd, bt = fcst_base(datetime.now(KST))
    items, stored = kma_call("getVilageFcst", bd, bt, nx, ny, 1000)

    slots, days = {}, {}
    for i in items:
        d, t, c, val = i["fcstDate"], i["fcstTime"], i["category"], i["fcstValue"]
        s = slots.setdefault((d, t), {})
        s[c] = val
        day = days.setdefault(d, {"pop_max": None, "tmin": None, "tmax": None, "tmps": [], "rehs": []})
        if c == "POP":
            p = to_num(val)
            day["pop_max"] = p if day["pop_max"] is None else max(day["pop_max"], p)
        elif c == "TMN":
            day["tmin"] = to_num(val)
        elif c == "TMX":
            day["tmax"] = to_num(val)
        elif c == "TMP" and to_num(val) is not None:
            day["tmps"].append(to_num(val))
        elif c == "REH" and to_num(val) is not None:
            day["rehs"].append(to_num(val))

    now_key = datetime.now(KST).strftime("%Y%m%d%H00")
    upcoming = [k for k in sorted(slots) if k[0] + k[1] >= now_key]   # 지난 시각은 빼고 지금 시각부터
    hourly = []
    for (d, t) in upcoming[:hours]:
        s = slots[(d, t)]
        hourly.append({
            "time": f"{d[4:6]}-{d[6:]} {t[:2]}:00",
            "temperature_c": to_num(s.get("TMP")),
            "precip_prob_pct": to_num(s.get("POP")),
            "precip_type": PTY_CODE.get(str(s.get("PTY")), s.get("PTY")),
            "precip_mm": s.get("PCP"),          # "강수없음" / "1mm 미만" / "3.0mm" 등 문자열
            "snow_cm": s.get("SNO"),            # "적설없음" / "1cm 미만" / "2.0cm" 등 문자열
            "humidity_pct": to_num(s.get("REH")),
            "wind_speed_ms": to_num(s.get("WSD")),
            "sky": SKY_CODE.get(str(s.get("SKY")), s.get("SKY")),
        })

    # 일별 최저/최고: 기상청 TMN/TMX 가 없으면(발표 시각상 지난 시간대·마지막 날) 시간별 기온으로 채움
    daily = []
    for d, v in sorted(days.items()):
        from_hourly = v["tmin"] is None or v["tmax"] is None
        tmin = v["tmin"] if v["tmin"] is not None else (min(v["tmps"]) if v["tmps"] else None)
        tmax = v["tmax"] if v["tmax"] is not None else (max(v["tmps"]) if v["tmps"] else None)
        daily.append({
            "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "temp_min_c": tmin,
            "temp_max_c": tmax,
            "temp_from_hourly": from_hourly,   # true = 기상청 일 최저/최고가 아니라 남은 시간대 기온으로 계산 (참고용)
            "precip_prob_max_pct": v["pop_max"],
            "humidity_avg_pct": round(sum(v["rehs"]) / len(v["rehs"])) if v["rehs"] else None,
        })

    return {
        "region": region,
        "issued_at": f"{bd[:4]}-{bd[4:6]}-{bd[6:]} {bt[:2]}:00",
        "daily": daily,
        "hourly": hourly,
        "fetched_at": datetime.fromtimestamp(stored, KST).strftime("%Y-%m-%d %H:%M"),
    }


REGION_PROP = {
    "regions": {
        "type": "array",
        "items": {"type": "string", "enum": list(REGIONS)},
        "description": "조회할 지역. 생략하면 서울·부산 모두",
    }
}

TOOLS = [
    {
        "name": "get_current_weather",
        "title": "현재 날씨",
        "description": "서울·부산의 현재 기온, 1시간 강수량, 강수 형태, 습도, 풍속 (기상청 초단기실황, 매시간 갱신)",
        "inputSchema": {"type": "object", "properties": REGION_PROP, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "get_short_forecast",
        "title": "단기 예보",
        "description": "서울·부산의 일별 최저/최고 기온·최대 강수확률·평균 습도와 시간별 기온·강수확률·강수량·적설·습도·풍속·하늘상태 (기상청 단기예보, 하루 8번 발표, 최대 3~4일)",
        "inputSchema": {
            "type": "object",
            "properties": {
                **REGION_PROP,
                "hours": {"type": "integer", "minimum": 1, "maximum": 72, "default": 24,
                          "description": "시간별 예보 개수 (기본 24)"},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
]


def call_tool(name, args):
    regions = args.get("regions") or list(REGIONS)
    bad = [r for r in regions if r not in REGIONS]
    if bad:
        raise ValueError(f"지원하지 않는 지역: {bad} (가능: {list(REGIONS)})")
    if name == "get_current_weather":
        return {"results": [current_weather(r) for r in regions]}
    if name == "get_short_forecast":
        hours = max(1, min(72, int(args.get("hours", 24))))
        return {"results": [short_forecast(r, hours) for r in regions]}
    raise KeyError(name)


# ---------------------------------------------------------------------------
# MCP (Streamable HTTP, 상태 없음 · JSON 응답)
# ---------------------------------------------------------------------------
def handle_rpc(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:                       # 알림(notifications/*)은 응답 없음
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}

    if method == "initialize":
        req = params.get("protocolVersion")
        ver = req if req in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
        return ok({"protocolVersion": ver, "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": SERVER_INFO,
                   "instructions": "사내 날씨 커넥터. 서울·부산 현재 날씨와 단기 예보(기상청)를 제공합니다."})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        try:
            data = call_tool(name, params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                       "structuredContent": data, "isError": False})
        except KeyError:
            return err(-32602, f"알 수 없는 도구: {name}")
        except Exception as e:            # 도구 실패는 isError 로 돌려줌 (프로토콜 오류 아님)
            msg = redact(f"{type(e).__name__}: {e}")
            print(f"[ERROR] {name}: {msg}")
            return ok({"content": [{"type": "text", "text": f"날씨 조회 실패: {msg}"}], "isError": True})
    return err(-32601, f"지원하지 않는 메서드: {method}")


def resp(status, body=None):
    r = {"statusCode": status, "headers": {"Content-Type": "application/json"}}
    if body is not None:
        r["body"] = json.dumps(body, ensure_ascii=False)
    return r


def lambda_handler(event, context):
    path = event.get("rawPath", "")
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    # 토큰은 헤더로만 받습니다 (claude.ai 커넥터 "Request headers" 에 등록 — 암호화 저장, URL·로그에 남지 않음)
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    if path.rstrip("/") != "/mcp" or not token_ok(headers):
        return resp(404, {"error": "not found"})
    if method != "POST":                  # SSE 스트림은 쓰지 않음
        return {"statusCode": 405, "headers": {"Allow": "POST"}}

    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    try:
        msg = json.loads(body)
    except json.JSONDecodeError:
        return resp(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})

    if isinstance(msg, list):
        out = [r for r in (handle_rpc(m) for m in msg) if r is not None]
        return resp(200, out) if out else {"statusCode": 202}
    out = handle_rpc(msg)
    return resp(200, out) if out is not None else {"statusCode": 202}
