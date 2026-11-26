from collections import defaultdict
from math import asin, cos, radians, sin, sqrt

import numpy as np

EARTH_METERS = 6_371_008.8
Coordinate = tuple[float, float]


def distance_meters(first: Coordinate, second: Coordinate) -> float:
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_METERS * asin(sqrt(min(1, a)))


def cluster_labels(points: list[Coordinate], eps: int, minimum: int) -> list[int]:
    if len(points) < minimum:
        return [-1] * len(points)
    from sklearn.cluster import DBSCAN

    # Compress equal pins to keep repeated reports from creating a dense neighbor matrix.
    unique, inverse, counts = np.unique(points, axis=0, return_inverse=True, return_counts=True)
    fitted = DBSCAN(
        eps=eps / EARTH_METERS,
        min_samples=minimum,
        algorithm="ball_tree",
        metric="haversine",
        n_jobs=1,
    ).fit(np.radians(unique), sample_weight=counts)
    return fitted.labels_[inverse.reshape(-1)].tolist()


def previous_cluster_members(
    current: list[Coordinate], labels: list[int], previous: list[Coordinate], eps: int
) -> dict[int, list[int]]:
    if not current or not previous:
        return {}
    from sklearn.neighbors import BallTree

    valid = [(point, label) for point, label in zip(current, labels, strict=True) if label != -1]
    if not valid:
        return {}
    points, cluster_ids = zip(*valid, strict=True)
    tree = BallTree(np.radians(points), metric="haversine")
    distances, indices = tree.query(np.radians(previous), k=1)
    grouped = defaultdict(list)
    for index, (distance, nearest) in enumerate(zip(distances[:, 0], indices[:, 0], strict=True)):
        if distance * EARTH_METERS <= eps:
            grouped[cluster_ids[nearest]].append(index)
    return dict(grouped)


def center(points: list[Coordinate], precision: int) -> Coordinate:
    # Use a spherical mean so clusters across the date line stay near the date line.
    latitudes, longitudes = np.radians(points).T
    x = np.mean(np.cos(latitudes) * np.cos(longitudes))
    y = np.mean(np.cos(latitudes) * np.sin(longitudes))
    z = np.mean(np.sin(latitudes))
    return (
        round(float(np.degrees(np.arctan2(z, np.hypot(x, y)))), precision),
        round(float(np.degrees(np.arctan2(y, x))), precision),
    )
