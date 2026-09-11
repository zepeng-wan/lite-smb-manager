"""Windows error normalization with localized user-facing guidance."""

from __future__ import annotations

from lite_smb_manager.application.ports import ApplicationError

ERROR_MESSAGES: dict[int, str] = {
    53: "找不到网络路径。请检查服务器地址、网络连接和 VPN 状态。",
    64: "网络名称不再可用。请检查服务器是否在线后重试。",
    67: "找不到指定的共享名。请确认 SMB 地址中的共享名称。",
    85: "目标盘符已被使用。请选择空闲盘符，或先确认该映射是否属于此配置。",
    86: "密码错误。请重新输入密码后重试。",
    87: "Windows 拒绝了请求参数。请检查 SMB 地址、盘符和用户名格式。",
    1219: (
        "Windows 已使用另一组凭据连接到该服务器。请统一账号或检查现有网络连接；"
        "应用不会自动断开其他连接。"
    ),
    1326: "用户名或密码不正确。请核对账号、域和密码。",
    2250: "指定的网络连接不存在，可能已被其他程序断开。",
}


def user_error_for_code(code: int) -> ApplicationError:
    """Map documented MPR error codes without leaking lower-level details."""
    return ApplicationError(
        ERROR_MESSAGES.get(code, f"SMB 操作失败（Windows 错误码 {code}）。请查看诊断日志。"),
        code=code,
    )
