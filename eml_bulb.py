"""
eml_bulb.py — EML-Bulb 3D fractal renderer

Mandelbulb-like fractal replacing the classical radial power r^p with:
    rho = exp(r) - ln(1 + r)

Iteration (per voxel c = (cx, cy, cz), starting from v = (0, 0, 0)):
    r     = |v|
    rho   = exp(r) - ln(1 + r)
    theta = arccos(vz / r)   [0 at origin]
    phi   = atan2(vy, vx)    [0 at origin]
    v'    = rho * spherical(p*theta, p*phi) + c

The fixed point of this map is c = (0, 0, -1):
    v0 = (0,0,0)  →  v1 = (0, 0, 1) + (0,0,-1) = (0,0,0)  ✓
So the bounded region is centred near c = (0, 0, -1), not the origin.

Pipeline:
    compute_field → extract_mesh → export_obj + preview_3d + show_slices

Usage:
    python eml_bulb.py [--res 96] [--power 8] [--max-iter 32]
                       [--escape 8.0] [--iso 0.95] [--bounds 1.5]
                       [--cx 0] [--cy 0] [--cz -1]
                       [--no-slices] [--no-export]
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

_EML_CMAP = LinearSegmentedColormap.from_list(
    "eml_lsd",
    ["#000011", "#0033ff", "#00ccff", "#00ff99", "#aaff00"],
    N=256,
)


# ── scalar field ───────────────────────────────────────────────────────────────

def compute_field(
    resolution: int = 96,
    bounds: float = 1.5,
    center: tuple = (0.0, 0.0, -1.0),
    power: int = 8,
    max_iter: int = 32,
    escape_radius: float = 8.0,
) -> np.ndarray:
    """
    Compute the EML-Bulb scalar field on a (resolution)^3 voxel grid.

    The grid covers [center[i]-bounds, center[i]+bounds] on each axis.
    Default center=(0,0,-1) places the grid over the fractal's fixed point.

    Returns float32 array of shape (resolution, resolution, resolution).
    Value 1.0 = orbit bounded (inside the set).
    Value n/max_iter = orbit escaped at iteration n.
    """
    cx0, cy0, cz0 = center
    xs = np.linspace(cx0 - bounds, cx0 + bounds, resolution, dtype=np.float64)
    ys = np.linspace(cy0 - bounds, cy0 + bounds, resolution, dtype=np.float64)
    zs = np.linspace(cz0 - bounds, cz0 + bounds, resolution, dtype=np.float64)
    CX, CY, CZ = np.meshgrid(xs, ys, zs, indexing="ij")

    VX = np.zeros_like(CX)
    VY = np.zeros_like(CY)
    VZ = np.zeros_like(CZ)

    n_total = resolution ** 3
    field = np.ones((resolution, resolution, resolution), dtype=np.float32)
    active = np.ones((resolution, resolution, resolution), dtype=bool)

    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for n in range(max_iter):
            n_active = int(active.sum())
            if n_active == 0:
                break
            print(f"  iter {n+1:3d}/{max_iter}  active={n_active:,}/{n_total:,}", end="\r", flush=True)

            vx = VX[active]
            vy = VY[active]
            vz = VZ[active]

            r = np.sqrt(vx**2 + vy**2 + vz**2)
            near_origin = r < 1e-14

            # EML radial transform: rho = exp(r) - ln(1+r)
            # rho(0) = 1  (non-zero — different from classical Mandelbulb)
            rho = np.exp(r) - np.log1p(r)

            # Spherical angles — defined as 0 at the origin (as per spec)
            safe_r = np.where(near_origin, 1.0, r)
            theta = np.where(near_origin, 0.0, np.arccos(np.clip(vz / safe_r, -1.0, 1.0)))
            phi   = np.where(near_origin, 0.0, np.arctan2(vy, vx))

            # Angular multiplication by power p
            tp = power * theta
            pp = power * phi
            sin_tp = np.sin(tp)

            # Back to Cartesian + add parameter c
            new_vx = rho * sin_tp * np.cos(pp) + CX[active]
            new_vy = rho * sin_tp * np.sin(pp) + CY[active]
            new_vz = rho * np.cos(tp)           + CZ[active]

            VX[active] = new_vx
            VY[active] = new_vy
            VZ[active] = new_vz

            # Escape: large radius or non-finite (overflow → inf / nan)
            new_r2 = new_vx**2 + new_vy**2 + new_vz**2
            escaped_local = (new_r2 > escape_radius**2) | ~np.isfinite(new_r2)

            if escaped_local.any():
                newly_escaped = np.zeros((resolution, resolution, resolution), dtype=bool)
                newly_escaped[active] = escaped_local
                field[newly_escaped] = float(n) / max_iter
                active &= ~newly_escaped

    inside = int((field == 1.0).sum())
    fmin, fmax = float(field.min()), float(field.max())
    print(f"\n  Done. Inside (bounded): {inside:,}/{n_total:,}")
    print(f"  Field range: min={fmin:.4f}  max={fmax:.4f}  mean={field.mean():.4f}")
    return field


# ── mesh extraction ────────────────────────────────────────────────────────────

def extract_mesh(
    field: np.ndarray,
    iso_level: float = 0.95,
    bounds: float = 1.5,
    center: tuple = (0.0, 0.0, -1.0),
):
    """
    Extract the isosurface at iso_level using marching cubes.

    Returns (vertices, faces, normals) in world coordinates,
    or None if scikit-image is not available.

    If iso_level is outside the field's value range it is automatically
    adjusted to 90% of the way from min to max, with a printed warning.
    """
    try:
        from skimage.measure import marching_cubes
    except ImportError:
        print("scikit-image not found.  Install with:  pip install scikit-image")
        return None

    fmin, fmax = float(field.min()), float(field.max())
    if not (fmin < iso_level < fmax):
        adjusted = fmin + 0.9 * (fmax - fmin)
        print(f"  Warning: iso_level {iso_level:.4f} is outside field range "
              f"[{fmin:.4f}, {fmax:.4f}] — using {adjusted:.4f} instead.")
        print(f"  Tip: re-run with --iso {adjusted:.2f} to use this level explicitly.")
        iso_level = adjusted

    n = field.shape[0]
    cx0, cy0, cz0 = center

    verts, faces, normals, _ = marching_cubes(field, level=iso_level)

    # Scale voxel indices [0, n-1] → world coordinates [center-bounds, center+bounds]
    verts[:, 0] = verts[:, 0] / (n - 1) * (2 * bounds) + (cx0 - bounds)
    verts[:, 1] = verts[:, 1] / (n - 1) * (2 * bounds) + (cy0 - bounds)
    verts[:, 2] = verts[:, 2] / (n - 1) * (2 * bounds) + (cz0 - bounds)

    return verts, faces, normals


# ── visualisation ──────────────────────────────────────────────────────────────

def show_slices(
    field: np.ndarray,
    bounds: float = 1.5,
    center: tuple = (0.0, 0.0, -1.0),
):
    """
    Display XY, XZ, and YZ cross-sections through the centre of the field.
    Bright (lime) = inside the set; dark (black) = escaped early.
    """
    n = field.shape[0]
    mid = n // 2
    cx0, cy0, cz0 = center

    # World-coordinate extents for each slice plane
    xy_ext = [cx0 - bounds, cx0 + bounds, cy0 - bounds, cy0 + bounds]
    xz_ext = [cx0 - bounds, cx0 + bounds, cz0 - bounds, cz0 + bounds]
    yz_ext = [cy0 - bounds, cy0 + bounds, cz0 - bounds, cz0 + bounds]

    z_mid = cz0  # the actual z value at the centre slice
    y_mid = cy0
    x_mid = cx0

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("EML-Bulb  —  scalar field cross-sections  (1.0 = inside)", fontsize=13)

    slices = [
        (field[:, :, mid].T, f"XY  (z = {z_mid:.2f})", "x", "y", xy_ext),
        (field[:, mid, :].T, f"XZ  (y = {y_mid:.2f})", "x", "z", xz_ext),
        (field[mid, :, :].T, f"YZ  (x = {x_mid:.2f})", "y", "z", yz_ext),
    ]
    for ax, (data, title, xlabel, ylabel, ext) in zip(axes, slices):
        im = ax.imshow(
            data, origin="lower", extent=ext,
            cmap=_EML_CMAP, vmin=0.0, vmax=1.0, interpolation="bilinear",
        )
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        fig.colorbar(im, ax=ax, label="field value")

    plt.tight_layout()
    plt.show()


def preview_3d(verts: np.ndarray, faces: np.ndarray, normals: np.ndarray):
    """
    Interactive 3D mesh preview.
    Uses PyVista when available; falls back to matplotlib Poly3DCollection.
    """
    try:
        import pyvista as pv
        pv_faces = np.column_stack([np.full(len(faces), 3, dtype=np.int_), faces]).ravel()
        mesh = pv.PolyData(verts, pv_faces)
        mesh.compute_normals(inplace=True)
        mesh["z"] = verts[:, 2]
        pl = pv.Plotter(window_size=(900, 900))
        pl.add_mesh(mesh, scalars="z", cmap="cool", smooth_shading=True, show_edges=False)
        pl.add_title("EML-Bulb", font_size=14)
        pl.show()
        return
    except ImportError:
        pass  # fall through to matplotlib

    # ── matplotlib fallback ────────────────────────────────────────────────────
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    max_faces = 30_000
    idx = faces
    if len(faces) > max_faces:
        rng = np.random.default_rng(0)
        idx = faces[rng.choice(len(faces), max_faces, replace=False)]
        print(f"  Subsampled to {max_faces:,} / {len(faces):,} faces for matplotlib speed.")

    tris = verts[idx]
    z_mid = tris[:, :, 2].mean(axis=1)
    z_norm = (z_mid - z_mid.min()) / (z_mid.ptp() + 1e-12)
    colours = plt.cm.cool(z_norm)

    fig = plt.figure(figsize=(9, 9))
    ax = fig.add_subplot(111, projection="3d")

    coll = Poly3DCollection(tris, facecolors=colours, edgecolors="none", alpha=0.85)
    ax.add_collection3d(coll)

    lo, hi = verts.min(), verts.max()
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_zlim(lo, hi)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.set_title("EML-Bulb  (install pyvista for interactive view)")
    plt.tight_layout()
    plt.show()


# ── OBJ export ─────────────────────────────────────────────────────────────────

def export_obj(verts: np.ndarray, faces: np.ndarray, path: str = "eml_bulb.obj"):
    """Export the mesh as a Wavefront OBJ file."""
    with open(path, "w") as f:
        f.write("# EML-Bulb mesh\n")
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
    print(f"Exported  →  {path}  ({len(verts):,} verts, {len(faces):,} faces)")


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="EML-Bulb 3D fractal renderer")
    ap.add_argument("--res",       type=int,   default=96,   metavar="N", help="voxel grid resolution N^3      (default 96)")
    ap.add_argument("--bounds",    type=float, default=1.5,  metavar="B", help="bounding box half-extent        (default 1.5)")
    ap.add_argument("--cx",        type=float, default=0.0,  metavar="X", help="grid centre x                   (default 0)")
    ap.add_argument("--cy",        type=float, default=0.0,  metavar="Y", help="grid centre y                   (default 0)")
    ap.add_argument("--cz",        type=float, default=-1.0, metavar="Z", help="grid centre z                   (default -1)")
    ap.add_argument("--power",     type=int,   default=8,    metavar="P", help="angular power                   (default 8)")
    ap.add_argument("--max-iter",  type=int,   default=32,   metavar="I", help="max iterations                  (default 32)")
    ap.add_argument("--escape",    type=float, default=8.0,  metavar="R", help="escape radius                   (default 8.0)")
    ap.add_argument("--iso",       type=float, default=0.95, metavar="L", help="isosurface level                (default 0.95)")
    ap.add_argument("--no-slices", action="store_true",                   help="skip cross-section plots")
    ap.add_argument("--no-export", action="store_true",                   help="skip OBJ export")
    args = ap.parse_args()

    center = (args.cx, args.cy, args.cz)

    print(f"EML-Bulb  res={args.res}^3  power={args.power}  max_iter={args.max_iter}  "
          f"escape={args.escape}  bounds=±{args.bounds}  center={center}")

    field = compute_field(
        resolution=args.res,
        bounds=args.bounds,
        center=center,
        power=args.power,
        max_iter=args.max_iter,
        escape_radius=args.escape,
    )

    if not args.no_slices:
        show_slices(field, bounds=args.bounds, center=center)

    result = extract_mesh(field, iso_level=args.iso, bounds=args.bounds, center=center)
    if result is not None:
        verts, faces, normals = result
        print(f"Mesh: {len(verts):,} vertices, {len(faces):,} faces")

        if not args.no_export:
            export_obj(verts, faces)

        preview_3d(verts, faces, normals)
