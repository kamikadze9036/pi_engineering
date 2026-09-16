from app.catalog import BY_CODE, REFERENCE_U10_3045


def test_reference_template_uses_valid_unique_catalogue_slots():
    seen = set()
    for item in REFERENCE_U10_3045["parameters"]:
        definition = BY_CODE[item["definition_code"]]
        position = item["position_key"]
        assert (definition.code, position) not in seen
        seen.add((definition.code, position))
        if definition.positions:
            assert position in dict(definition.positions)
        else:
            assert position == ""
        if definition.value_type == "NUMERIC":
            assert item["numeric_target"] is not None
        elif definition.value_type == "TEXT":
            assert item["text_value"]
        else:
            assert item["boolean_value"] is not None

    assert len(seen) == 103
