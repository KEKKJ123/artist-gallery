"""serve 启动提示与本机地址识别。"""

from __future__ import annotations

from artist_gallery.cli import serve_banner
from artist_gallery.netinfo import LanAddress, lan_addresses


class TestLanAddresses:
    def test_home_network_ranked_first(self) -> None:
        # 取自一台真实电脑：代理的虚拟网卡 + VPN + 真正的 Wi-Fi
        got = lan_addresses(["198.18.0.1", "26.135.196.115", "192.168.1.2"])
        assert got[0] == LanAddress("192.168.1.2", likely=True)

    def test_proxy_tun_range_is_marked_unlikely(self) -> None:
        got = {a.ip: a for a in lan_addresses(["198.18.0.1", "192.168.1.2"])}
        assert got["198.18.0.1"].likely is False
        assert got["192.168.1.2"].likely is True

    def test_other_private_ranges_are_likely(self) -> None:
        for ip in ("10.1.2.3", "172.20.0.5", "192.168.43.1"):  # 最后一个是手机热点常见地址
            assert lan_addresses([ip])[0].likely, ip

    def test_loopback_unspecified_linklocal_ipv6_and_garbage_dropped(self) -> None:
        assert (
            lan_addresses(["127.0.0.1", "0.0.0.0", "169.254.3.4", "::1", "fe80::1", "abc", ""])
            == []
        )

    def test_duplicates_collapsed(self) -> None:
        assert len(lan_addresses(["192.168.1.2", "192.168.1.2"])) == 1

    def test_system_lookup_never_raises(self) -> None:
        assert isinstance(lan_addresses(), list)


class TestServeBanner:
    def _text(self, host: str, found: list[LanAddress] | None = None) -> str:
        return "\n".join(serve_banner(host, 8765, found))

    def test_local_mode_mentions_how_to_open_to_phone(self) -> None:
        t = self._text("127.0.0.1")
        assert "http://localhost:8765" in t
        assert "--host 0.0.0.0" in t
        assert "没有登录保护" not in t

    def test_all_interfaces_shows_real_lan_ip_and_warns_about_0000(self) -> None:
        t = self._text(
            "0.0.0.0", [LanAddress("192.168.1.2", True), LanAddress("198.18.0.1", False)]
        )
        assert "http://192.168.1.2:8765" in t
        assert "http://localhost:8765" in t
        assert "不要在浏览器里输入 0.0.0.0" in t
        assert "没有登录保护" in t

    def test_never_suggests_0000_as_an_address(self) -> None:
        t = self._text("0.0.0.0", [LanAddress("192.168.1.2", True)])
        assert "http://0.0.0.0" not in t

    def test_unlikely_address_is_flagged_without_guessing_the_cause(self) -> None:
        t = self._text(
            "0.0.0.0", [LanAddress("192.168.1.2", True), LanAddress("198.18.0.1", False)]
        )
        line = next(x for x in t.splitlines() if "198.18.0.1" in x)
        assert "手机多半连不上" in line
        assert "代理" not in line  # 不武断地猜这是什么软件
        line = next(x for x in t.splitlines() if "192.168.1.2" in x)
        assert "连不上" not in line

    def test_only_virtual_addresses_falls_back_to_ipconfig_hint(self) -> None:
        t = self._text("0.0.0.0", [LanAddress("198.18.0.1", False)])
        assert "ipconfig" in t

    def test_no_addresses_found_still_gives_instructions(self) -> None:
        t = self._text("0.0.0.0", [])
        assert "ipconfig" in t and "http://<那个地址>:8765" in t

    def test_explicit_lan_ip_host_is_echoed(self) -> None:
        t = self._text("192.168.1.2")
        assert "http://192.168.1.2:8765" in t

    def test_ipv6_wildcard_treated_like_all_interfaces(self) -> None:
        assert "不要在浏览器里输入 0.0.0.0" in self._text("::", [LanAddress("192.168.1.2", True)])
