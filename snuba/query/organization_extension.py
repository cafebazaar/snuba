from dataclasses import dataclass
from typing import Any, Mapping

from snuba.query.extensions import QueryExtension
from snuba.query.query_processor import QueryExtensionProcessor
from snuba.query.query import Query
from snuba.request.request_settings import RequestSettings


ORGANIZATION_EXTENSION_SCHEMA = {
    "type": "object",
    "properties": {
        "organization": {
            "type": "integer",
            "minimum": 1,
        },
    },
    "required": ["organization"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class OrganizationExtensionPayload:
    organization: int


class OrganizationExtensionProcessor(QueryExtensionProcessor[OrganizationExtensionPayload]):
    """
    Extension processor for datasets that require an organization ID to be given in the request.
    """

    def process_query(
            self,
            query: Query,
            extension_data: OrganizationExtensionPayload,
            request_settings: RequestSettings,
    ) -> None:
        organization_id = extension_data.organization
        query.add_conditions([("org_id", "=", organization_id)])


class OrganizationExtension(QueryExtension):
    def __init__(self) -> None:
        super().__init__(
            schema=ORGANIZATION_EXTENSION_SCHEMA,
            processor=OrganizationExtensionProcessor(),
        )

    def _parse_payload(cls, payload: Mapping[str, Any]) -> OrganizationExtensionPayload:
        return OrganizationExtensionPayload(
            organization=payload["organization"]
        )
