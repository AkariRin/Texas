"""鉴权 API Pydantic Schemas。"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── 请求 Schemas ──


class TokenLoginRequest(BaseModel):
    """静态令牌登录请求。"""

    token: str = Field(..., min_length=1, description="管理员静态令牌")


class TOTPVerifyRequest(BaseModel):
    """TOTP 登录请求。"""

    code: str = Field(
        ..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6 位 TOTP 码"
    )


class TOTPSetupConfirmRequest(BaseModel):
    """TOTP 绑定确认请求。"""

    code: str = Field(
        ..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6 位 TOTP 验证码"
    )


class WebAuthnLoginFinishRequest(BaseModel):
    """WebAuthn 登录完成请求。"""

    challenge_id: str = Field(..., description="begin 阶段返回的 challenge_id")
    credential: dict = Field(  # type: ignore[type-arg]
        ..., description="浏览器 navigator.credentials.get() 返回的凭据 JSON"
    )


class WebAuthnRegisterFinishRequest(BaseModel):
    """WebAuthn 注册完成请求。"""

    challenge_id: str = Field(..., description="begin 阶段返回的 challenge_id")
    credential: dict = Field(  # type: ignore[type-arg]
        ..., description="浏览器 navigator.credentials.create() 返回的凭据 JSON"
    )
    device_name: str = Field(default="我的设备", max_length=64, description="设备名称")


# ── 响应 Schemas ──


class SessionInfoResponse(BaseModel):
    """当前 Session 信息响应。"""

    auth_method: str
    created_at: str
    expires_at: str


class TOTPSetupResponse(BaseModel):
    """TOTP 设置响应。"""

    otpauth_uri: str = Field(..., description="otpauth:// URI，前端渲染为二维码")
    secret: str = Field(..., description="TOTP secret（供手动输入）")


class WebAuthnBeginResponse(BaseModel):
    """WebAuthn begin 响应（登录/注册通用字段）。"""

    challenge_id: str
    challenge_b64: str
    rp_id: str
    rp_name: str


class WebAuthnCredentialInfo(BaseModel):
    """Passkey 凭据信息（列表展示用）。"""

    credential_id_b64: str
    device_name: str
    created_at: str
    last_used_at: str
