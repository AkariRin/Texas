"""鉴权 API 路由 —— 登录、登出、TOTP、WebAuthn、Session 管理。"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog
import webauthn
from fastapi import APIRouter, Cookie, Request
from fastapi.responses import JSONResponse

from src.api.schemas.auth import (
    SessionInfoResponse,
    TokenLoginRequest,
    TOTPSetupConfirmRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    WebAuthnCredentialInfo,
    WebAuthnLoginFinishRequest,
    WebAuthnRegisterFinishRequest,
)
from src.core.config import get_settings
from src.core.utils.response import fail, ok
from src.services.auth import (
    AuthNotFoundError,
    AuthService,
    InvalidTOTPCodeError,
    TOTPNotConfiguredError,
)

if TYPE_CHECKING:
    from starlette.responses import Response

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(request: Request) -> AuthService:
    """从 app.state 获取 AuthService。"""
    return request.app.state.auth_service  # type: ignore[no-any-return]


def _get_client_ip(request: Request) -> str:
    """获取客户端 IP（兼容反向代理）。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, session_id: str, ttl: int, *, secure: bool) -> None:
    """设置 Session Cookie。"""
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=ttl,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    """清除 Session Cookie。"""
    response.delete_cookie(key="session_id", path="/")


# ── 静态令牌登录 ──


@router.post("/login")
async def login(body: TokenLoginRequest, request: Request) -> Any:
    """静态令牌登录，成功后设置 session_id cookie。"""
    auth = _get_auth_service(request)
    ip = _get_client_ip(request)

    if await auth.check_fail_limit(ip):
        return JSONResponse(
            status_code=429,
            content=fail("登录尝试次数过多，请 15 分钟后重试", code=429),
        )

    if not await auth.verify_static_token(body.token):
        count = await auth.increment_fail_count(ip)
        logger.warning("静态令牌登录失败", ip=ip, fail_count=count, event_type="auth.login_failed")
        return JSONResponse(status_code=401, content=fail("令牌错误", code=401))

    await auth.clear_fail_count(ip)
    session_id = await auth.create_session("token")
    resp = JSONResponse(content=ok(None, message="登录成功"))
    settings = get_settings()
    _set_session_cookie(resp, session_id, settings.AUTH_SESSION_TTL, secure=settings.is_production)
    logger.info("静态令牌登录成功", ip=ip, event_type="auth.login_success")
    return resp


# ── 登出 ──


@router.post("/logout")
async def logout(request: Request, session_id: str | None = Cookie(default=None)) -> Any:
    """撤销当前 Session（不存在时静默忽略），清除 cookie。"""
    auth = _get_auth_service(request)
    if session_id:
        await auth.revoke_session(session_id)
    resp = JSONResponse(content=ok(None, message="已登出"))
    _clear_session_cookie(resp)
    return resp


# ── TOTP 登录 ──


@router.post("/totp/verify")
async def totp_verify(body: TOTPVerifyRequest, request: Request) -> Any:
    """TOTP 码登录，成功后设置 session_id cookie。"""
    auth = _get_auth_service(request)
    ip = _get_client_ip(request)

    if await auth.check_fail_limit(ip):
        return JSONResponse(
            status_code=429,
            content=fail("登录尝试次数过多，请 15 分钟后重试", code=429),
        )

    try:
        valid = await auth.verify_totp(body.code)
    except TOTPNotConfiguredError:
        return JSONResponse(
            status_code=403,
            content={**fail("TOTP 未配置"), "error_code": "TOTP_NOT_CONFIGURED"},
        )

    if not valid:
        count = await auth.increment_fail_count(ip)
        logger.warning("TOTP 登录失败", ip=ip, fail_count=count, event_type="auth.totp_failed")
        return JSONResponse(status_code=401, content=fail("TOTP 验证码错误", code=401))

    await auth.clear_fail_count(ip)
    session_id = await auth.create_session("totp")
    resp = JSONResponse(content=ok(None, message="登录成功"))
    settings = get_settings()
    _set_session_cookie(resp, session_id, settings.AUTH_SESSION_TTL, secure=settings.is_production)
    return resp


# ── Session 信息 ──


@router.get("/session")
async def session_info(request: Request, session_id: str | None = Cookie(default=None)) -> Any:
    """返回当前 Session 信息。"""
    if not session_id:
        return JSONResponse(status_code=401, content=fail("未登录"))
    auth = _get_auth_service(request)
    data = await auth.get_session_data(session_id)
    if data is None:
        return JSONResponse(status_code=401, content=fail("Session 已过期"))
    created_at = data.get("created_at", "")
    ttl = get_settings().AUTH_SESSION_TTL
    try:
        created_dt = datetime.fromisoformat(created_at)
        expires_dt = created_dt + timedelta(seconds=ttl)
        expires_at = expires_dt.isoformat()
    except ValueError, TypeError:
        expires_at = ""
    resp_data = SessionInfoResponse(
        auth_method=data.get("auth_method", ""),
        created_at=created_at,
        expires_at=expires_at,
    )
    return JSONResponse(content=ok(resp_data.model_dump()))


# ── TOTP 设置 ──


@router.get("/totp/setup")
async def totp_setup_get(request: Request, session_id: str | None = Cookie(default=None)) -> Any:
    """获取 TOTP 设置 URI（需已登录）。"""
    if not session_id:
        return JSONResponse(status_code=401, content=fail("未登录"))
    auth = _get_auth_service(request)
    uri, secret = await auth.get_totp_setup_uri(session_id)
    return JSONResponse(content=ok(TOTPSetupResponse(otpauth_uri=uri, secret=secret).model_dump()))


@router.post("/totp/setup")
async def totp_setup_post(
    body: TOTPSetupConfirmRequest,
    request: Request,
    session_id: str | None = Cookie(default=None),
) -> Any:
    """确认绑定 TOTP（需已登录）。"""
    if not session_id:
        return JSONResponse(status_code=401, content=fail("未登录"))
    auth = _get_auth_service(request)
    try:
        await auth.confirm_totp_setup(session_id, body.code)
    except AuthNotFoundError as e:
        return JSONResponse(status_code=400, content=fail(str(e)))
    except InvalidTOTPCodeError:
        return JSONResponse(status_code=400, content=fail("验证码错误，请重试"))
    return JSONResponse(content=ok(None, message="TOTP 绑定成功"))


# ── WebAuthn 登录 begin ──


@router.get("/webauthn/login/begin")
async def webauthn_login_begin(request: Request) -> Any:
    """返回 WebAuthn 认证 challenge（公开端点，白名单内）。"""
    auth = _get_auth_service(request)
    credentials = await auth.get_webauthn_credentials()
    challenge_bytes, challenge_id = await auth.generate_webauthn_challenge()

    allow_credentials = [
        {
            "type": "public-key",
            "id": base64.urlsafe_b64encode(c.credential_id).rstrip(b"=").decode(),
        }
        for c in credentials
    ]
    challenge_b64 = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode()
    settings = get_settings()
    return JSONResponse(
        content=ok(
            {
                "challenge_id": challenge_id,
                "challenge_b64": challenge_b64,
                "rp_id": settings.AUTH_RP_ID,
                "allow_credentials": allow_credentials,
                "user_verification": "preferred",
            }
        )
    )


# ── WebAuthn 登录 finish ──


@router.post("/webauthn/login/finish")
async def webauthn_login_finish(body: WebAuthnLoginFinishRequest, request: Request) -> Any:
    """完成 WebAuthn 认证，成功后设置 session_id cookie。"""
    auth = _get_auth_service(request)
    settings = get_settings()

    challenge_bytes = await auth.consume_webauthn_challenge(body.challenge_id)
    if challenge_bytes is None:
        return JSONResponse(status_code=400, content=fail("Challenge 已过期或无效"))

    raw_id_b64: str = body.credential.get("rawId", "")
    remainder = len(raw_id_b64) % 4
    padded = raw_id_b64 + "=" * (4 - remainder) if remainder != 0 else raw_id_b64
    try:
        credential_id_bytes = base64.urlsafe_b64decode(padded)
    except Exception:
        return JSONResponse(status_code=400, content=fail("无效的 credential_id"))

    cred = await auth.get_webauthn_credential_by_id(credential_id_bytes)
    if cred is None:
        return JSONResponse(status_code=400, content=fail("Passkey 未注册"))

    origin = f"http{'s' if settings.is_production else ''}://{settings.AUTH_RP_ID}"
    try:
        authentication_verification = webauthn.verify_authentication_response(
            credential=body.credential,
            expected_challenge=challenge_bytes,
            expected_rp_id=settings.AUTH_RP_ID,
            expected_origin=origin,
            credential_public_key=cred.public_key,
            credential_current_sign_count=cred.sign_count,
            require_user_verification=False,
        )
    except Exception as exc:
        logger.warning("WebAuthn 认证失败", error=str(exc), event_type="auth.webauthn_failed")
        return JSONResponse(status_code=401, content=fail("Passkey 认证失败"))

    await auth.update_sign_count(credential_id_bytes, authentication_verification.new_sign_count)
    session_id = await auth.create_session("webauthn")
    resp = JSONResponse(content=ok(None, message="登录成功"))
    _set_session_cookie(resp, session_id, settings.AUTH_SESSION_TTL, secure=settings.is_production)
    return resp


# ── WebAuthn 注册 begin（需已登录）──


@router.get("/webauthn/register/begin")
async def webauthn_register_begin(request: Request) -> Any:
    """返回 WebAuthn 注册 challenge（需已登录）。"""
    auth = _get_auth_service(request)
    settings = get_settings()
    challenge_bytes, challenge_id = await auth.generate_webauthn_challenge()
    challenge_b64 = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode()
    return JSONResponse(
        content=ok(
            {
                "challenge_id": challenge_id,
                "challenge_b64": challenge_b64,
                "rp_id": settings.AUTH_RP_ID,
                "rp_name": settings.AUTH_RP_NAME,
                "user": {"id": "admin", "name": "admin", "displayName": "管理员"},
                "authenticator_selection": {
                    "resident_key": "preferred",
                    "user_verification": "preferred",
                },
            }
        )
    )


# ── WebAuthn 注册 finish（需已登录）──


@router.post("/webauthn/register/finish")
async def webauthn_register_finish(body: WebAuthnRegisterFinishRequest, request: Request) -> Any:
    """完成 WebAuthn 注册，保存 Passkey 凭据（需已登录）。"""
    auth = _get_auth_service(request)
    settings = get_settings()

    challenge_bytes = await auth.consume_webauthn_challenge(body.challenge_id)
    if challenge_bytes is None:
        return JSONResponse(status_code=400, content=fail("Challenge 已过期或无效"))

    origin = f"http{'s' if settings.is_production else ''}://{settings.AUTH_RP_ID}"
    try:
        registration_verification = webauthn.verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge_bytes,
            expected_rp_id=settings.AUTH_RP_ID,
            expected_origin=origin,
            require_user_verification=False,
        )
    except Exception as exc:
        logger.warning(
            "WebAuthn 注册失败", error=str(exc), event_type="auth.webauthn_register_failed"
        )
        return JSONResponse(status_code=400, content=fail(f"Passkey 注册失败：{exc}"))

    await auth.save_webauthn_credential(
        credential_id=registration_verification.credential_id,
        public_key=registration_verification.credential_public_key,
        sign_count=registration_verification.sign_count,
        device_name=body.device_name,
    )
    return JSONResponse(content=ok(None, message="Passkey 注册成功"))


# ── WebAuthn 凭据列表（需已登录）──


@router.get("/webauthn/credentials")
async def webauthn_credentials(request: Request) -> Any:
    """列出所有已注册的 Passkey 设备。"""
    auth = _get_auth_service(request)
    creds = await auth.get_webauthn_credentials()
    data = [
        WebAuthnCredentialInfo(
            credential_id_b64=base64.urlsafe_b64encode(c.credential_id).rstrip(b"=").decode(),
            device_name=c.device_name,
            created_at=c.created_at.isoformat(),
            last_used_at=c.last_used_at.isoformat(),
        ).model_dump()
        for c in creds
    ]
    return JSONResponse(content=ok(data))


# ── WebAuthn 删除凭据（需已登录）──


@router.delete("/webauthn/{credential_id}")
async def webauthn_delete_credential(credential_id: str, request: Request) -> Any:
    """删除指定 Passkey 设备（credential_id 为 base64url 编码）。"""
    auth = _get_auth_service(request)
    try:
        await auth.delete_webauthn_credential(credential_id)
    except AuthNotFoundError:
        return JSONResponse(status_code=404, content=fail("Passkey 不存在"))
    return JSONResponse(content=ok(None, message="Passkey 已删除"))
