"""Starter Manim scene in the Seneca style. Copy next to the project, rename, and edit.

Render:
  node <math>/scripts/render-math.mjs scene.py Explainer --size 1920x1080 --gif
  node <math>/scripts/render-math.mjs scene.py Explainer --timings voice/timings.json --clip

Equations are Typst math (not LaTeX): frac(a, b), sqrt(x), sum_(k=0)^n, x^2, alpha, RR, ->.
Group terms with {{ ... : label }} and pick them with eq.select("label").
"""
from seneca_scene import *


class Explainer(SenecaScene):
    def construct(self):
        P = self.palette

        # Beat 1: the statement. Kicker on top, equation centered.
        kicker = self.text("THE IDEA", size=26, color=P["steel"], weight="BOLD").to_edge(UP, buff=0.6)
        eq = self.eq("{{ sum_(k=1)^n k : sum }} = {{ (n(n+1)) / 2 : closed }}", size=88)
        self.play(FadeIn(kicker, shift=DOWN * 0.2), Write(eq), run_time=1.6)
        self.beat("statement", hold=1.0)

        # Beat 2: point at the part that matters.
        box = SurroundingRectangle(eq.select("closed"), color=P["signal"], buff=0.18, corner_radius=0.12)
        note = self.typst("closed form: one step, any $n$", size=34, color=P["steel"]).next_to(box, DOWN, buff=0.4)
        self.play(Create(box), FadeIn(note, shift=UP * 0.15), run_time=0.9)
        self.beat("closed-form", hold=1.2)

        # Beat 3: plug in a number, transforming in place so the eye can follow.
        example = self.eq("sum_(k=1)^100 k = (100 dot 101) / 2 = 5050", size=72).move_to(eq)
        self.play(FadeOut(box), FadeOut(note), TransformMatchingShapes(eq, example), run_time=1.4)
        self.play(Indicate(example, color=P["signal"], scale_factor=1.06), run_time=0.8)
        self.beat("example", hold=1.5)
