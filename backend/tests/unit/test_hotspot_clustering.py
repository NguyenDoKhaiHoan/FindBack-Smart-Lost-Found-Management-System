import pytest

from app.modules.hotspots.clustering import (
    center,
    cluster_labels,
    distance_meters,
    previous_cluster_members,
)
from app.modules.hotspots.schemas import AlgorithmConfig
from app.modules.hotspots.service import coordinate, density_level


def test_haversine_and_spherical_mean():
    assert distance_meters((0, 0), (0, 1)) == pytest.approx(111195, rel=1e-5)
    assert distance_meters((0, 179.999), (0, -179.999)) == pytest.approx(222.39, rel=1e-4)
    assert abs(center([(0, 179.999), (0, -179.999)], 2)[1]) == 180


def test_dbscan_groups_repeated_coordinates_and_noise():
    first = [(21, 105.8)] * 3 + [(21.001, 105.8)] * 2
    second = [(21.01, 105.81)] * 5
    points = first + second + [(21.03, 105.84)]
    labels = cluster_labels(points, 200, 5)
    assert len(set(labels[:5])) == len(set(labels[5:10])) == 1
    assert labels[0] != labels[5]
    assert labels[-1] == -1
    assert cluster_labels(first[:4], 200, 5) == [-1] * 4
    matches = previous_cluster_members(points, labels, [(21, 105.8), (21.04, 105.82)], 200)
    assert matches == {labels[0]: [0]}


@pytest.mark.parametrize("point", [(None, 105), (91, 105), (21, -181), (float("nan"), 105), (0, 0)])
def test_invalid_coordinates(point):
    assert coordinate(*point) is None


def test_density_levels_follow_thresholds():
    config = AlgorithmConfig()
    assert [density_level(count, config) for count in (9, 10, 19, 20, 34, 35)] == [
        "low",
        "medium",
        "medium",
        "high",
        "high",
        "very_high",
    ]
