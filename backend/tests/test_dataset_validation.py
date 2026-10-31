import io
import uuid

import pytest
from PIL import Image, PngImagePlugin
from pydantic import ValidationError

from app.integrations.exports import ExportStore
from app.schemas.datasets import ExportConsentRequest, PublicationRequest
from app.services.dataset_exports import canonical_image, csv_cell


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_publication_requires_explicit_confirmation(value):
    with pytest.raises(ValidationError):
        PublicationRequest(criteria_version=1, distribution_authorised=value, privacy_reviewed=True)


@pytest.mark.parametrize(
    "alias", ["email@example.test", "https://example.test", "<script>", "x" * 81]
)
def test_attribution_never_falls_back_to_private_account(alias):
    with pytest.raises(ValidationError):
        ExportConsentRequest(
            publication_id=uuid.uuid4(), agree_public_distribution=True, public_attribution=alias
        )


def test_canonical_export_removes_all_metadata():
    stream = io.BytesIO()
    meta = PngImagePlugin.PngInfo()
    meta.add_text("GPS", "secret")
    meta.add_text("email", "secret")
    Image.new("RGB", (8, 8), "blue").save(stream, "PNG", pnginfo=meta)
    result = canonical_image(stream.getvalue())
    with Image.open(io.BytesIO(result)) as image:
        assert image.info == {} and not image.getexif()
    assert result == canonical_image(stream.getvalue())


@pytest.mark.parametrize("value", ["=SUM(1)", "+CMD", "-CMD", "@SUM", "  =CMD", "\t=CMD"])
def test_csv_formula_cells_are_safe(value):
    assert csv_cell(value).startswith("'")


@pytest.mark.parametrize(
    "key",
    [
        "../secret",
        "/etc/passwd",
        "archives/../secret.zip",
        "objects/abc",
        "archives/" + "a" * 32 + "/../../secret.zip",
    ],
)
def test_export_store_rejects_paths(tmp_path, key):
    with pytest.raises(ValueError):
        ExportStore(str(tmp_path)).open(key)


def test_export_store_rejects_symlink(tmp_path):
    store = ExportStore(str(tmp_path / "cache"))
    key = "archives/" + "a" * 32 + "/" + "b" * 32 + ".zip"
    path = store.path(key)
    path.parent.mkdir(parents=True)
    outside = tmp_path / "private.txt"
    outside.write_text("private")
    path.symlink_to(outside)
    with pytest.raises(ValueError):
        store.open(key)
    assert outside.read_text() == "private"
