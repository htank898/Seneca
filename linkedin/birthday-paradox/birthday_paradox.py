"""The birthday paradox: 23 people is enough for a better-than-even shared birthday.

Render:
  node <ai-math>/scripts/render-math.mjs birthday_paradox.py BirthdayParadox --size 1080x1350 --fps 30 --gif
"""
import math

from seneca_scene import *


def p_match(n):
    """Exact chance that at least two of n people share a birthday (365 days)."""
    q = 1.0
    for k in range(int(n)):
        q *= (365 - k) / 365
    return 1 - q


def p_smooth(x):
    """p_match between integers, for drawing the curve."""
    lo = math.floor(x)
    return p_match(lo) + (p_match(lo + 1) - p_match(lo)) * (x - lo)


def pct(n):
    return f"{p_match(n) * 100:.1f}%"


class BirthdayParadox(SenecaScene):
    def construct(self):
        P = self.palette
        NO = P["steel"]       # "no match" everywhere
        HIT = "#c99a00"       # the answer (signal yellow, darkened to read on paper)
        H = config.frame_height / 2

        # Beat 1: the hook, visible from frame one.
        kicker = self.text("23 PEOPLE IN A MEETING", size=30, color=P["steel"], weight="BOLD").move_to(UP * (H - 0.75))
        question = self.text("What are the odds that\ntwo share a birthday?", size=44, weight="BOLD", line_spacing=1.1)
        question.next_to(kicker, DOWN, buff=0.45)
        self.add(kicker, question)
        self.wait(1.6)

        # Beat 2: build the chance of NO match, one person at a time.
        label = self.eq('P("no match") =', size=64, color=NO).next_to(question, DOWN, buff=0.8)
        prod = self.eq(
            "{{ 365/365 : f1 }} {{ dot 364/365 : f2 }} {{ dot 363/365 : f3 }} {{ dots.c 343/365 : fn }}",
            size=64, color=NO,
        ).next_to(label, DOWN, buff=0.45)
        prod.scale_to_fit_width(min(prod.width, config.frame_width - 1.0))
        note = self.text("each new person has to miss\neveryone already in the room", size=30,
                         color=P["ink"], line_spacing=1.1).next_to(prod, DOWN, buff=0.5)
        self.play(FadeIn(label), FadeIn(prod.select("f1")), run_time=0.6)
        for key in ("f2", "f3"):
            self.play(FadeIn(prod.select(key), shift=LEFT * 0.2), run_time=0.45)
        self.play(FadeIn(prod.select("fn"), shift=LEFT * 0.2), FadeIn(note), run_time=0.6)
        self.wait(0.9)

        # Collapse: no match ≈ 0.493, so match ≈ 50.7%.
        q23 = 1 - p_match(23)
        no_val = self.eq(f'P("no match") approx {q23:.3f}', size=64, color=NO).move_to(label)
        hit_eq = self.eq(f'P("match") = 1 - {q23:.3f}', size=64).next_to(no_val, DOWN, buff=0.6)
        hit_v = self.eq(f'approx "{p_match(23) * 100:.1f}%"', size=96, color=HIT).next_to(hit_eq, DOWN, buff=0.5)
        hit = VGroup(hit_eq, hit_v)
        self.play(FadeOut(note), FadeOut(prod, shift=UP * 0.2), ReplacementTransform(label, no_val), run_time=0.7)
        self.play(FadeIn(hit, shift=UP * 0.15), run_time=0.6)
        self.play(Indicate(hit_v, color=HIT, scale_factor=1.15), run_time=0.8)
        self.wait(1.0)

        # Beat 3: the curve. Readout replaces the question.
        readout = self.typst("23 people: *50.7%*", size=54).next_to(kicker, DOWN, buff=0.45)
        axes = Axes(
            x_range=[0, 70, 10], y_range=[0, 1, 0.25],
            x_length=config.frame_width - 1.6, y_length=5.0,
            axis_config={"color": P["steel"], "stroke_width": 3, "include_tip": False},
        ).move_to(DOWN * 1.15 + RIGHT * 0.35)
        x_nums = VGroup(*[
            self.text(str(k), size=26, color=P["steel"]).next_to(axes.c2p(k, 0), DOWN, buff=0.15)
            for k in range(0, 71, 10)
        ])
        y_labels = VGroup(*[
            self.text(f"{int(f * 100)}%", size=26, color=P["steel"]).next_to(axes.c2p(0, f), LEFT, buff=0.15)
            for f in (0.25, 0.5, 0.75, 1.0)
        ])
        x_title = self.text("people in the room", size=30, color=P["steel"]).next_to(axes.x_axis, DOWN, buff=0.65)
        half = DashedLine(axes.c2p(0, 0.5), axes.c2p(70, 0.5), color=P["steel"], stroke_width=3, dash_length=0.12)
        half_lbl = self.text("coin flip", size=26, color=P["steel"]).next_to(axes.c2p(70, 0.5), UP, buff=0.1).align_to(axes.c2p(70, 0.5), RIGHT)

        n = ValueTracker(1)
        curve = always_redraw(lambda: axes.plot(p_smooth, x_range=[1, max(n.get_value(), 1.01), 0.25],
                                                color=P["ink"], stroke_width=6))
        dot = always_redraw(lambda: Dot(axes.c2p(n.get_value(), p_smooth(n.get_value())), radius=0.11, color=P["ink"]))

        self.play(
            FadeOut(question), FadeOut(no_val), FadeOut(hit),
            Create(axes), FadeIn(x_nums), FadeIn(y_labels), FadeIn(x_title), Create(half), FadeIn(half_lbl),
            run_time=0.9,
        )
        self.add(curve, dot)
        self.play(n.animate.set_value(23), run_time=1.6, rate_func=linear)

        def marker(k, color, size=32):
            pt = axes.c2p(k, p_match(k))
            d = Dot(pt, radius=0.15, color=color)
            lbl = self.text(pct(k), size=size, color=color, weight="BOLD")
            return d, lbl

        d23, l23 = marker(23, HIT, 40)
        l23.next_to(d23, RIGHT, buff=0.2).shift(DOWN * 0.4)
        v23 = DashedLine(axes.c2p(23, 0), axes.c2p(23, p_match(23)), color=HIT, stroke_width=3)
        self.play(GrowFromCenter(d23), Create(v23), FadeIn(l23), FadeIn(readout), run_time=0.6)
        self.wait(1.6)

        # Beat 4: keep going.
        stops = []
        tag = self.text("a company all-hands", size=30, color=P["steel"]).next_to(readout, DOWN, buff=0.2)
        for k, side in ((30, LEFT), (50, DOWN), (70, UP)):
            self.play(n.animate.set_value(k), run_time=0.7, rate_func=smooth)
            d, l = marker(k, P["ink"], 30)
            l.next_to(d, side, buff=0.2)
            if k == 70:
                l.align_to(d, RIGHT)
            new_readout = self.typst(f"{k} people: *{pct(k)}*", size=54).move_to(readout)
            anims = [GrowFromCenter(d), FadeIn(l), Transform(readout, new_readout)]
            if k == 70:
                anims.append(FadeIn(tag))
            self.play(*anims, run_time=0.45)
            stops.append(VGroup(d, l))
            self.wait(0.4 if k < 70 else 0.8)

        # Beat 5: the punchline holds on the last frame.
        self.wait(0.4)
        chart = VGroup(axes, x_nums, y_labels, x_title, half, half_lbl, dot, *stops, v23)
        curve.clear_updaters(); dot.clear_updaters()
        punch = self.typst("Just *23 people* beats a coin flip.", size=44).move_to(readout)
        self.play(chart.animate.set_opacity(0.25), curve.animate.set_stroke(opacity=0.3),
                  FadeOut(tag), Transform(readout, punch),
                  Indicate(d23, color=HIT, scale_factor=1.4), run_time=0.8)
        self.wait(2.2)
