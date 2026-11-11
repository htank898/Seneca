"""Squares on the sides of a right triangle: the areas add up.

Render (from the repo root):
  node skills/ai-math/scripts/render-math.mjs examples/math/pythagoras.py Pythagoras --size 1080x1080 --gif
"""
from seneca_scene import *


class Pythagoras(SenecaScene):
    def construct(self):
        P = self.palette
        a, b = 1.5, 2.0                       # legs; c = 2.5
        A = ORIGIN
        B = A + RIGHT * b
        C = A + UP * a
        tri = Polygon(A, B, C, color=P["ink"], stroke_width=6, fill_color=P["card"], fill_opacity=1)

        def square_on(p, q, color):
            # square built outward from edge p→q (outward = to the right of p→q for this winding)
            d = q - p
            n = np.array([d[1], -d[0], 0])
            return Polygon(p, q, q + n, p + n, color=color, stroke_width=4, fill_color=color, fill_opacity=0.35)

        sq_b = square_on(A, B, P["steel"])    # below the base
        sq_a = square_on(C, A, P["steel"])    # left of the height
        sq_c = square_on(B, C, P["signal"])   # on the hypotenuse
        fig = VGroup(sq_a, sq_b, sq_c, tri)
        fig.scale_to_fit_height(config.frame_height * 0.52).move_to(UP * 0.35)

        la = self.eq("a^2", color=P["ink"]).move_to(sq_a)
        lb = self.eq("b^2", color=P["ink"]).move_to(sq_b)
        lc = self.eq("c^2", color=P["ink"]).move_to(sq_c)

        title = self.text("Squares on a right triangle", size=34, color=P["steel"]).to_edge(UP, buff=0.45)

        self.play(FadeIn(title, shift=DOWN * 0.2), Create(tri), run_time=1.2)
        self.play(GrowFromEdge(sq_a, RIGHT), GrowFromEdge(sq_b, UP), run_time=1.0)
        self.play(FadeIn(la, scale=0.8), FadeIn(lb, scale=0.8), run_time=0.6)
        self.beat("legs", hold=0.6)
        self.play(GrowFromCenter(sq_c), run_time=1.0)
        self.play(FadeIn(lc, scale=0.8), run_time=0.5)
        self.beat("hypotenuse", hold=0.6)

        # The labels fly down and become the equation.
        e = self.eq("{{ a^2 : a }} + {{ b^2 : b }} = {{ c^2 : c }}", size=96).to_edge(DOWN, buff=0.55)
        self.play(
            ReplacementTransform(la, e.select("a")),
            ReplacementTransform(lb, e.select("b")),
            ReplacementTransform(lc, e.select("c")),
            FadeIn(VGroup(*[m for m in e.submobjects if m not in (*e.select("a"), *e.select("b"), *e.select("c"))])),
            fig.animate.set_opacity(0.25),
            run_time=1.4,
        )
        self.play(Indicate(e.select("c"), color=P["signal"], scale_factor=1.15), run_time=0.9)
        self.beat("equation", hold=1.5)
