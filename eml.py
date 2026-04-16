import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# LSD-style cycling colormap: black → blue → cyan → green → lime → orange → deep orange → violet → black
_EML_CMAP = LinearSegmentedColormap.from_list(
    "eml_lsd",
    [
        "#000011",  # near-black (interior)
        "#0033ff",  # vivid blue
        "#00ccff",  # sky blue / cyan
        "#00ff99",  # bright green
        "#aaff00",  # lime
    ],
    N=512,
)

# ============================================
# EML Fractal interactive viewer
# z_{n+1} = exp(z_n) - Log(c),   z_0 = 0
# Controls:
#   - Mouse wheel: zoom in/out
#   - Left mouse drag: pan
# ============================================


class EMLFractalViewer:
    def __init__(self):
        # Initial view
        self.xmin, self.xmax = -1.0, 3.0
        self.ymin, self.ymax = -2.0, 2.0

        # Render settings
        self.width = 800
        self.height = 800
        self.max_iter = 80
        self.escape_radius = 20.0

        # Drag state
        self.dragging = False
        self.drag_start_screen = None
        self.drag_start_view = None

        # Figure
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        self.image_artist = None

        # Connect events
        self.fig.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)

        self.render()

    def compute_image(self):
        log_R = np.log(self.escape_radius)

        xs = np.linspace(self.xmin, self.xmax, self.width)
        ys = np.linspace(self.ymin, self.ymax, self.height)

        # Build full complex grid: shape (height, width)
        C = xs[np.newaxis, :] + 1j * ys[:, np.newaxis]

        # Points where c ≈ 0 are treated as inside the set (log undefined)
        near_zero = np.abs(C) < 1e-14
        log_C = np.log(np.where(near_zero, 1.0, C))  # safe; near_zero pixels stay inside

        Z = np.zeros((self.height, self.width), dtype=np.complex128)
        image = np.full((self.height, self.width), float(self.max_iter), dtype=np.float32)

        # active: pixels still being iterated
        active = ~near_zero

        with np.errstate(over="ignore", invalid="ignore"):
            for n in range(self.max_iter):
                # z_{n+1} = exp(z_n) - Log(c)  — only for pixels not yet escaped
                Z[active] = np.exp(Z[active]) - log_C[active]

                abs_Z = np.abs(Z)
                newly_escaped = active & (abs_Z > self.escape_radius)

                if newly_escaped.any():
                    # Smooth coloring: normalise by log(R) for transcendental map
                    lz = np.log(abs_Z[newly_escaped])
                    nu = np.where(
                        lz > log_R,
                        n + 1.0 - np.log(lz / log_R) / log_R,
                        float(n + 1),
                    )
                    image[newly_escaped] = np.maximum(0.0, nu)
                    active &= ~newly_escaped

                if not active.any():
                    break

        return image

    def render(self):
        print(
            f"Rendering: x=[{self.xmin:.6f}, {self.xmax:.6f}], "
            f"y=[{self.ymin:.6f}, {self.ymax:.6f}]"
        )

        image = self.compute_image()

        if self.image_artist is None:
            self.image_artist = self.ax.imshow(
                image,
                extent=[self.xmin, self.xmax, self.ymin, self.ymax],
                origin="lower",
                cmap=_EML_CMAP,
                interpolation="bilinear",
                vmin=0,
                vmax=self.max_iter,
            )
            self.ax.set_title("EML Fractal: scroll=zoom, left-drag=pan")
            self.ax.set_xlabel("Re(c)")
            self.ax.set_ylabel("Im(c)")
            self.fig.colorbar(self.image_artist, ax=self.ax, label="escape time")
        else:
            self.image_artist.set_data(image)
            self.image_artist.set_clim(0, self.max_iter)
            self.image_artist.set_extent([self.xmin, self.xmax, self.ymin, self.ymax])

        self.ax.set_xlim(self.xmin, self.xmax)
        self.ax.set_ylim(self.ymin, self.ymax)
        self.fig.canvas.draw_idle()

    def zoom(self, xcenter, ycenter, scale_factor):
        xrange = self.xmax - self.xmin
        yrange = self.ymax - self.ymin

        new_xrange = xrange * scale_factor
        new_yrange = yrange * scale_factor

        relx = (xcenter - self.xmin) / xrange
        rely = (ycenter - self.ymin) / yrange

        self.xmin = xcenter - relx * new_xrange
        self.xmax = self.xmin + new_xrange
        self.ymin = ycenter - rely * new_yrange
        self.ymax = self.ymin + new_yrange

    def on_scroll(self, event):
        if event.xdata is None or event.ydata is None:
            return

        # Scroll up -> zoom in, scroll down -> zoom out
        if event.button == "up":
            scale_factor = 0.8
        elif event.button == "down":
            scale_factor = 1.25
        else:
            return

        self.zoom(event.xdata, event.ydata, scale_factor)
        self.render()

    def on_press(self, event):
        if event.button != 1:
            return
        if event.xdata is None or event.ydata is None:
            return

        self.dragging = True
        self.drag_start_screen = (event.xdata, event.ydata)
        self.drag_start_view = (self.xmin, self.xmax, self.ymin, self.ymax)

    def on_motion(self, event):
        if not self.dragging:
            return
        if event.xdata is None or event.ydata is None:
            return

        x0, y0 = self.drag_start_screen
        xmin0, xmax0, ymin0, ymax0 = self.drag_start_view

        dx = event.xdata - x0
        dy = event.ydata - y0

        # Dragging moves the view with the mouse
        self.xmin = xmin0 - dx
        self.xmax = xmax0 - dx
        self.ymin = ymin0 - dy
        self.ymax = ymax0 - dy

        # Update only viewport during drag for smoothness
        self.ax.set_xlim(self.xmin, self.xmax)
        self.ax.set_ylim(self.ymin, self.ymax)
        self.image_artist.set_extent([self.xmin, self.xmax, self.ymin, self.ymax])
        self.fig.canvas.draw_idle()

    def on_release(self, event):
        if event.button != 1:
            return
        if not self.dragging:
            return

        self.dragging = False
        self.drag_start_screen = None
        self.drag_start_view = None

        # Re-render after pan
        self.render()


if __name__ == "__main__":
    viewer = EMLFractalViewer()
    plt.show()