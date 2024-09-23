import xml
from pathlib import Path

import xmltodict


def _web_service_path(web_service_file_name: str) -> Path:
    return Path("web_services") / f"{web_service_file_name}"


def _parse_web_service(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as web_service:
            package_xml = xmltodict.parse(web_service.read())

        webservice_data = package_xml.get("ImportExportData", {}).get("webservices", {})

        # 2024.1 and earlier
        webservice_xml = webservice_data.get("webservicexml", "")

        if not webservice_data.get("webservice") and webservice_xml:
            webservice_data = xmltodict.parse(webservice_xml)

        return webservice_data.get("webservice", {}).get("authentication", {})

    except (xml.parsers.expat.ExpatError, KeyError):
        return {}
