"""Bounded full-dimensional convex halfspaces; no physical-model inference."""

import math


def convex_halfspace_geometry(normals: list, offsets: list) -> dict:
    """Intersect supplied closed halfspaces normal[i] dot x <= offset[i].

    Supply 3..512 planes in 2D or 4..512 in 3D. Components must be finite real
    numbers, excluding booleans/strings, with absolute value <=1e12. Each normal
    must be nonzero. Every row and offset is divided by the positive normal norm;
    units of coordinates are whatever makes the supplied inequalities consistent.
    No implicit symmetry completion, missing-plane inference, physical Wulff
    assumptions, unit conversion, or random numerical perturbation is performed.

    The intersection must be feasible, bounded and numerically full dimensional.
    Coordinate LP bounds and a positive Chebyshev interior radius certify these
    preconditions. Coordinates are internally scaled by max(abs(normalized
    offsets)). Geometry thinner than 1e-8 of the scaled bounding-box size is
    rejected as numerically unresolved. Qhull is called without joggle options.
    Residual tolerance is 1e-8 times max(1,scaled bounding-box span). Coincident
    normalized constraints within 1e-10 are coalesced: a facet lists ALL original
    constraint indices, and its measure is counted only once. Redundant planes
    have no facet. Near-degenerate geometry may explicitly fail rather than be
    perturbed. Returned vertices/facet ordering is a numerical implementation
    detail, not a correspondence guarantee across differently ordered inputs.
    """
    import numpy as np
    from scipy.optimize import linprog
    from scipy.spatial import ConvexHull, HalfspaceIntersection, QhullError
    from threadpoolctl import threadpool_limits

    if not isinstance(normals, list) or not 3 <= len(normals) <= 512:
        raise ValueError("normals must contain 3..512 rows")
    if not isinstance(normals[0], list) or len(normals[0]) not in (2, 3):
        raise ValueError("each normal must be a 2D or 3D vector")
    dimension = len(normals[0])
    if len(normals) < dimension + 1:
        raise ValueError("at least dimension+1 halfspaces are required")
    if not isinstance(offsets, list) or len(offsets) != len(normals):
        raise ValueError("offsets must match the number of normals")
    rows, bounds = [], []
    for row, offset in zip(normals, offsets):
        if not isinstance(row, list) or len(row) != dimension:
            raise ValueError("normal rows must have equal dimension 2 or 3")
        for number in row + [offset]:
            if type(number) not in (int, float):
                raise ValueError("components must be real numbers, not bool/string/null")
            try:
                valid = math.isfinite(number) and abs(number) <= 1e12
            except (OverflowError, TypeError):
                valid = False
            if not valid:
                raise ValueError("components must be finite with absolute value <=1e12")
        length = math.hypot(*row)
        if length == 0:
            raise ValueError("zero normals are invalid")
        normalized_offset = offset / length
        if not math.isfinite(normalized_offset) or abs(normalized_offset) > 1e12:
            raise ValueError("normalized offsets must be finite and bounded by 1e12")
        rows.append([number / length for number in row])
        bounds.append(normalized_offset)
    scale = max(abs(v) for v in bounds)
    if scale == 0:
        raise ValueError("homogeneous halfspaces cannot form a bounded full-dimensional body")
    matrix = np.asarray(rows, dtype=float)
    rhs = np.asarray(bounds, dtype=float) / scale
    options = {"time_limit": 5.0, "maxiter": 10000,
               "primal_feasibility_tolerance": 1e-9,
               "dual_feasibility_tolerance": 1e-9}

    def solve(objective, a=matrix, b=rhs, var_bounds=None):
        result = linprog(objective, A_ub=a, b_ub=b,
                         bounds=var_bounds or [(None, None)] * dimension,
                         method="highs", options=options)
        if result.status == 2:
            raise ValueError("halfspace intersection is infeasible")
        if result.status == 3:
            raise ValueError("halfspace intersection is unbounded")
        if not result.success or not np.all(np.isfinite(result.x)):
            raise ValueError("bounded LP certificate could not be established")
        return result

    with threadpool_limits(limits=1):
        coordinate_bounds = []
        for axis in range(dimension):
            e = np.zeros(dimension); e[axis] = 1
            low = solve(e).x[axis]; high = solve(-e).x[axis]
            coordinate_bounds.append([float(low), float(high)])
        span = max(hi - lo for lo, hi in coordinate_bounds)
        if not math.isfinite(span) or span > 1e8:
            raise ValueError("scaled coordinate bounds exceed the numerical work domain")
        tolerance = 1e-8 * max(1.0, span)
        cheb = solve([0.0] * dimension + [-1.0],
                     np.column_stack([matrix, np.ones(len(matrix))]), rhs,
                     [(None, None)] * dimension + [(0, None)])
        center, radius = cheb.x[:dimension], float(cheb.x[-1])
        if radius <= tolerance:
            raise ValueError("intersection is lower dimensional or numerically unresolved")
        # One representative for a coincident plane; redundant noncoincident
        # planes remain, and are subsequently identified by zero facet measure.
        groups = []
        for index, (row, bound) in enumerate(zip(matrix, rhs)):
            matching = next((g for g in groups if
                             np.max(np.abs(matrix[g[0]] - row)) <= 1e-10 and
                             abs(rhs[g[0]] - bound) <= 1e-10), None)
            if matching is None:
                groups.append([index])
            else:
                matching.append(index)
        representatives = [g[0] for g in groups]
        try:
            halfspaces = np.column_stack([matrix[representatives], -rhs[representatives]])
            vertices = HalfspaceIntersection(halfspaces, center).intersections
            if len(vertices) > 10000 or not np.all(np.isfinite(vertices)):
                raise ValueError("invalid or excessive vertex output")
            hull = ConvexHull(vertices)
        except QhullError as error:
            raise ValueError("halfspace geometry is numerically unresolved; no perturbation applied") from error
        if np.max(matrix @ vertices.T - rhs[:, None]) > tolerance:
            raise ValueError("computed vertices violate halfspace residual tolerance")
        vertices = vertices[hull.vertices] if dimension == 2 else vertices
        facets = []
        active = set()
        for group in groups:
            index = group[0]; normal = matrix[index]
            indices = np.where(np.abs(vertices @ normal - rhs[index]) <= tolerance)[0]
            if len(indices) < dimension:
                continue
            points = vertices[indices]
            if dimension == 2:
                tangent = np.array([-normal[1], normal[0]])
                projections = points @ tangent
                order = np.argsort(projections)
                ordered = indices[order]
                measure = float(projections[order[-1]] - projections[order[0]])
                ordered = [int(ordered[0]), int(ordered[-1])]
            else:
                reference = np.eye(3)[int(np.argmin(np.abs(normal)))]
                u = np.cross(normal, reference); u /= np.linalg.norm(u)
                v = np.cross(normal, u)
                centroid = np.mean(points, axis=0)
                angles = np.arctan2((points-centroid) @ v, (points-centroid) @ u)
                ordered = indices[np.argsort(angles)]
                p = vertices[ordered]
                measure = float(abs(np.sum(np.cross(p, np.roll(p, -1, axis=0)) @ normal)) / 2)
                ordered = [int(x) for x in ordered]
            if measure <= tolerance ** (dimension - 1):
                continue
            active.update(group)
            facets.append({"constraint_indices": group,
                           "normal": normal.tolist(), "offset": bounds[index],
                           "vertex_indices": ordered,
                           "measure": measure * scale ** (dimension - 1)})
        boundary = float(hull.area) * scale ** (dimension - 1)
        if abs(sum(f["measure"] for f in facets)-boundary) > 1e-6 * max(boundary, 1e-30):
            raise ValueError("facet attribution is numerically ambiguous")
        measure = float(hull.volume) * scale ** dimension
        if min(measure, boundary, radius * scale, tolerance * scale) <= 0:
            raise ValueError("geometry underflowed; rescale input coordinates explicitly")
        result = {"dimension": dimension,
                  "vertices": (vertices * scale).tolist(),
                  "measure": measure, "boundary_measure": boundary,
                  "facets": facets,
                  "active_constraint_indices": sorted(active),
                  "inactive_constraint_indices": [i for i in range(len(rows)) if i not in active],
                  "normalized_normals": rows, "normalized_offsets": bounds,
                  "coordinate_bounds": [[lo*scale, hi*scale] for lo,hi in coordinate_bounds],
                  "interior_point": (center*scale).tolist(),
                  "interior_radius": radius*scale,
                  "coordinate_scale": scale, "residual_tolerance": tolerance*scale,
                  "method": "normalized halfspaces; bounded coordinate and Chebyshev LP certificates; unperturbed Qhull intersection and hull",
                  "scope": "Geometry of supplied inequalities only. Measures are area/perimeter in 2D and volume/surface area in 3D; no unit or physical-model inference. Facets with coincident constraints are counted once."}
        def finite_tree(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("geometry overflowed; no partial result returned")
            if isinstance(value, list):
                for item in value: finite_tree(item)
            if isinstance(value, dict):
                for item in value.values(): finite_tree(item)
        finite_tree(result)
        return result
