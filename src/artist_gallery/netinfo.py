"""本机网络地址：给 `serve` 在局域网模式下提示"手机该访问哪个地址"。

只用标准库（Android / Termux 上也能跑），出任何问题都返回空列表，绝不影响服务启动。
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass

# 常见的家用路由器网段：手机和电脑连同一个 Wi-Fi 时，地址几乎一定在这些范围里。
_HOME_NETS = tuple(
    ipaddress.ip_network(n) for n in ("192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12")
)
# 代理 / 虚拟网卡常用的段：地址是"本机内部"的，手机连不上。
# 198.18.0.0/15 是 RFC 2544 的测试网段，Clash / Mihomo 的 TUN 模式常用它；
# 100.64.0.0/10 是运营商级 NAT / Tailscale。
_VIRTUAL_NETS = tuple(ipaddress.ip_network(n) for n in ("198.18.0.0/15", "100.64.0.0/10"))


@dataclass(frozen=True)
class LanAddress:
    ip: str
    likely: bool  # True = 很可能是手机能连上的那个（家用网段）


def _classify(ip: str) -> LanAddress | None:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if addr.version != 4 or addr.is_loopback or addr.is_unspecified or addr.is_link_local:
        return None
    if any(addr in n for n in _VIRTUAL_NETS):
        return LanAddress(ip, likely=False)
    return LanAddress(ip, likely=any(addr in n for n in _HOME_NETS))


def lan_addresses(candidates: list[str] | None = None) -> list[LanAddress]:
    """本机的 IPv4 地址，"很可能是局域网"的排在前面。

    candidates 只用于测试；正常调用时从系统取。
    """
    if candidates is None:
        try:
            infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
            candidates = [str(i[4][0]) for i in infos]
        except OSError:
            candidates = []
    seen: dict[str, LanAddress] = {}
    for ip in candidates:
        la = _classify(ip)
        if la and la.ip not in seen:
            seen[la.ip] = la
    return sorted(seen.values(), key=lambda a: (not a.likely, a.ip))
