from aioafero.v1.models import resource


def test_resource_type_unknown():
    assert resource.ResourceTypes("beans") == resource.ResourceTypes.UNKNOWN
