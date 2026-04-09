from legacygym.server.tasks import dataset_path, load_rosetta_pairs


def test_load_rosetta_pairs_uses_utf8_and_pairs_languages():
    pairs = load_rosetta_pairs(dataset_path())

    assert "Array length" in pairs
    assert "Tokenize a string with escaping" in pairs
    assert "Word frequency" in pairs
    assert "identification division" in pairs["Array length"].cobol_code.lower()
    assert "print" in pairs["Array length"].python_code.lower()
