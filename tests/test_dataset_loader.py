from legacygym.server.tasks import (
    cobol_review_dataset_path,
    dataset_path,
    load_cobol_review_samples,
    load_rosetta_pairs,
)


def test_load_rosetta_pairs_uses_utf8_and_pairs_languages():
    pairs = load_rosetta_pairs(dataset_path())

    assert "Array length" in pairs
    assert "Tokenize a string with escaping" in pairs
    assert "Word frequency" in pairs
    assert "identification division" in pairs["Array length"].cobol_code.lower()
    assert "print" in pairs["Array length"].python_code.lower()


def test_load_cobol_review_samples_parses_file_fixtures():
    samples = load_cobol_review_samples(cobol_review_dataset_path())

    assert "task_func_02" in samples
    sample = samples["task_func_02"]
    assert sample.input_file_names == ["input.txt"]
    assert sample.output_file_names == ["output.txt"]
    assert "input.txt" in sample.inputs
    assert "output.txt" in sample.outputs
    assert "COBOL program" in sample.instruct_prompt
