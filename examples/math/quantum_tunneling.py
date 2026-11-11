"""Quantum tunneling, computed rather than drawn.

The wave packet is a real solution of the time-dependent Schrodinger equation (split-step
Fourier, hbar = m = 1), so the reflected/transmitted split on screen is the physics, not a guess.

  E = 2, V0 = 2.5, L = 1.5  ->  kappa = sqrt(2(V0 - E)) = 1
  single energy E = 2: exact 12.4%, thick-barrier formula 12.7%
  the packet (sigma = 4): simulated 13.4%, exact average over its momentum spread 13.40%
    (converged: 8192 points / dt 0.002 and 16384 / 0.0005 agree to 0.01%)
  double the width (L = 3): exact 0.63%

Render (from the repo root):
  node skills/ai-math/scripts/render-math.mjs examples/math/quantum_tunneling.py QuantumTunneling \
    --out examples/math/quantum-tunneling.mp4 --size 1920x1080 --fps 30
"""
import numpy as np

from seneca_scene import *

# ---------------------------------------------------------------- physics (hbar = m = 1)
K0, V0, L, SIGMA, X0 = 2.0, 2.5, 1.5, 4.0, -20.0
E = K0**2 / 2
KAPPA = np.sqrt(2 * (V0 - E))
XMIN, XMAX = -32.0, 32.0


def simulate(t_end=21.0, dt=0.002, n=8192, half=150.0, keep=420, L=L, sigma=SIGMA, x0=X0, window=(XMIN, XMAX),
             complex_frames=False):
    """Split-step Fourier solution of i dpsi/dt = -1/2 psi'' + V psi. Returns |psi|^2 frames on the plot window
    (or psi itself with complex_frames=True), plus reflected/transmitted probability per frame."""
    x = np.linspace(-half, half, n, endpoint=False)
    dx = x[1] - x[0]
    k = 2 * np.pi * np.fft.fftfreq(n, dx)
    # Edges rounded over ~0.02 units: a perfectly sharp step rings at the grid's Nyquist
    # frequency in a spectral solver. It doesn't change T (13.4% either way).
    w = 0.02
    V = V0 * 0.5 * (np.tanh(x / w) - np.tanh((x - L) / w))
    psi = (2 * np.pi * sigma**2) ** -0.25 * np.exp(-((x - x0) ** 2) / (4 * sigma**2) + 1j * K0 * x)
    half_v, kin = np.exp(-0.5j * V * dt), np.exp(-0.5j * k**2 * dt)
    steps = int(round(t_end / dt))
    every = max(1, steps // keep)
    win = (x >= window[0]) & (x <= window[1])
    frames, refl, trans = [], [], []
    for i in range(steps + 1):
        if i % every == 0:
            p = np.abs(psi) ** 2
            frames.append(psi[win].copy() if complex_frames else p[win])
            refl.append(p[x < 0].sum() * dx)
            trans.append(p[x > L].sum() * dx)
        psi = half_v * np.fft.ifft(kin * np.fft.fft(half_v * psi))
    return x[win], np.array(frames), np.array(refl), np.array(trans)


def stationary(xs):
    """|psi| of the energy-E scattering state: e^{ikx} + r e^{-ikx} | A e^{kx} + B e^{-kx} | t e^{ikx}."""
    k, q = K0, KAPPA
    eL, emL, ekL = np.exp(q * L), np.exp(-q * L), np.exp(1j * k * L)
    # unknowns r, A, B, t ; continuity of psi and psi' at x = 0 and x = L
    M = np.array([
        [-1, 1, 1, 0],
        [1j * k, q, -q, 0],
        [0, eL, emL, -ekL],
        [0, q * eL, -q * emL, -1j * k * ekL],
    ], dtype=complex)
    rhs = np.array([1, 1j * k, 0, 0], dtype=complex)
    r, A, B, t = np.linalg.solve(M, rhs)
    psi = np.where(xs < 0, np.exp(1j * k * xs) + r * np.exp(-1j * k * xs),
                   np.where(xs <= L, A * np.exp(q * xs) + B * np.exp(-q * xs), t * np.exp(1j * k * xs)))
    return np.abs(psi), abs(t) ** 2


class QuantumTunneling(SenecaScene):
    def construct(self):
        P = self.palette
        xs, frames, refl, trans = simulate()
        nf = len(frames)

        # ------------------------------------------------ beat 1: the equation
        kicker = self.text("QUANTUM TUNNELING", size=26, color=P["steel"], weight="BOLD").to_edge(UP, buff=0.5)
        tdse = self.eq("i ħ (partial psi)/(partial t) = -ħ^2/(2m) (partial^2 psi)/(partial x^2) + V(x) psi", size=60)
        gloss = self.typst("A particle is a wave $psi(x, t)$. Where $|psi|^2$ is tall, you're likely to find it.",
                           size=32, color=P["steel"]).next_to(tdse, DOWN, buff=0.6)
        self.play(FadeIn(kicker, shift=DOWN * 0.2), Write(tdse), run_time=2.0)
        self.play(FadeIn(gloss, shift=UP * 0.15), run_time=0.8)
        self.beat("equation", hold=2.6)
        self.play(FadeOut(gloss), tdse.animate.scale(0.55).next_to(kicker, DOWN, buff=0.3), run_time=1.0)

        # ------------------------------------------------ beat 2: the wall
        ax = Axes(x_range=[XMIN, XMAX, 8], y_range=[0, 0.35, 0.05], x_length=13, y_length=4.2, tips=False,
                  axis_config={"color": P["steel"], "stroke_width": 3, "include_ticks": False})
        ax.y_axis.set_opacity(0)
        ax.shift(DOWN * (ax.c2p(0, 0)[1] + 2.3))      # baseline at y = -2.3
        base_y = ax.c2p(0, 0)[1]
        wall_h = 2.6
        x0p, x1p = ax.c2p(0, 0)[0], ax.c2p(L, 0)[0]
        wall = Rectangle(width=x1p - x0p, height=wall_h, stroke_color=P["ink"], stroke_width=3,
                         fill_color=P["ink"], fill_opacity=0.85)
        wall.move_to([(x0p + x1p) / 2, base_y + wall_h / 2, 0])
        e_y = base_y + wall_h * E / V0
        e_line = DashedLine([ax.c2p(XMIN, 0)[0], e_y, 0], [ax.c2p(XMAX, 0)[0], e_y, 0],
                            color=P["steel"], stroke_width=2.5, dash_length=0.12)
        v_lab = self.eq("V_0", size=40).next_to(wall, UP, buff=0.15)
        e_lab = self.eq("E < V_0", size=36, color=P["steel"]).next_to(e_line, UP, buff=0.12).align_to(e_line, LEFT).shift(RIGHT * 0.2)
        brace = Brace(wall, DOWN, buff=0.08, color=P["steel"])
        l_lab = self.eq("L", size=30, color=P["steel"]).next_to(brace, DOWN, buff=0.05)
        classical = self.text("Classically, that's a wall: with less energy than V₀, every particle bounces.",
                              size=30, color=P["ink"]).to_edge(DOWN, buff=0.3)
        self.play(Create(ax), run_time=0.8)
        self.play(GrowFromEdge(wall, DOWN), FadeIn(v_lab), run_time=0.8)
        self.play(Create(e_line), FadeIn(e_lab), GrowFromCenter(brace), FadeIn(l_lab), run_time=0.9)
        self.play(FadeIn(classical, shift=UP * 0.15), run_time=0.7)
        self.beat("wall", hold=2.4)

        # ------------------------------------------------ beat 3: the packet, solved
        clock = ValueTracker(0)
        ys = 4.2 / 0.35   # |psi|^2 -> scene units; the collision's interference peaks (~0.34) just fit
        ZOOM = 6          # the transmitted part is small at true scale, so also outline it magnified

        def density():
            s = clock.get_value()
            i = int(np.floor(s))
            f = s - i
            p = frames[min(i, nf - 1)] * (1 - f) + frames[min(i + 1, nf - 1)] * f
            return p

        def region(mask, color, opacity):
            def make():
                p = density()
                sel = np.where(mask)[0]
                pts = [ax.c2p(xs[j], 0) for j in (sel[0],)] + \
                      [np.array([ax.c2p(xs[j], 0)[0], base_y + p[j] * ys, 0]) for j in sel] + \
                      [ax.c2p(xs[sel[-1]], 0)]
                return Polygon(*pts, stroke_width=0, fill_color=color, fill_opacity=opacity)
            return make

        left = always_redraw(region(xs < 0, P["steel"], 0.55))
        right = always_redraw(region(xs > L, P["signal"], 0.95))
        outline = always_redraw(lambda: VMobject(stroke_color=P["ink"], stroke_width=3).set_points_as_corners(
            [np.array([ax.c2p(x, 0)[0], base_y + p * ys, 0]) for x, p in zip(xs, density())]))
        far = xs > L + 0.3
        zoomed = always_redraw(lambda: VMobject(stroke_color=P["signal"], stroke_width=3.5).set_points_as_corners(
            [np.array([ax.c2p(x, 0)[0], base_y + ZOOM * p * ys, 0]) for x, p in zip(xs[far], density()[far])]))
        zoom_lab = self.text(f"×{ZOOM}", size=28, color=P["ink"], weight="BOLD").move_to(ax.c2p(27, 0.1))

        def pct(series, label, color):
            def make():
                s = clock.get_value()
                i = int(np.floor(s))
                f = s - i
                v = series[min(i, nf - 1)] * (1 - f) + series[min(i + 1, nf - 1)] * f
                return self.text(f"{label}  {100 * v:4.1f}%", size=32, color=color, weight="BOLD")
            return make

        r_txt = always_redraw(lambda: pct(refl, "reflected", P["steel"])().move_to([ax.c2p(-24, 0)[0], 1.7, 0], aligned_edge=LEFT))
        t_txt = always_redraw(lambda: pct(trans, "transmitted", P["ink"])().move_to([ax.c2p(9, 0)[0], 1.7, 0], aligned_edge=LEFT))
        t_chip = always_redraw(lambda: SurroundingRectangle(t_txt, color=P["signal"], fill_color=P["signal"],
                                                            fill_opacity=0.35, stroke_width=0, buff=0.12, corner_radius=0.08))
        solved = self.text("Solving that equation numerically, frame by frame:", size=30).to_edge(DOWN, buff=0.3)
        self.play(FadeOut(classical, run_time=0.3), FadeIn(solved, run_time=0.6))
        self.add(left, right, outline, zoomed)
        self.play(FadeIn(r_txt), FadeIn(t_chip), FadeIn(t_txt), run_time=0.6)
        self.play(clock.animate.set_value(nf * 0.62), run_time=6.8, rate_func=linear)
        self.play(FadeIn(zoom_lab), clock.animate.set_value(nf - 1), run_time=4.2, rate_func=linear)
        got = self.typst(f"{100 * trans[-1]:.1f}% of the wave ends up on the far side of a wall it can't climb.",
                         size=30).to_edge(DOWN, buff=0.3)
        self.play(FadeOut(solved, run_time=0.3), FadeIn(got, shift=UP * 0.15, run_time=0.7))
        self.beat("packet", hold=2.6)

        # ------------------------------------------------ beat 4: why: the wave decays inside, it doesn't stop
        for m in (left, right, outline, zoomed, r_txt, t_txt, t_chip):
            m.clear_updaters()
        old = VGroup(ax, wall, e_line, e_lab, v_lab, brace, l_lab, left, right, outline, zoomed, zoom_lab,
                     r_txt, t_txt, t_chip, got, tdse)
        self.play(FadeOut(old), run_time=0.8)

        zx = (-5.5, 7.0)
        ax2 = Axes(x_range=[zx[0], zx[1], 1], y_range=[0, 2.1, 0.5], x_length=12.4, y_length=3.3, tips=False,
                   axis_config={"color": P["steel"], "stroke_width": 3, "include_ticks": False})
        ax2.y_axis.set_opacity(0)
        ax2.shift(DOWN * (ax2.c2p(0, 0)[1] + 1.55))   # baseline at y = -1.55
        b0, b1 = ax2.c2p(0, 0), ax2.c2p(L, 0)
        wall2 = Rectangle(width=b1[0] - b0[0], height=3.3, stroke_width=0, fill_color=P["ink"], fill_opacity=0.12)
        wall2.move_to([(b0[0] + b1[0]) / 2, b0[1] + 1.65, 0])
        edges = VGroup(*[DashedLine([px, b0[1], 0], [px, b0[1] + 3.3, 0], color=P["ink"], stroke_width=2, dash_length=0.1)
                         for px in (b0[0], b1[0])])
        zs = np.linspace(zx[0], zx[1], 1400)
        amp, T_exact = stationary(zs)
        wave = VMobject(stroke_width=4).set_points_smoothly([ax2.c2p(x, a) for x, a in zip(zs, amp)])
        wave.set_color(P["ink"])
        inside = (zs >= 0) & (zs <= L)
        decay = VMobject(stroke_color=P["signal"], stroke_width=9).set_points_smoothly(
            [ax2.c2p(x, a) for x, a in zip(zs[inside], amp[inside])])
        title = self.text("Why: one energy, steady state, |ψ(x)|", size=32, color=P["steel"]).move_to([0, 2.55, 0]).to_edge(LEFT, buff=0.8)
        k_eq = self.eq("psi(x) prop e^(-kappa x), quad kappa = sqrt(2m(V_0 - E))/ħ", size=44).move_to(DOWN * 2.55)
        tag_left = self.text("incoming + reflected", size=26, color=P["steel"]).next_to(ax2.c2p(-2.75, 0), DOWN, buff=0.15)
        tag_right = self.text("what got through", size=26, color=P["steel"]).next_to(ax2.c2p(4.25, 0), DOWN, buff=0.15)
        self.play(FadeIn(title), Create(ax2), FadeIn(wall2), Create(edges), run_time=0.9)
        self.play(Create(wave), run_time=2.2, rate_func=linear)
        self.play(FadeIn(tag_left), FadeIn(tag_right), run_time=0.6)
        self.play(Create(decay), Write(k_eq), run_time=1.4)
        note = self.text("Inside the wall the wave shrinks exponentially, but it never reaches zero.",
                         size=30).to_edge(DOWN, buff=0.3)
        self.play(FadeIn(note, shift=UP * 0.1), run_time=0.6)
        self.beat("decay", hold=3.0)

        # ------------------------------------------------ beat 5: the number, and why width is everything
        self.play(FadeOut(VGroup(ax2, wall2, edges, wave, decay, title, tag_left, tag_right, note, k_eq)), run_time=0.8)
        t_eq = self.eq("T approx (16 E (V_0 - E))/V_0^2 thin {{ e^(-2 kappa L) : exp }}", size=72).move_to(UP * 1.5)
        box = SurroundingRectangle(t_eq, color=P["signal"], buff=0.3, corner_radius=0.14, stroke_width=5)
        vals = self.typst("$E = 2, space V_0 = 2.5, space L = 1.5 space (ħ = m = 1) quad -> quad kappa = 1$",
                          size=32, color=P["steel"]).next_to(box, DOWN, buff=0.45)
        approx = 16 * E * (V0 - E) / V0**2 * np.exp(-2 * KAPPA * L)
        rows = VGroup(
            self.text(f"formula  {100 * approx:.1f}%", size=30),
            self.text(f"exact at E = 2  {100 * T_exact:.1f}%", size=30),
            self.text(f"the packet above  {100 * trans[-1]:.1f}%", size=30, weight="BOLD"),
        ).arrange(RIGHT, buff=0.7).next_to(vals, DOWN, buff=0.5)
        spread = self.text("The packet carries a spread of energies, and its faster parts tunnel more.",
                           size=26, color=P["steel"]).next_to(rows, DOWN, buff=0.3)
        self.play(Write(t_eq), run_time=1.6)
        self.play(Create(box), FadeIn(vals), run_time=0.8)
        self.play(LaggedStart(*[FadeIn(r, shift=UP * 0.1) for r in rows], lag_ratio=0.35), run_time=1.4)
        self.play(FadeIn(spread), run_time=0.6)
        self.beat("formula", hold=2.5)

        _, T_double = stationary_T(2 * L)
        punch = self.typst(f"Double the wall to $L = 3$ and $T$ drops to *{100 * T_double:.2f}%*, about 20 times less.",
                           size=36).to_edge(DOWN, buff=0.85)
        why = self.text("That exponential is why a scanning tunneling microscope can feel single atoms.",
                        size=28, color=P["steel"]).next_to(punch, DOWN, buff=0.25)
        self.play(Indicate(t_eq.select("exp"), color=P["signal"], scale_factor=1.2), FadeIn(punch, shift=UP * 0.15), run_time=1.0)
        self.play(FadeIn(why), run_time=0.7)
        self.beat("width", hold=3.5)


def stationary_T(width):
    """Exact plane-wave transmission for a rectangular barrier of the given width (E < V0)."""
    T = 1 / (1 + V0**2 * np.sinh(KAPPA * width) ** 2 / (4 * E * (V0 - E)))
    return width, T
