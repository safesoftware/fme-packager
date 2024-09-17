import xml
from pathlib import Path

import xmltodict


def _web_service_path(web_service_file_name: str) -> Path:
    return Path("web_services") / f"{web_service_file_name}"


def _parse_web_service(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as web_service:
            package_xml = xmltodict.parse(web_service.read())

        webservice_xml = (
            package_xml.get("ImportExportData", {}).get("webservices", {}).get("webservicexml", "")
        )
        webservice_content = xmltodict.parse(webservice_xml)
    except xml.parsers.expat.ExpatError:
        return {}

    return webservice_content


def _web_service_description(webservice_content: dict) -> str:
    return (
        webservice_content.get("webservice", {})
        .get("authentication", {})
        .get("markdown_description", "")
    )
