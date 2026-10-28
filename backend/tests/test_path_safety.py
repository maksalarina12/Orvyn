import pytest

from backend.core.security import PathValidationError, sanitize_filename, validate_relative_path


def test_sanitize_filename_removes_traversal_and_spaces():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("my cool asset.PNG") == "mycoolasset.PNG"
    assert sanitize_filename("a/b\\c.jpg") == "bc.jpg"
    assert sanitize_filename("...") == "unnamed"
    assert sanitize_filename("") == "unnamed"


def test_validate_relative_path_rejects_escape():
    with pytest.raises(PathValidationError):
        validate_relative_path("assets/uploads/../../etc/passwd")
    with pytest.raises(PathValidationError):
        validate_relative_path("/etc/passwd")
    with pytest.raises(PathValidationError):
        validate_relative_path("assets/uploads/never-exists.png")


def test_validate_relative_path_allows_real_file(tmp_path):
    target = tmp_path / "assets"
    target.mkdir()
    real = target / "real.png"
    real.write_bytes(b"\x89PNG\r\n\x1a\n")
    resolved = validate_relative_path("assets/real.png", base=tmp_path)
    assert resolved == real
