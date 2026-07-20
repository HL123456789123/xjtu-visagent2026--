"""Legacy product APIs are intentionally no longer registered."""

import pytest


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/training/tasks"),
        ("post", "/api/training/tasks"),
        ("get", "/api/detection/tasks"),
        ("get", "/api/datasets"),
        ("get", "/api/models"),
        ("get", "/api/camera/status"),
        ("get", "/api/admin/roles"),
    ],
)
def test_legacy_training_detection_and_role_apis_return_404(db, client, method, path):
    del db
    response = getattr(client, method)(path)

    assert response.status_code == 404
