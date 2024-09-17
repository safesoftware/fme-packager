from pathlib import Path

import pytest

from fme_packager.web_service import _web_service_path, _parse_web_service, _web_service_description

CWD = Path(__file__).parent.resolve()


@pytest.fixture
def valid_web_service():
    return {
        "webservice": {
            "authentication": {
                "auth_type": "0",
                "connection_description": "<p>A basic connection description.</p>",
                "description": "<p>A simple web service</p>",
                "help_url": "<a href=https://example.com>my_alias</a>",
                "markdown_connection_description": "A basic connection description.",
                "markdown_description": "A simple web service",
                "service_name": "My Web Service",
                "type": "BASIC",
                "verify_ssl_certificate_default": "true",
                "version": "1",
            }
        }
    }


def test__web_service_path():
    assert _web_service_path("test_webservice.xml") == Path("web_services") / "test_webservice.xml"


def test__parse_web_service(valid_web_service):
    path = CWD / "fixtures" / "valid_package" / "web_services" / "My Web Service.xml"
    assert _parse_web_service(path) == valid_web_service


def test__parse_web_service_invalid():
    path = CWD / "fixtures" / "web_services" / "Invalid Web Service.xml"
    assert _parse_web_service(path) == {}


def test__web_service_description(valid_web_service):
    description = _web_service_description(valid_web_service)
    assert description == "A simple web service"
