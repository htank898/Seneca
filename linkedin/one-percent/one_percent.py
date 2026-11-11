"""1% better vs 1% worse, every day for a year: 1.01^n and 0.99^n race from day 1 to day 365.

Render (4:5 for the LinkedIn feed):
  node <ai-math>/scripts/render-math.mjs linkedin/one-percent/one_percent.py OnePercent \
    --size 1080x1350 --fps 30 --gif --out linkedin/one-percent/one-percent.mp4
"""
from seneca_scene import *

DAYS = 365
UP_RATE, DOWN_RATE = 1.01, 0.99
BEST = UP_RATE ** DAYS            # 37.7834...
WORST = DOWN_RATE ** DAYS         # 0.025518...
RATIO = BEST / WORST              # 1480.66...


class OnePercent(SenecaScene):
    def construct(self):
        P = self.palette
        W, H = config.frame_width, config.frame_height   # 8 x 10 at 4:5

        # Beat 1: the hook is on screen from frame 0 (LinkedIn shows the first frame).
        hook = self.text("1% better vs 1% worse", size=50, weight="BOLD").to_edge(UP, buff=0.5)
        hook.scale_to_fit_width(min(hook.width, W - 1.0))
        sub = self.text("every day, for a year", size=34, color=P["steel"]).next_to(hook, DOWN, buff=0.18)
        self.add(hook, sub)

        # Equations: better on the left (signal), worse on the right (steel).
        n = ValueTracker(0)
        col = W / 4
        eq_up = self.eq("1.01^n", size=80).move_to(LEFT * col + UP * 1.75)
        eq_dn = self.eq("0.99^n", size=80, color=P["steel"]).move_to(RIGHT * col + UP * 1.75)
        mark = RoundedRectangle(width=eq_up.width + 0.45, height=eq_up.height + 0.3, corner_radius=0.12,
                                stroke_width=0, fill_color=P["signal"], fill_opacity=1).move_to(eq_up)

        def value(rate, pos, color):
            def build():
                v = rate ** n.get_value()
                return self.text(f"= {v:.2f}", size=50, color=color, weight="BOLD").move_to(pos)
            return always_redraw(build)

        val_up = value(UP_RATE, LEFT * col + UP * 0.8, P["ink"])
        val_dn = value(DOWN_RATE, RIGHT * col + UP * 0.8, P["steel"])

        # Chart: linear y so the gap is felt, not read off a log scale.
        ax = Axes(x_range=[0, DAYS, 73], y_range=[0, 40, 10], x_length=W - 2.4, y_length=4.2, tips=False,
                  axis_config={"color": P["steel"], "stroke_width": 3, "include_ticks": True, "tick_size": 0.06})
        ax.to_edge(DOWN, buff=0.95).shift(RIGHT * 0.15)
        ylabels = VGroup(*[self.text(str(y), size=26, color=P["steel"]).next_to(ax.c2p(0, y), LEFT, buff=0.15)
                           for y in (0, 10, 20, 30, 40)])
        xlabels = VGroup(
            self.text("day 0", size=28, color=P["steel"]).next_to(ax.c2p(0, 0), DOWN, buff=0.2),
            self.text("day 365", size=28, color=P["steel"]).next_to(ax.c2p(DAYS, 0), DOWN, buff=0.2),
        )
        day = always_redraw(lambda: self.text(f"Day {int(round(n.get_value()))}", size=42, weight="BOLD")
                            .move_to(UP * 3.0))

        def curve(rate, color):
            def build():
                t = max(n.get_value(), 0.5)
                return ax.plot(lambda x: rate ** x, x_range=[0, t, 1], color=color, stroke_width=8)
            return always_redraw(build)

        def head(rate, color):
            return always_redraw(lambda: Dot(ax.c2p(n.get_value(), rate ** n.get_value()), radius=0.11,
                                             color=color, stroke_color=P["ink"], stroke_width=2))

        c_up, c_dn = curve(UP_RATE, P["signal"]), curve(DOWN_RATE, P["steel"])
        h_up, h_dn = head(UP_RATE, P["signal"]), head(DOWN_RATE, P["steel"])

        # Everything but the race is up from frame 0, so the preview frame already reads as the setup.
        self.add(mark, eq_up, eq_dn, val_up, val_dn, ax, ylabels, xlabels, day, c_up, c_dn, h_up, h_dn)
        self.wait(1.2)

        # Beat 2: the year plays out. Linear time, so the late explosion is felt.
        self.play(n.animate.set_value(DAYS), run_time=8, rate_func=linear)
        self.wait(0.6)

        # Beat 3: the punchline, in the empty space above the flat line.
        p1 = self.text("Same 2% difference.", size=34, color=P["steel"])
        p2 = self.text(f"{RATIO:,.0f}× apart.", size=50, weight="BOLD")
        punch = VGroup(p1, p2).arrange(DOWN, buff=0.18, aligned_edge=LEFT)
        punch.move_to(ax.c2p(0, 30), aligned_edge=LEFT).shift(RIGHT * 0.25)
        self.play(FadeIn(punch, shift=UP * 0.2), run_time=0.9)
        self.wait(2.6)
