from pathlib import Path

import pytest

from fme_packager.web_service import _web_service_path, _parse_web_service

CWD = Path(__file__).parent.resolve()


@pytest.fixture
def valid_web_service():
    def web_service(service_name):
        return {
            "auth_type": "0",
            "connection_description": "<p>A basic connection description.</p>",
            "description": "<p>A simple web service</p>",
            "help_url": "<a href=https://example.com>my_alias</a>",
            "markdown_connection_description": "A basic connection description.",
            "markdown_description": "A simple web service",
            "service_name": service_name,
            "type": "BASIC",
            "verify_ssl_certificate_default": "true",
            "version": "1",
        }

    return web_service


def test__web_service_path():
    assert _web_service_path("test_webservice.xml") == Path("web_services") / "test_webservice.xml"


@pytest.mark.parametrize(
    "path, service_name",
    [
        (
            CWD / "fixtures" / "valid_package" / "web_services" / "My Web Service.xml",
            "My Web Service",
        ),
        (CWD / "fixtures" / "web_services" / "2024 Web Service.xml", "2024 Web Service"),
    ],
)
def test__parse_web_service(path, service_name, valid_web_service):
    assert _parse_web_service(path) == valid_web_service(service_name)


def test__parse_web_service_invalid():
    path = CWD / "fixtures" / "web_services" / "Invalid Web Service.xml"
    assert _parse_web_service(path) == {}
