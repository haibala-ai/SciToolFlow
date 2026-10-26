"""Bounded proper-rigid shape dissimilarities for already corresponding points."""

import math


def rigid_superposition(coordinate_sets: list, set_ids: list, return_transforms: bool = False, return_aligned_coordinates: bool = False) -> dict:
    """Return pairwise minimum equal-point-weight RMSD after translation and SO(3) rotation.

    Every set must contain the same 3..256 corresponding finite 3D points in the
    same order and physical length units. Input contains 2..20 sets and at most
    10000 total scalar coordinates. Strings, bool, null and implicit point/shape
    broadcasts are rejected. IDs are distinct nonempty strings, retained in order.

    Each centered set must have its second singular value strictly greater than
    1e-12 times its largest: collinear, coincident and numerically near-collinear
    sets fail instead of receiving an unstable arbitrary orientation. Planar but
    noncollinear sets remain valid. Input correspondence is never inferred or
    repaired; mirrors, permutations, units and scale are not normalized away.

    Kabsch fits use equal per-point weights, translation and proper rotations
    only. Internal scalar normalization protects covariance formation; it is
    removed from the resulting RMSD and is not scientific shape rescaling.
    Output uses float64, exact copied symmetry and exact diagonal zeros. All
    intermediate centering and final RMSDs must be finite; flagged floating-point
    underflow fails rather than silently collapsing nonzero geometry to zero. No representative,
    clusters, confidence interval or physical/biological conclusion is selected.
    """
    import numpy as np
    from threadpoolctl import threadpool_limits

    if (
        not isinstance(coordinate_sets, list)
        or not 2 <= len(coordinate_sets) <= 20
        or not isinstance(set_ids, list)
        or len(set_ids) != len(coordinate_sets)
        or any(not isinstance(s, str) or not s or len(s) > 200 for s in set_ids)
        or len(set(set_ids)) != len(set_ids)
    ):
        raise ValueError(
            "Require 2..20 coordinate sets with distinct nonempty string IDs (<=200 characters)"
        )
    if (
        not isinstance(coordinate_sets[0], list)
        or not 3 <= len(coordinate_sets[0]) <= 256
    ):
        raise ValueError("Every coordinate set must have 3..256 matching 3D points")
    point_count = len(coordinate_sets[0])
    if len(coordinate_sets) * point_count * 3 > 10000:
        raise ValueError("Coordinate sets exceed 10000 total scalar coordinates")
    for coords in coordinate_sets:
        if not isinstance(coords, list) or len(coords) != point_count:
            raise ValueError(
                "Every coordinate set must have exactly the same point count"
            )
        for point in coords:
            if not isinstance(point, list) or len(point) != 3:
                raise ValueError(
                    "Every point must be a 3D list; no ragged or nested shape"
                )
            for value in point:
                if type(value) not in (int, float):
                    raise ValueError(
                        "Coordinates must be finite real numbers excluding bool and strings"
                    )
                try:
                    finite = math.isfinite(value)
                except OverflowError as error:
                    raise ValueError(
                        "Coordinate cannot be represented in finite float64"
                    ) from error
                if not finite:
                    raise ValueError("Coordinates must be finite")
    if type(return_transforms) is not bool or type(return_aligned_coordinates) is not bool:
        raise ValueError("Return flags must be strict Booleans")
    normalized, scales, centers = [], [], []
    pair_fits = []
    with (
        threadpool_limits(limits=1),
        np.errstate(over="raise", invalid="raise", divide="raise", under="raise"),
    ):
        try:
            for coords in coordinate_sets:
                a = np.asarray(coords, dtype=float)
                # Dividing first avoids overflow from summing equal very large coordinates.
                center = np.sum(a / point_count, axis=0)
                centered = a - center
                if not np.all(np.isfinite(centered)):
                    raise ValueError("Nonfinite centered coordinates")
                scale = float(np.max(np.abs(centered)))
                if scale == 0:
                    raise ValueError("Coincident point set is degenerate")
                normalized_set = centered / scale
                normalized.append(normalized_set)
                scales.append(scale)
                centers.append(center)
            count = len(normalized)
            singular = np.linalg.svd(np.stack(normalized), compute_uv=False)
            if np.any(singular[:, 1] <= 1e-12 * singular[:, 0]):
                raise ValueError("Collinear or numerically near-collinear point set")
            distances = np.zeros((count, count), dtype=float)
            pairs = [(i, j) for i in range(count) for j in range(i + 1, count)]
            covariances = np.stack([normalized[j].T @ normalized[i] for i, j in pairs])
            us, _, vts = np.linalg.svd(covariances)
            corrections = np.broadcast_to(np.eye(3), (len(pairs), 3, 3)).copy()
            determinants = np.linalg.det(us @ vts)
            corrections[:, -1, -1] = np.where(determinants >= 0, 1.0, -1.0)
            rotations = us @ corrections @ vts
            for pair_index, (i, j) in enumerate(pairs):
                rotation = rotations[pair_index]
                common_scale = max(scales[i], scales[j])
                delta = normalized[i] * (scales[i] / common_scale) - (
                    normalized[j] @ rotation
                ) * (scales[j] / common_scale)
                distance = float(
                    np.sqrt(np.mean(np.sum(delta * delta, axis=1))) * common_scale
                )
                if not math.isfinite(distance):
                    raise ValueError(
                        "Fitted RMSD is not representable as finite float64"
                    )
                distances[i, j] = distances[j, i] = distance
                pair = dict(reference_id=set_ids[i], mobile_id=set_ids[j], rmsd=distance)
                if return_transforms:
                    translation = centers[i] - centers[j] @ rotation
                    if not np.all(np.isfinite(translation)):
                        raise ValueError("Translation is not representable in finite float64")
                    pair.update(rotation=rotation.tolist(), translation=translation.tolist(), determinant=float(np.linalg.det(rotation)))
                if return_aligned_coordinates:
                    fitted = (normalized[j] @ rotation) * scales[j] + centers[i]
                    residuals = np.sqrt(np.sum(delta * delta, axis=1)) * common_scale
                    if not np.all(np.isfinite(fitted)) or not np.all(np.isfinite(residuals)):
                        raise ValueError("Aligned coordinates are not finite")
                    pair.update(aligned_mobile_coordinates=fitted.tolist(), residual_distances=residuals.tolist())
                pair_fits.append(pair)
        except (FloatingPointError, np.linalg.LinAlgError, OverflowError) as error:
            raise ValueError(
                "Coordinate centering or proper-rigid fitting overflows, underflows or is numerically unrepresentable"
            ) from error
    return {
        "set_ids": list(set_ids),
        "rmsd_matrix": distances.tolist(),
        "pair_fits": pair_fits,
        "transform_convention": "row vectors: mobile @ rotation + translation; stable centered coordinates used for fitted output",
        "set_count": count,
        "point_count": point_count,
        "pair_count": count * (count - 1) // 2,
        "fit_convention": "Minimum equal-point-weight RMSD after centering and proper SO(3) rotation; no reflection, scale fit, point rematching or point omission",
        "numeric_protocol": "Float64; 1 CPU thread; noncollinearity requires second centered singular value >1e-12 times first; copied exact symmetry and zero diagonal; length units inherited unchanged",
        "scope": "Already corresponding complete points only; caller supplies scientifically meaningful identity and units. No representative selection, ensemble probabilities, uncertainty inference or physical interpretation",
    }


def pairwise_superposition_rmsd(coordinate_sets: list, set_ids: list) -> dict:
    """Internal compatibility adapter; public catalogue uses RigidSuperposition."""
    return rigid_superposition(coordinate_sets, set_ids)
