"""Tests for input validators."""
import pytest
from app.core.validators import (
    validate_ip,
    validate_ip_network,
    validate_interface,
    validate_chain_name,
    validate_protocol,
    validate_port,
    validate_fwmark,
    validate_comment,
    validate_day,
    validate_time,
    validate_address,
)


class TestValidateIP:
    def test_valid_ipv4(self):
        assert validate_ip("10.8.0.1") == "10.8.0.1"

    def test_valid_ipv4_with_mask(self):
        assert validate_ip("10.8.0.1/32") == "10.8.0.1/32"

    def test_invalid_ip(self):
        with pytest.raises(ValueError):
            validate_ip("not-an-ip")

    def test_injection_attempt(self):
        with pytest.raises(ValueError):
            validate_ip("10.8.0.1; rm -rf /")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            validate_ip("")


class TestValidateInterface:
    def test_valid_interface(self):
        assert validate_interface("wg0") == "wg0"
        assert validate_interface("eth0") == "eth0"
        assert validate_interface("wg-dest1") == "wg-dest1"

    def test_invalid_interface(self):
        with pytest.raises(ValueError):
            validate_interface("wg0; cat /etc/passwd")

    def test_too_long(self):
        with pytest.raises(ValueError):
            validate_interface("a" * 16)

    def test_special_chars(self):
        with pytest.raises(ValueError):
            validate_interface("wg0`id`")


class TestValidateChainName:
    def test_valid_chain(self):
        assert validate_chain_name("vpn_user_1") == "vpn_user_1"

    def test_invalid_chain(self):
        with pytest.raises(ValueError):
            validate_chain_name("chain; drop table")


class TestValidateProtocol:
    def test_valid_protocols(self):
        assert validate_protocol("tcp") == "tcp"
        assert validate_protocol("udp") == "udp"
        assert validate_protocol("icmp") == "icmp"
        assert validate_protocol("any") == "any"

    def test_case_insensitive(self):
        assert validate_protocol("TCP") == "tcp"

    def test_invalid_protocol(self):
        with pytest.raises(ValueError):
            validate_protocol("invalid")


class TestValidatePort:
    def test_valid_ports(self):
        assert validate_port(80) == 80
        assert validate_port(443) == 443
        assert validate_port(1) == 1
        assert validate_port(65535) == 65535

    def test_invalid_port_zero(self):
        with pytest.raises(ValueError):
            validate_port(0)

    def test_invalid_port_negative(self):
        with pytest.raises(ValueError):
            validate_port(-1)

    def test_invalid_port_too_high(self):
        with pytest.raises(ValueError):
            validate_port(65536)


class TestValidateFwmark:
    def test_valid_fwmark(self):
        assert validate_fwmark(100) == 100

    def test_invalid_fwmark(self):
        with pytest.raises(ValueError):
            validate_fwmark(-1)


class TestValidateComment:
    def test_valid_comment(self):
        assert validate_comment("vpn_sched_1") == "vpn_sched_1"
        assert validate_comment("user:1: ") == "user:1: "

    def test_injection_in_comment(self):
        with pytest.raises(ValueError):
            validate_comment('"; DROP TABLE users; --')


class TestValidateDay:
    def test_valid_days(self):
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            assert validate_day(day) == day

    def test_invalid_day(self):
        with pytest.raises(ValueError):
            validate_day("Monday")


class TestValidateTime:
    def test_valid_times(self):
        assert validate_time("00:00") == "00:00"
        assert validate_time("23:59") == "23:59"
        assert validate_time("12:30:45") == "12:30:45"

    def test_invalid_time(self):
        with pytest.raises(ValueError):
            validate_time("not-a-time")


class TestValidateAddress:
    def test_valid_ip(self):
        assert validate_address("8.8.8.8") == "8.8.8.8"

    def test_valid_cidr(self):
        assert validate_address("10.0.0.0/8") == "10.0.0.0/8"

    def test_invalid_address(self):
        with pytest.raises(ValueError):
            validate_address("not-valid")
