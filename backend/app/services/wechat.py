"""WeChat 网站应用 OAuth2 (QR login) client + helpers.

Real QR login uses the official endpoints. When credentials are absent the API
layer falls back to a mock login (non-production only); this module only covers
the real flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import Settings
from app.core.errors import AppError

_AUTHORIZE_ENDPOINT = "https://open.weixin.qq.com/connect/qrconnect"
_ACCESS_TOKEN_ENDPOINT = "https://api.weixin.qq.com/sns/oauth2/access_token"
_USERINFO_ENDPOINT = "https://api.weixin.qq.com/sns/userinfo"


class WechatOAuthError(AppError):
    status_code = 502
    code = "WECHAT_OAUTH_ERROR"
    default_message = "微信登录失败，请稍后重试。"


@dataclass(slots=True)
class WechatIdentity:
    openid: str
    unionid: str | None = None
    nickname: str | None = None


def wechat_configured(settings: Settings) -> bool:
    return bool(settings.wechat_app_id and settings.wechat_app_secret)


def build_authorize_url(settings: Settings, state: str) -> str:
    params = {
        "appid": settings.wechat_app_id,
        "redirect_uri": settings.wechat_redirect_uri,
        "response_type": "code",
        "scope": "snsapi_login",
        "state": state,
    }
    return f"{_AUTHORIZE_ENDPOINT}?{urlencode(params)}#wechat_redirect"


async def exchange_code(settings: Settings, code: str) -> WechatIdentity:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.get(
                _ACCESS_TOKEN_ENDPOINT,
                params={
                    "appid": settings.wechat_app_id,
                    "secret": settings.wechat_app_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_resp.json()
            if "errcode" in token_data or "access_token" not in token_data:
                raise WechatOAuthError(token_data.get("errmsg") or None)

            openid = token_data.get("openid")
            if not openid:
                raise WechatOAuthError()

            unionid = token_data.get("unionid")
            info_resp = await client.get(
                _USERINFO_ENDPOINT,
                params={
                    "access_token": token_data["access_token"],
                    "openid": openid,
                    "lang": "zh_CN",
                },
            )
            info = info_resp.json()
            return WechatIdentity(
                openid=openid,
                unionid=unionid or info.get("unionid"),
                nickname=info.get("nickname"),
            )
    except WechatOAuthError:
        raise
    except (httpx.HTTPError, ValueError) as exc:  # pragma: no cover - network path
        raise WechatOAuthError() from exc
