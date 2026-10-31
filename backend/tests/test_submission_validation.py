import io

import pytest
from PIL import Image, PngImagePlugin

from app.auth import AuthError
from app.image_processing import process_image
from app.project_schemas import FormDefinition, Label, ProjectDefinition, Question
from app.storage import LocalObjectStore
from app.submission_schemas import SubmissionRequest
from app.submissions import validate_answers


def definition(question=None):
    return ProjectDefinition(
        name="Synthetic",
        min_width=8,
        min_height=8,
        allowed_formats=["JPEG", "PNG", "WEBP"],
        labels=[Label(key="scene", name="Scene")],
        criteria=FormDefinition(questions=[question] if question else []),
    )


@pytest.mark.parametrize(
    "kind,value,rules",
    [
        ("single_choice", "A", {"options": ["A", "B"]}),
        ("multiple_choice", ["A", "B"], {"options": ["A", "B"], "min_selections": 1}),
        ("short_text", "abc", {"min_length": 2, "max_length": 5}),
        ("number", 0, {"min_value": 0, "max_value": 3, "integer_only": True}),
        ("yes_no", False, {}),
    ],
)
def test_valid_answers(kind, value, rules):
    d = definition(Question(key="q", title="Question", type=kind, required=True, **rules))
    validate_answers(d, "scene", {"q": value})


@pytest.mark.parametrize(
    "kind,value,rules",
    [
        ("single_choice", "unknown", {"options": ["A", "B"]}),
        ("multiple_choice", ["A", "A"], {"options": ["A", "B"]}),
        ("multiple_choice", ["Z"], {"options": ["A", "B"]}),
        ("multiple_choice", ["A"], {"options": ["A", "B"], "min_selections": 2}),
        ("short_text", " ", {}),
        ("short_text", "abc", {"max_length": 2}),
        ("number", True, {}),
        ("number", "3", {}),
        ("number", float("nan"), {}),
        ("number", float("inf"), {}),
        ("number", 10**1000, {}),
        ("number", 1.5, {"integer_only": True}),
        ("number", -1, {"min_value": 0}),
        ("yes_no", "yes", {}),
        ("yes_no", 1, {}),
    ],
)
def test_invalid_answers(kind, value, rules):
    with pytest.raises(AuthError):
        validate_answers(
            definition(Question(key="q", title="Question", type=kind, required=True, **rules)),
            "scene",
            {"q": value},
        )


def test_required_optional_unknown_and_label():
    d = definition(Question(key="q", title="Question", type="yes_no", required=True))
    for label, answers in [
        ("wrong", {"q": True}),
        ("scene", {}),
        ("scene", {"q": True, "extra": 1}),
    ]:
        with pytest.raises(AuthError):
            validate_answers(d, label, answers)
    validate_answers(definition(Question(key="q", title="Optional", type="number")), "scene", {})


@pytest.mark.parametrize("consent", [False, 1, "true", None])
def test_explicit_consent_only(consent):
    from uuid import uuid4

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SubmissionRequest(
            request_key=uuid4(),
            criteria_version=1,
            label_key="scene",
            consent=consent,
            privacy_acknowledgement=True,
        )


def image_bytes(fmt="PNG", color="red", size=(16, 16)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format=fmt)
    return out.getvalue()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_decodes_and_reencodes(fmt):
    result = process_image(image_bytes(fmt), definition())
    assert result.width == result.height == 16 and result.format == fmt
    with Image.open(io.BytesIO(result.data)) as image:
        image.load()
        assert not image.getexif() and not image.info.get("xmp")


def test_strips_metadata_and_orients_pixels():
    out = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "Synthetic private author"
    exif[34853] = {1: "N", 2: (1.0, 2.0, 3.0), 3: "E", 4: (4.0, 5.0, 6.0)}
    Image.new("RGB", (12, 20), "red").save(out, format="JPEG", exif=exif)
    result = process_image(out.getvalue(), definition())
    assert (result.width, result.height) == (20, 12)
    with Image.open(io.BytesIO(result.data)) as image:
        assert not image.getexif()
    meta = PngImagePlugin.PngInfo()
    meta.add_text("location", "Synthetic GPS text")
    out = io.BytesIO()
    Image.new("RGB", (16, 16)).save(out, format="PNG", pnginfo=meta)
    with Image.open(io.BytesIO(process_image(out.getvalue(), definition()).data)) as image:
        assert not image.info


@pytest.mark.parametrize(
    "data", [b"", b"not a photo", b"<svg></svg>", b"x" * (10 * 1024 * 1024 + 1)]
)
def test_unsupported_empty_and_oversized(data):
    with pytest.raises(AuthError):
        process_image(data, definition())


def test_limits_pixels_dimensions_formats_animation_and_truncation(monkeypatch):
    with pytest.raises(AuthError):
        process_image(image_bytes(size=(4, 4)), definition())
    d = definition()
    d.allowed_formats = ["JPEG"]
    with pytest.raises(AuthError):
        process_image(image_bytes(), d)
    with pytest.raises(AuthError):
        process_image(image_bytes("JPEG")[:100], definition())
    out = io.BytesIO()
    Image.new("RGB", (16, 16)).save(
        out,
        format="WEBP",
        save_all=True,
        append_images=[Image.new("RGB", (16, 16), "blue")],
        duration=100,
    )
    with pytest.raises(AuthError):
        process_image(out.getvalue(), definition())
    monkeypatch.setattr("app.image_processing.MAX_PIXELS", 100)
    with pytest.raises(AuthError):
        process_image(image_bytes(), definition())


def test_storage_rejects_paths_and_symlinks(tmp_path):
    store = LocalObjectStore(str(tmp_path))
    key = "objects/" + "a" * 32 + "/" + "b" * 32 + ".png"
    store.put(key, b"sanitized")
    assert store.read(key) == b"sanitized"
    for bad in [
        "../../etc/passwd",
        "/etc/passwd",
        "objects/a/b.png",
        "objects/" + "a" * 32 + "/../secret.png",
    ]:
        with pytest.raises(ValueError):
            store.read(bad)
    with pytest.raises(FileExistsError):
        store.put(key, b"overwrite")
    store.delete(key)
    assert not store.path(key).exists()
    store.path(key).parent.mkdir(parents=True, exist_ok=True)
    store.path(key).symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError):
        store.read(key)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_local_upload_storage_fails_closed_outside_development(environment):
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://synthetic@localhost/synthetic",
            environment=environment,
            uploads_enabled=True,
        )
