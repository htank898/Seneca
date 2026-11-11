"""What if YOU could quantum tunnel? A vertical (9:16) narrated short.

Arc: what it would mean -> what it would take (real odds) -> why mass matters -> an electron's
wave actually tunneling (the real Schrodinger simulation from ../quantum_tunneling.py) -> the math.

Numbers on screen (T ~ e^{-2 kappa L}, kappa = sqrt(2 m (V - E)) / hbar):
  you:      m = 70 kg, V - E = 1 J,  L = 10 cm  ->  2 kappa L = 2.2e34  ->  T ~ 10^(-9.7e33) ~ 10^(-10^34)
  electron: m = 9.11e-31 kg, V - E = 1 eV, L = 1 nm  ->  2 kappa L = 10.2  ->  T ~ 3.5e-5 (1 in 28,000)
  simulated wave packet (hbar = m = 1, E = 2, V0 = 2.5, L = 1.5): 13.4% gets through
  "you" is the usual toy estimate: a person treated as one particle.

Build (from the repo root):
  python3 <ai-video>/scripts/tts.py examples/math/tunneling-short/scenes.json
  node <ai-video>/scripts/render-video.mjs examples/math/tunneling-short/animation.html \
    --out examples/math/tunneling-short/quantum-tunneling-short.mp4 --audio-only     (and --captions-only)
  node skills/ai-math/scripts/render-math.mjs examples/math/tunneling-short/tunneling_short.py TunnelingShort \
    --size 1080x1920 --fps 30 --timings examples/math/tunneling-short/voice/timings.json --out picture.mp4
  then mux picture.mp4 with voice/narration.wav (loudnorm to -16 LUFS).
"""
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from seneca_scene import *  # noqa: E402
import quantum_tunneling as qt  # noqa: E402

WIN = (-24.0, 24.0)
X0 = -16.0
HBAR = 1.054571817e-34


def two_kappa_L(m, gap, L):
    return 2 * math.sqrt(2 * m * gap) / HBAR * L


YOU = two_kappa_L(70.0, 1.0, 0.10)                            # ~2.24e34
ELECTRON = two_kappa_L(9.1093837e-31, 1.602176634e-19, 1e-9)  # ~10.25


def load_srt(path):
    cues = []
    for block in open(path).read().strip().split("\n\n"):
        lines = block.strip().split("\n")
        m = re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1])
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
        cues.append((h1 * 3600 + m1 * 60 + s1 + ms1 / 1000, h2 * 3600 + m2 * 60 + s2 + ms2 / 1000, "\n".join(lines[2:])))
    return cues


class TunnelingShort(SenecaScene):
    eq_size = 64
    text_size = 44

    def construct(self):
        P = self.palette
        xs, frames, refl, trans = qt.simulate(x0=X0, window=WIN, complex_frames=True)
        nf = len(frames)

        # ------------------------------------------------ persistent layers: headline + captions
        cues = load_srt(os.path.join(HERE, "quantum-tunneling-short.srt"))
        cap_cache = {}

        def caption():
            t = self.now
            for i, (a, b, txt) in enumerate(cues):
                if a <= t < b:
                    if i not in cap_cache:
                        words = self.text(txt, size=36, color=P["paper"], weight="BOLD", line_spacing=0.9)
                        if words.width > 7.0:
                            words.scale_to_fit_width(7.0)
                        words.move_to(DOWN * 3.85)
                        pad = SurroundingRectangle(words, buff=0.22, corner_radius=0.14, stroke_width=0,
                                                   fill_color=P["ink"], fill_opacity=0.92)
                        cap_cache[i] = VGroup(pad, words)
                    return cap_cache[i].copy()
            return VGroup()

        caps = always_redraw(caption)
        self.add(caps)

        state = {"head": VGroup(), "text": None}

        def headline(s):
            if state["text"] == s:
                return []
            new = self.text(s, size=60, weight="BOLD").move_to(UP * 4.55)
            new.scale_to_fit_width(min(new.width, 7.2))
            anims = [FadeIn(new, shift=UP * 0.15)]
            if len(state["head"]):
                anims.append(FadeOut(state["head"], shift=UP * 0.15))
            state["head"], state["text"] = new, s
            return anims

        def at(scene_id, key="from", plus=0.0):
            self.wait_until(self.cue(scene_id, key, default=self.now) + plus)

        def said(prefix):
            """Wait until the caption starting with `prefix` comes up (i.e. when that phrase is spoken)."""
            hits = [a for a, _, txt in cues if txt.replace("\n", " ").startswith(prefix)]
            if not hits:
                raise KeyError(f"no caption starts with {prefix!r}")
            self.wait_until(hits[0])

        def person(h=1.9):
            head_ = Circle(radius=h * 0.13, stroke_width=0, fill_color=P["ink"], fill_opacity=1)
            body = RoundedRectangle(width=h * 0.36, height=h * 0.62, corner_radius=h * 0.12, stroke_width=0,
                                    fill_color=P["ink"], fill_opacity=1)
            head_.next_to(body, UP, buff=h * 0.05)
            return VGroup(body, head_)

        # ------------------------------------------------ hook + mean: walking through a wall
        floor_y = -1.6
        floor = Line(LEFT * 3.8 + UP * floor_y, RIGHT * 3.8 + UP * floor_y, color=P["steel"], stroke_width=3)
        wall = Rectangle(width=0.55, height=3.6, stroke_width=0, fill_color=P["steel"], fill_opacity=1)
        wall.move_to(UP * (floor_y + 1.8))
        bricks = VGroup(*[Line(LEFT * 0.275, RIGHT * 0.275, stroke_width=2, color=P["paper"]).move_to(UP * (floor_y + 0.3 + 0.45 * k))
                          for k in range(8)])
        you = person()
        you.move_to(LEFT * 2.6 + UP * (floor_y + you.height / 2))
        you_lab = self.text("you", size=34, color=P["steel"]).next_to(you, UP, buff=0.2)
        self.play(*headline("What if you could tunnel?"), FadeIn(floor), GrowFromEdge(wall, DOWN), FadeIn(bricks),
                  FadeIn(you, shift=RIGHT * 0.2), FadeIn(you_lab), run_time=1.2)
        self.beat("hook", hold=1.0)

        at("mean")
        self.play(*headline("Walls become optional"), FadeOut(you_lab), run_time=0.5)
        home = you.get_center().copy()
        self.play(you.animate.move_to([0, home[1], 0]).set_opacity(0.45), run_time=1.0, rate_func=linear)
        self.play(you.animate.move_to([2.6, home[1], 0]).set_opacity(1.0), run_time=1.0, rate_func=linear)
        poof = VGroup(*[Line(ORIGIN, RIGHT * 0.35, stroke_width=5, color=P["signal"]).rotate(a, about_point=ORIGIN).shift(
            RIGHT * 0.45 * np.cos(a) + UP * 0.45 * np.sin(a)) for a in np.linspace(0, TAU, 8, endpoint=False)]).move_to(wall)
        self.play(FadeIn(poof, scale=0.5), run_time=0.4)
        self.play(FadeOut(poof, scale=1.5), run_time=0.4)
        self.beat("mean", hold=1.0)

        # ------------------------------------------------ take: what would it take?
        at("take")
        q = self.text("?", size=180, weight="BOLD", color=P["signal"]).move_to(UP * 3.0 + RIGHT * 1.6)
        self.play(*headline("What would it take?"), you.animate.move_to(home), FadeIn(q, scale=0.6), run_time=0.9)
        self.beat("take", hold=1.0)

        # ------------------------------------------------ odds: 10^(-10^34)
        at("odds")
        stage = VGroup(floor, wall, bricks, you)
        self.play(*headline("Your odds"), FadeOut(q), stage.animate.scale(0.55).move_to(DOWN * 1.95), run_time=0.8)
        tiny = self.text("0.000000000000…0001", size=58, weight="BOLD")
        tiny.scale_to_fit_width(7.0).move_to(UP * 3.0)
        brace = Brace(tiny[2:-1], DOWN, color=P["steel"], buff=0.1)
        zeros = self.typst("about $10^34$ zeros", size=40, color=P["steel"]).next_to(brace, DOWN, buff=0.12)
        big = self.eq("T approx 10^(-10^34)", size=84).move_to(UP * 0.5)
        fine = self.text("you as one 70 kg particle  ·  a 10 cm wall  ·  1 joule short", size=24, color=P["steel"])
        fine.scale_to_fit_width(min(fine.width, 7.2)).next_to(big, DOWN, buff=0.3)
        self.play(Write(tiny), run_time=1.4)
        self.play(GrowFromCenter(brace), FadeIn(zeros), run_time=0.7)
        self.play(FadeIn(big, scale=0.9), FadeIn(fine), run_time=0.9)
        self.beat("odds", hold=1.0)

        # ------------------------------------------------ wait: every second since the Big Bang
        at("wait")
        self.play(*headline("Keep trying"), FadeOut(VGroup(tiny, brace, zeros, big, fine)),
                  stage.animate.scale(1 / 0.55).move_to(DOWN * 0.3), run_time=0.8)
        attempts = ValueTracker(0.0)   # log10 of attempts
        AGE = 13.8e9 * 3.156e7         # seconds since the Big Bang, ~4.4e17

        def attempts_txt():
            n = int(round(10 ** attempts.get_value()))
            return self.text(f"attempts  {n:,}", size=34, weight="BOLD").move_to(UP * 3.4)

        att = always_redraw(attempts_txt)
        succ = self.text("got through  0", size=34, weight="BOLD", color=P["steel"]).move_to(UP * 2.8)
        self.add(att)
        self.play(FadeIn(succ), run_time=0.4)
        home = you.get_center().copy()
        hit = np.array([wall.get_left()[0] - you.width / 2, home[1], 0])
        span = max(3.0, self.cue("wait", "end", default=self.now + 5) - self.now)
        bounces = 7
        for k in range(bounces):
            d = span / bounces
            self.play(you.animate.move_to(hit), attempts.animate.set_value(math.log10(AGE) * (k + 0.5) / bounces),
                      rate_func=rush_into, run_time=d * 0.45)
            self.play(you.animate.move_to(home), attempts.animate.set_value(math.log10(AGE) * (k + 1) / bounces),
                      rate_func=rush_from, run_time=d * 0.55)
        self.beat("wait", hold=0.8)

        # ------------------------------------------------ mass: you vs an electron
        at("mass")
        att.clear_updaters()
        self.play(*headline("Mass is the problem"), FadeOut(VGroup(att, succ, floor, wall, bricks)),
                  you.animate.move_to(LEFT * 1.9 + UP * 1.4), run_time=0.8)
        you_kg = self.text("you", size=36, weight="BOLD").next_to(you, DOWN, buff=0.3)
        you_m = self.eq("70 \"kg\"", size=48, color=P["steel"]).next_to(you_kg, DOWN, buff=0.15)
        dot = Dot(radius=0.07, color=P["signal"]).move_to([1.9, you.get_center()[1], 0])
        halo = Circle(radius=0.35, color=P["signal"], stroke_width=3).move_to(dot)
        e_lab = self.text("an electron", size=36, weight="BOLD").move_to([1.9, you_kg.get_center()[1], 0])
        e_m = self.eq("9 times 10^(-31) \"kg\"", size=48, color=P["steel"]).next_to(e_lab, DOWN, buff=0.15)
        ratio = self.typst("about $10^32$ times lighter", size=40).move_to(DOWN * 1.9)
        self.play(FadeIn(you_kg), FadeIn(you_m), run_time=0.6)
        self.play(GrowFromCenter(dot), Create(halo), FadeIn(e_lab), FadeIn(e_m), run_time=0.8)
        self.play(FadeIn(ratio, shift=UP * 0.15), run_time=0.6)
        self.beat("mass", hold=1.0)

        # ------------------------------------------------ wave + split: the real simulation
        at("wave")
        ax = Axes(x_range=[WIN[0], WIN[1], 8], y_range=[-0.62, 0.62, 0.2], x_length=7.4, y_length=4.4, tips=False,
                  axis_config={"color": P["steel"], "stroke_width": 0, "include_ticks": False})
        ax.move_to(UP * 0.35)
        base = ax.c2p(0, 0)[1]
        ground = Line(ax.c2p(WIN[0], 0), ax.c2p(WIN[1], 0), color=P["steel"], stroke_width=3)
        x0p, x1p = ax.c2p(0, 0)[0], ax.c2p(qt.L, 0)[0]
        barrier = Rectangle(width=x1p - x0p, height=4.0, stroke_width=0, fill_color=P["ink"], fill_opacity=1)
        barrier.move_to([(x0p + x1p) / 2, base, 0])
        amp = 2.2 / 0.6
        clock = ValueTracker(0)
        grow = ValueTracker(0.0)

        def psi_now():
            s = clock.get_value()
            i = int(np.floor(s))
            f = s - i
            return frames[min(i, nf - 1)] * (1 - f) + frames[min(i + 1, nf - 1)] * f

        px = np.array([ax.c2p(x, 0)[0] for x in xs])
        far = xs > qt.L

        def env():
            p = np.abs(psi_now()) * amp * grow.get_value()
            pts = [np.array([a, base + b, 0]) for a, b in zip(np.concatenate([px, px[::-1]]), np.concatenate([p, -p[::-1]]))]
            return Polygon(*pts, stroke_width=0, fill_color=P["steel"], fill_opacity=0.18)

        def line(mask, color):
            def make():
                v = psi_now().real * amp * grow.get_value()
                return VMobject(stroke_color=color, stroke_width=3.5).set_points_as_corners(
                    [np.array([a, base + y, 0]) for a, y in zip(px[mask], v[mask])])
            return make

        w_env, w_near, w_far = always_redraw(env), always_redraw(line(~far, P["ink"])), always_redraw(line(far, P["signal"]))
        self.play(*headline("Electrons are waves"), FadeOut(VGroup(you, you_kg, you_m, e_lab, e_m, ratio, halo)),
                  dot.animate.move_to([ax.c2p(X0, 0)[0], base, 0]), FadeIn(ground), GrowFromEdge(barrier, DOWN), run_time=1.0)
        self.add(w_env, w_near, w_far)
        self.play(dot.animate.scale(0.2).set_opacity(0), grow.animate.set_value(1.0), run_time=1.2)
        self.remove(dot)

        said("Watch an electron's wave")
        sim_end = self.cue("split", "end", default=self.now + 9)
        run = max(4.0, sim_end - self.now)
        split_at = self.cue("split", "from", default=self.now + run * 0.4)

        def pct(series, label, color, y):
            def make():
                s = clock.get_value()
                i = int(np.floor(s))
                f = s - i
                v = series[min(i, nf - 1)] * (1 - f) + series[min(i + 1, nf - 1)] * f
                return self.text(f"{label}  {100 * v:.1f}%", size=40, color=color, weight="BOLD").move_to([0, y, 0])
            return make

        back = always_redraw(pct(refl, "bounced back", P["steel"], 3.35))
        thru = always_redraw(pct(trans, "got through", P["ink"], 2.75))
        chip = always_redraw(lambda: SurroundingRectangle(thru, buff=0.12, corner_radius=0.1, stroke_width=0,
                                                          fill_color=P["signal"], fill_opacity=0.45))
        first = max(0.5, split_at - self.now)
        frac = min(0.9, first / run)
        self.play(clock.animate.set_value((nf - 1) * frac), run_time=first, rate_func=linear)
        # live counters change glyph count as they tick, so they appear directly rather than fading in
        self.add(back, chip, thru)
        self.play(*headline("Some gets through"), clock.animate.set_value((nf - 1) * min(1.0, frac + 0.6 / run)),
                  run_time=0.6, rate_func=linear)
        self.play(clock.animate.set_value(nf - 1), run_time=max(0.5, sim_end - self.now), rate_func=linear)
        self.beat("split", hold=0.8)

        # ------------------------------------------------ inside: fades, never vanishes
        at("inside")
        for m in (w_env, w_near, w_far, back, thru, chip):
            m.clear_updaters()
        ax2 = Axes(x_range=[-4.5, 6.0, 1], y_range=[0, 2.1, 0.5], x_length=7.4, y_length=3.6, tips=False,
                   axis_config={"color": P["steel"], "stroke_width": 0, "include_ticks": False})
        ax2.shift(DOWN * (ax2.c2p(0, 0)[1] + 1.4))
        zs = np.linspace(-4.5, 6.0, 900)
        mag, _ = qt.stationary(zs)
        b0, b1 = ax2.c2p(0, 0), ax2.c2p(qt.L, 0)
        slab = Rectangle(width=b1[0] - b0[0], height=4.0, stroke_width=0, fill_color=P["ink"], fill_opacity=0.14)
        slab.move_to([(b0[0] + b1[0]) / 2, b0[1] + 2.0, 0])
        ground2 = Line(ax2.c2p(-4.5, 0), ax2.c2p(6.0, 0), color=P["steel"], stroke_width=3)
        steady = VMobject(stroke_color=P["ink"], stroke_width=5).set_points_smoothly([ax2.c2p(x, a) for x, a in zip(zs, mag)])
        ins = (zs >= 0) & (zs <= qt.L)
        fade = VMobject(stroke_color=P["signal"], stroke_width=12).set_points_smoothly(
            [ax2.c2p(x, a) for x, a in zip(zs[ins], mag[ins])])
        right = zs > qt.L
        left_over = VMobject(stroke_color=P["signal"], stroke_width=12).set_points_smoothly(
            [ax2.c2p(x, a) for x, a in zip(zs[right], mag[right])])
        zoom_tag = self.text("zoomed in on the wall", size=30, color=P["steel"]).move_to(UP * 3.2)
        self.play(FadeOut(VGroup(w_env, w_near, w_far, back, thru, chip, barrier, ground)), *headline("Fades, never vanishes"),
                  run_time=0.7)
        self.play(FadeIn(slab), Create(ground2), FadeIn(zoom_tag), run_time=0.6)
        self.play(Create(steady), run_time=1.8, rate_func=linear)
        self.play(Create(fade), run_time=0.9)
        said("Whatever is left")
        self.play(Create(left_over), run_time=0.9)
        self.beat("inside", hold=0.8)

        # ------------------------------------------------ math1: psi ~ e^{-kappa x}
        at("math1")
        mini = VGroup(slab, ground2, steady, fade, left_over)
        self.play(*headline("The math"), FadeOut(zoom_tag), mini.animate.scale(0.5).move_to(DOWN * 1.9), run_time=0.8)
        m1 = self.eq("psi(x) prop e^(-kappa x)", size=80).move_to(UP * 2.6)
        m1_note = self.text("how the wave fades inside the wall", size=28, color=P["steel"]).next_to(m1, DOWN, buff=0.25)
        self.play(Write(m1), run_time=1.3)
        self.play(FadeIn(m1_note), run_time=0.6)
        self.beat("math1", hold=0.8)

        # ------------------------------------------------ math2: kappa
        at("math2")
        m2 = self.eq("kappa = sqrt(2 {{ m : m }} {{ (V - E) : gap }}) / ħ", size=80).move_to(UP * 0.55)
        m2.select("m").set_color(P["signal"])
        m2.select("gap").set_color(P["steel"])
        m_tag = VGroup(self.eq("m", size=40, color=P["signal"]), self.text("= your mass", size=28, weight="BOLD")).arrange(RIGHT, buff=0.15)
        gap_tag = VGroup(self.eq("V - E", size=40, color=P["steel"]),
                         self.text("= energy gap", size=28, weight="BOLD", color=P["steel"])).arrange(RIGHT, buff=0.15)
        VGroup(m_tag, gap_tag).arrange(RIGHT, buff=0.6).next_to(m2, DOWN, buff=0.3)
        self.play(FadeOut(mini), FadeOut(m1_note), m1.animate.scale(0.75).move_to(UP * 3.0), run_time=0.6)
        self.play(Write(m2), run_time=1.3)
        self.play(FadeIn(m_tag, shift=UP * 0.1), FadeIn(gap_tag, shift=UP * 0.1), run_time=0.6)
        self.beat("math2", hold=0.6)

        # ------------------------------------------------ math3: T ~ e^{-2 kappa L}
        at("math3")
        m3 = self.eq("T approx e^(-2 kappa {{ L : L }})", size=96).move_to(DOWN * 1.95)
        m3.select("L").set_color(P["signal"])
        box = SurroundingRectangle(m3, color=P["signal"], buff=0.28, corner_radius=0.14, stroke_width=5)
        l_tag = self.text("wall thickness", size=28, weight="BOLD").next_to(box, DOWN, buff=0.15)
        self.play(Write(m3), run_time=1.3)
        self.play(Create(box), FadeIn(l_tag), run_time=0.7)
        self.beat("math3", hold=0.8)

        # ------------------------------------------------ plug: electron vs you
        at("plug")
        self.play(*headline("Plug in the numbers"), FadeOut(VGroup(m1, m2, m_tag, gap_tag, l_tag)),
                  VGroup(m3, box).animate.scale(0.7).move_to(UP * 3.25), run_time=0.8)

        def card(title, given, two_kl, result, y, hot):
            t_ = self.text(title, size=38, weight="BOLD")
            g_ = self.text(given, size=26, color=P["ink"] if hot else P["steel"])
            k_ = self.eq(two_kl, size=46)
            r_ = self.eq(result, size=60)
            col = VGroup(t_, g_, k_, r_).arrange(DOWN, buff=0.2)
            bg = SurroundingRectangle(col, buff=0.3, corner_radius=0.16, stroke_width=0,
                                      fill_color=P["signal"] if hot else P["card"], fill_opacity=0.5 if hot else 1)
            bg.stretch_to_fit_width(7.2)
            return VGroup(bg, col).move_to(UP * y)

        one_in = f"{round(math.exp(ELECTRON), -3):,.0f}"
        c1 = card("an electron", "9×10⁻³¹ kg  ·  1 eV short  ·  1 nm barrier",
                  f"2 kappa L approx {ELECTRON:.0f}", f"T approx \"1 in {one_in}\"", 0, True)
        c2 = card("you", "70 kg  ·  1 joule short  ·  10 cm wall",
                  "2 kappa L approx 2 times 10^34", "T approx 10^(-10^34)", 0, False)
        cards = VGroup(c1, c2).arrange(DOWN, buff=0.3)
        if cards.height > 5.5:
            cards.scale_to_fit_height(5.5)
        cards.move_to(UP * (2.55 - 3.15) / 2 + UP * 0.0).align_to(UP * 2.55, UP)
        self.play(FadeIn(c1, shift=UP * 0.2), run_time=0.8)
        said("For you, it's")
        self.play(FadeIn(c2, shift=UP * 0.2), run_time=0.8)
        self.beat("plug", hold=0.8)

        # ------------------------------------------------ close
        at("close")
        title = self.text("Quantum\ntunneling", size=96, weight="BOLD", line_spacing=0.85).move_to(UP * 2.2)
        body = RoundedRectangle(width=2.2, height=1.45, corner_radius=0.15, stroke_width=0, fill_color=P["ink"], fill_opacity=1)
        pins = VGroup(*[Rectangle(width=0.12, height=0.28, stroke_width=0, fill_color=P["steel"], fill_opacity=1)
                        .move_to(body.get_top() + RIGHT * dx + UP * 0.1) for dx in np.linspace(-0.85, 0.85, 6)])
        pins_b = pins.copy().flip(RIGHT).move_to(body.get_bottom() + DOWN * 0.1)
        mem = VGroup(pins, pins_b, body).move_to(DOWN * 1.2)
        mem_lab = self.text("phone memory", size=32, weight="BOLD", color=P["steel"]).next_to(mem, DOWN, buff=0.25)
        spark = VGroup(*[Dot(radius=0.06, color=P["signal"]).move_to(mem.get_center() + LEFT * 0.7 + RIGHT * 0.28 * k)
                         for k in range(6)])
        self.play(FadeOut(VGroup(c1, c2, m3, box)), FadeOut(state["head"]), run_time=0.5)
        self.play(FadeIn(title, shift=UP * 0.2), FadeIn(mem), FadeIn(mem_lab), run_time=1.0)
        self.play(LaggedStart(*[Flash(d, color=P["signal"], line_length=0.12, flash_radius=0.15) for d in spark],
                              lag_ratio=0.25), run_time=1.6)
        self.beat("close", hold=2.5)
        self.remove(caps)
