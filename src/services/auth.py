"""鉴权业务逻辑服务 —— 令牌验证、Session 管理、失败限速。"""

from __future__ import annotations

import base64
import secrets
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pyotp
import structlog
from passlib.context import CryptContext  # type: ignore[import-untyped]
from sqlalchemy import select

from src.models.auth import AdminCredential, WebAuthnCredential

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.core.cache.client import CacheClient
    from src.core.config import Settings

logger = structlog.get_logger()

# ── 自定义异常 ──


class TOTPNotConfiguredError(Exception):
    """TOTP 未绑定。"""


class InvalidTOTPCodeError(Exception):
    """TOTP 验证码错误。"""


class AuthNotFoundError(Exception):
    """凭据不存在。"""


class RateLimitExceededError(Exception):
    """登录失败次数超限。"""


# ── 常量 ──

_FAIL_KEY_PREFIX = "auth:fail:"
_SESSION_KEY_PREFIX = "auth:session:"
_CHALLENGE_KEY_PREFIX = "auth:challenge:"
_TOTP_PENDING_PREFIX = "auth:totp_pending:"
_MAX_FAIL_COUNT = 10
_FAIL_TTL = 900  # 15 分钟
_CHALLENGE_TTL = 300  # 5 分钟
_TOTP_PENDING_TTL = 600  # 10 分钟

_pwd_context: CryptContext | None = None


def _get_pwd_context(rounds: int) -> CryptContext:
    """懒加载 CryptContext（bcrypt work factor 运行时可配置）。"""
    global _pwd_context  # noqa: PLW0603
    if _pwd_context is None:
        _pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=rounds)
    return _pwd_context


class AuthService:
    """鉴权核心服务。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cache: CacheClient,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache
        self._settings = settings

    # ── 启动引导 ──

    async def bootstrap_token(self) -> None:
        """检查 admin_credentials 表，为空时生成令牌并以 WARNING 级别打印。"""
        if await self.has_credential():
            return
        raw_token = secrets.token_urlsafe(32)
        ctx = _get_pwd_context(self._settings.AUTH_BCRYPT_ROUNDS)
        token_hash = ctx.hash(raw_token)
        async with self._session_factory() as session:
            session.add(AdminCredential(token_hash=token_hash))
            await session.commit()
        logger.warning(
            "首次启动：已生成管理员静态令牌，请妥善保存（此消息仅出现一次）",
            token=raw_token,
            event_type="auth.bootstrap_token",
        )

    async def has_credential(self) -> bool:
        """返回 admin_credentials 表是否有记录。"""
        async with self._session_factory() as session:
            result = await session.execute(select(AdminCredential).limit(1))
            return result.scalar_one_or_none() is not None

    # ── 静态令牌验证 ──

    async def verify_static_token(self, raw_token: str) -> bool:
        """bcrypt 验证静态令牌，返回是否匹配。"""
        async with self._session_factory() as session:
            result = await session.execute(select(AdminCredential).limit(1))
            cred = result.scalar_one_or_none()
        if cred is None:
            return False
        ctx = _get_pwd_context(self._settings.AUTH_BCRYPT_ROUNDS)
        return bool(ctx.verify(raw_token, cred.token_hash))

    # ── Session 管理 ──

    async def create_session(self, auth_method: str) -> str:
        """创建 Redis Session，返回 session_id（uuid4 字符串）。"""
        session_id = str(uuid.uuid4())
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        data: dict[str, Any] = {
            "created_at": datetime.now(UTC).isoformat(),
            "auth_method": auth_method,
        }
        await self._cache.set(key, data, ttl=self._settings.AUTH_SESSION_TTL)
        return session_id

    async def validate_session(self, session_id: str) -> bool:
        """验证 Session 是否存在于 Redis。"""
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        return await self._cache.exists(key)

    async def get_session_data(self, session_id: str) -> dict[str, Any] | None:
        """获取 Session 数据，不存在返回 None。"""
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        return await self._cache.get(key)

    async def revoke_session(self, session_id: str) -> None:
        """从 Redis 删除 Session（不存在时静默忽略）。"""
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        await self._cache.delete(key)

    # ── 失败限速 ──

    async def increment_fail_count(self, ip: str) -> int:
        """递增登录失败计数，返回当前次数。"""
        key = f"{_FAIL_KEY_PREFIX}{ip}"
        count = await self._cache.incr(key)
        await self._cache.expire(key, _FAIL_TTL)
        return count

    async def check_fail_limit(self, ip: str) -> bool:
        """返回是否超过失败限制（True = 被封锁）。"""
        key = f"{_FAIL_KEY_PREFIX}{ip}"
        val = await self._cache.get(key)
        if val is None:
            return False
        return int(val) >= _MAX_FAIL_COUNT

    async def clear_fail_count(self, ip: str) -> None:
        """登录成功后清除失败计数。"""
        key = f"{_FAIL_KEY_PREFIX}{ip}"
        await self._cache.delete(key)

    # ── WebAuthn Challenge ──

    async def generate_webauthn_challenge(self) -> tuple[bytes, str]:
        """生成 WebAuthn challenge，存入 Redis，返回 (challenge_bytes, challenge_id)。

        challenge_id 作为 begin 响应字段返回前端，finish 请求中带回用于查找。
        """
        challenge_bytes = secrets.token_bytes(32)
        challenge_id = secrets.token_urlsafe(16)
        key = f"{_CHALLENGE_KEY_PREFIX}{challenge_id}"
        challenge_b64 = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode()
        await self._cache.set(key, challenge_b64, ttl=_CHALLENGE_TTL)
        return challenge_bytes, challenge_id

    async def consume_webauthn_challenge(self, challenge_id: str) -> bytes | None:
        """从 Redis 取出并删除 challenge bytes（防重放），不存在返回 None。"""
        key = f"{_CHALLENGE_KEY_PREFIX}{challenge_id}"
        val = await self._cache.get(key)
        if val is None:
            return None
        await self._cache.delete(key)
        # val 是 base64url 无 padding 字符串
        padded = val + "=" * (4 - len(val) % 4) if len(val) % 4 != 0 else val
        return base64.urlsafe_b64decode(padded)

    # ── WebAuthn 凭据 CRUD ──

    async def get_webauthn_credentials(self) -> list[WebAuthnCredential]:
        """返回所有已注册的 Passkey 凭据列表。"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(WebAuthnCredential).order_by(WebAuthnCredential.created_at)
            )
            return list(result.scalars().all())

    async def get_webauthn_credential_by_id(
        self, credential_id: bytes
    ) -> WebAuthnCredential | None:
        """按 credential_id（bytes）查询 Passkey 凭据。"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(WebAuthnCredential).where(WebAuthnCredential.credential_id == credential_id)
            )
            return result.scalar_one_or_none()

    async def save_webauthn_credential(
        self,
        credential_id: bytes,
        public_key: bytes,
        sign_count: int,
        device_name: str,
    ) -> WebAuthnCredential:
        """保存新注册的 Passkey 凭据并返回。"""
        cred = WebAuthnCredential(
            credential_id=credential_id,
            public_key=public_key,
            sign_count=sign_count,
            device_name=device_name,
        )
        async with self._session_factory() as session:
            session.add(cred)
            await session.commit()
            await session.refresh(cred)
        return cred

    async def update_sign_count(self, credential_id: bytes, sign_count: int) -> None:
        """更新 Passkey 签名计数器及 last_used_at。"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(WebAuthnCredential).where(WebAuthnCredential.credential_id == credential_id)
            )
            cred = result.scalar_one_or_none()
            if cred is None:
                return
            cred.sign_count = sign_count
            cred.last_used_at = datetime.now(UTC)
            await session.commit()

    async def delete_webauthn_credential(self, credential_id_b64: str) -> None:
        """删除指定 Passkey 凭据。credential_id_b64 为 base64url 编码（无 padding）。

        内部 decode 为 bytes 后匹配 DB，不存在时抛出 AuthNotFoundError。
        """
        padded = (
            credential_id_b64 + "=" * (4 - len(credential_id_b64) % 4)
            if len(credential_id_b64) % 4 != 0
            else credential_id_b64
        )
        try:
            cred_bytes = base64.urlsafe_b64decode(padded)
        except Exception as exc:
            raise AuthNotFoundError("无效的 credential_id 编码") from exc

        async with self._session_factory() as session:
            result = await session.execute(
                select(WebAuthnCredential).where(WebAuthnCredential.credential_id == cred_bytes)
            )
            cred = result.scalar_one_or_none()
            if cred is None:
                raise AuthNotFoundError("Passkey 凭据不存在")
            await session.delete(cred)
            await session.commit()

    # ── TOTP ──

    async def verify_totp(self, code: str) -> bool:
        """验证 TOTP 码。未配置时抛出 TOTPNotConfiguredError。"""
        async with self._session_factory() as session:
            result = await session.execute(select(AdminCredential).limit(1))
            cred = result.scalar_one_or_none()
        if cred is None or cred.totp_secret is None:
            raise TOTPNotConfiguredError("TOTP 未绑定")
        totp = pyotp.TOTP(cred.totp_secret)
        return bool(totp.verify(code, valid_window=1))

    async def get_totp_setup_uri(self, session_id: str) -> tuple[str, str]:
        """生成新 TOTP secret，暂存 Redis（绑定 session_id），返回 (otpauth_uri, secret)。

        pending secret key: auth:totp_pending:{session_id}，TTL 10 分钟。
        绑定 session_id 防止多标签页并发覆盖。
        """
        secret = pyotp.random_base32()
        key = f"{_TOTP_PENDING_PREFIX}{session_id}"
        await self._cache.set(key, secret, ttl=_TOTP_PENDING_TTL)
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name="admin", issuer_name=self._settings.AUTH_RP_NAME)
        return uri, secret

    async def confirm_totp_setup(self, session_id: str, code: str) -> None:
        """验证 TOTP 码后将 pending secret 写入 DB。

        - pending secret 不存在 → 抛出 AuthNotFoundError（setup URI 已过期）
        - code 错误 → 抛出 InvalidTOTPCodeError
        """
        key = f"{_TOTP_PENDING_PREFIX}{session_id}"
        secret = await self._cache.get(key)
        if secret is None:
            raise AuthNotFoundError("TOTP 设置已过期，请重新获取二维码")
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            raise InvalidTOTPCodeError("TOTP 验证码错误")
        # 写入 DB
        async with self._session_factory() as session:
            result = await session.execute(select(AdminCredential).limit(1))
            cred = result.scalar_one_or_none()
            if cred is None:
                raise AuthNotFoundError("管理员凭据不存在")
            cred.totp_secret = secret
            await session.commit()
        # 清除 pending
        await self._cache.delete(key)
