import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from ..config import DEFAULT_CAMERA_DISTANCE, GRID_SIZE, GRID_SPACING

try:
    import pyqtgraph as pg
    import pyqtgraph.opengl as gl
except Exception:
    pg = None
    gl = None

try:
    from c3d import Reader
except Exception:
    Reader = None

try:
    import ezc3d
except Exception:
    ezc3d = None

class Markers3DWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self._marker_size = 20
        if gl is None:
            self.layout.addWidget(QLabel("pyqtgraph or OpenGL not installed"))
            return
        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=5000)
        self.layout.addWidget(self.view)
        g = gl.GLGridItem()
        g.setSize(x=GRID_SIZE, y=GRID_SIZE)
        g.setSpacing(GRID_SPACING, GRID_SPACING)
        self.view.addItem(g)
        self.scatter = None
        self.last_points = None

    def plot_markers(self, markers):
        if gl is None:
            return
        if self.scatter is not None:
            try:
                self.view.removeItem(self.scatter)
            except Exception:
                pass
        pts = np.asarray(markers, dtype=float)
        try:
            self.last_points = pts.copy()
        except Exception:
            self.last_points = pts
        if pts.size == 0:
            return
        colors = np.ones((pts.shape[0], 4), dtype=float)
        colors[:, 0:3] = (1.0, 1.0, 1.0)
        colors[:, 3] = 1.0
        marker_size = getattr(self, '_marker_size', 20)
        self.scatter = gl.GLScatterPlotItem(pos=pts, size=20, color=colors, pxMode=False)
        self.view.addItem(self.scatter)

    def plot_markers_masked(self, markers, mask):
        """Plot all markers but apply mask (boolean array) to set alpha=0 for hidden markers.
        markers: (N,3) array, mask: boolean array length N (True == visible).
        """
        if gl is None:
            return
        try:
            if self.scatter is not None:
                self.view.removeItem(self.scatter)
            self.scatter = None
        except Exception:
            self.scatter = None

        pts = np.asarray(markers, dtype=float)
        try:
            self.last_points = pts.copy()
        except Exception:
            self.last_points = pts
        if pts.size == 0:
            return

        m = np.asarray(mask, dtype=bool) if mask is not None else np.ones((pts.shape[0],), dtype=bool)
        if m.size < pts.shape[0]:
            m = np.concatenate([m, np.ones((pts.shape[0] - m.size,), dtype=bool)])
        elif m.size > pts.shape[0]:
            m = m[:pts.shape[0]]

        colors = np.empty((pts.shape[0], 4), dtype=float)
        colors[:, 0:3] = 1.0
        colors[:, 3] = m.astype(float)

        try:
            self.scatter = gl.GLScatterPlotItem(pos=pts, size=20.0, color=colors, pxMode=False)
            self.view.addItem(self.scatter)
            self.view.update()
        except Exception:
            self.scatter = None

    def load_c3d(self, path):
        if ezc3d is not None:
            try:
                c = ezc3d.c3d(path)
                pts = np.array(c['data']['points'])
                if pts.ndim >= 3 and pts.shape[2] > 0:
                    first = pts[:3, :, 0].T
                    self.plot_markers(first)
                    return int(first.shape[0])
            except Exception as e:
                ez_err = e
        else:
            ez_err = None

        if Reader is None:
            raise RuntimeError(f"No C3D reader available (ezc3d import error: {ez_err})")

        try:
            with open(path, 'rb') as handle:
                r = Reader(handle)
                for i, fr in enumerate(r.read_frames()):
                    points, analog = fr
                    pts = np.array(points)[:, :3]
                    self.plot_markers(pts)
                    return int(pts.shape[0])
        except Exception as e:
            msg = str(e)
            if 'out of bounds for uint16' in msg.lower() or '65536' in msg:
                raise RuntimeError(
                    "C3D parsing failed due to integer overflow in 'python-c3d' (value >= 65536). "
                    "This is a known limitation for some C3D files. Please install 'ezc3d' which handles more variants: 'pip install ezc3d'"
                )
            raise RuntimeError(f"Failed to parse C3D file: {e}")
