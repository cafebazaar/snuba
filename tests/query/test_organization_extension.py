import pytest
from jsonschema.exceptions import ValidationError

from snuba.query.organization_extension import OrganizationExtension
from snuba.query.query import Query
from snuba.request.request_settings import RequestSettings
from snuba.schemas import validate_jsonschema


def test_organization_extension_query_processing_happy_path():
    extension = OrganizationExtension()
    raw_data = {"organization": 2}

    query = Query({
        "conditions": []
    })
    request_settings = RequestSettings(turbo=False, consistent=False, debug=False)

    extension.validate(raw_data).process_query(query, request_settings)

    assert query.get_conditions() == [("org_id", "=", 2)]


def test_invalid_data_does_not_validate():
    extension = OrganizationExtension()

    with pytest.raises(ValidationError):
        validate_jsonschema({"organization": "2"}, extension.get_schema())

    with pytest.raises(ValidationError):
        validate_jsonschema({"organization": 0}, extension.get_schema())

    with pytest.raises(ValidationError):
        validate_jsonschema({"organization": [2]}, extension.get_schema())
