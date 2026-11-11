"""Seneca house style for Manim scenes.

Import this from a scene file (scripts/manim.py puts this folder on PYTHONPATH):

    from seneca_scene import *

    class Proof(SenecaScene):
        def construct(self):
            e = self.eq("{{ a^2 + b^2 : lhs }} = {{ c^2 : rhs }}")
            self.play(Write(e))
            self.beat("hook")          # hold until the narration for "hook" leaves the screen

What it gives you:
  PALETTE / FONT    the Seneca palette and text face; override per scene (class attributes) or globally
  SenecaScene       background + defaults, plus eq(), text(), beat(), wait_until(), cue()
  eq(expr)          Typst math (MathTypst). {{ ... : label }} groups are selectable with .select("label")
  text(s)           Pango text in the house face
  beat(id)          wait until scene `id` of an ai-video timings.json ends (falls back to `hold` seconds)
  cue(id, key)      a time from timings.json: "start"/"end" (spoken line) or "from"/"to" (on screen)

Equations use Typst math syntax, not LaTeX. See reference/math-parameters.md for a cheatsheet.
"""
import json
import os

from manim import *  # noqa: F401,F403  (re-exported so scenes need a single import)
from manim import BLACK, Mobject, MathTypst, Scene, Text, Typst, config

PALETTE = {
    "paper": "#e6eae8",   # background
    "ink": "#16191d",     # equations and text
    "steel": "#5e7a94",   # secondary terms, guides, axes
    "signal": "#f5c518",  # the one thing to look at
    "mute": "#c9d1cd",    # de-emphasized / faded
    "card": "#f7f8f7",    # panels
}
FONT = "Helvetica Neue"


def _fit_frame_to_pixels():
    """Manim keeps a 14.2 x 8 frame whatever the pixel size, which stretches square and
    portrait renders. Match the frame's aspect to the pixels, short side = 8 units, so
    font sizes read the same at 16:9, 1:1 and 9:16."""
    w, h = config.pixel_width, config.pixel_height
    if w >= h:
        config.frame_height, config.frame_width = 8.0, 8.0 * w / h
    else:
        config.frame_width, config.frame_height = 8.0, 8.0 * h / w


_fit_frame_to_pixels()


def _load_timings():
    path = os.environ.get("AI_MATH_TIMINGS")
    if not path:
        return None
    with open(path) as f:
        data = json.load(f)
    return {s["id"]: s for s in data.get("scenes", [])}


class SenecaScene(Scene):
    palette = PALETTE
    font = FONT
    eq_size = 64        # MathTypst font_size; ~64 reads well at 1080p
    text_size = 40

    def setup(self):
        super().setup()
        self.camera.background_color = self.palette["paper"]
        self._timings = _load_timings()
        # Frame-accurate clock. renderer.time only advances between play()/wait() calls, so
        # anything that reads the time mid-animation (captions, cue-driven updaters) would freeze
        # through a long hold. This invisible ticker counts frames within an animation and
        # re-syncs to renderer.time at each boundary (where updaters skip one frame's dt).
        self._clock = Mobject()
        self._clock.t = 0.0
        self._clock.add_updater(lambda m, dt: setattr(m, "t", max(m.t + dt, self.renderer.time)))
        self.add(self._clock)

    # ------------------------------------------------------------ builders
    def eq(self, expr, color=None, size=None, **kw):
        """Typst display math. Groups: "{{ a^2 + b^2 : lhs }} = {{ c^2 }}" then .select("lhs") / .select(0)."""
        return MathTypst(expr, color=color or self.palette["ink"], font_size=size or self.eq_size, **kw)

    def typst(self, markup, color=None, size=None, **kw):
        """Full Typst markup (text + $inline math$), for labels that mix words and symbols.
        Words use the house font (falling back to Typst's Libertinus); math keeps its math font."""
        kw.setdefault("typst_preamble", f'#set text(font: ("{self.font}", "Libertinus Serif"))')
        return Typst(markup, color=color or self.palette["ink"], font_size=size or self.text_size, **kw)

    def text(self, s, color=None, size=None, weight="NORMAL", **kw):
        return Text(s, font=self.font, color=color or self.palette["ink"],
                    font_size=size or self.text_size, weight=weight, **kw)

    # ------------------------------------------------------------ timing
    @property
    def now(self):
        """Seconds since the scene started, correct on every frame (use this in updaters)."""
        return max(self._clock.t, self.renderer.time)

    def wait_until(self, t):
        """Wait until absolute timeline time t (seconds). No-op if already past it."""
        dt = t - self.renderer.time   # called between animations, where renderer.time is exact
        if dt > 1 / config.frame_rate:
            self.wait(dt)

    def cue(self, scene_id, key="start", default=None):
        """A time from the ai-video timings.json passed with --timings, or `default` without one."""
        if not self._timings:
            return default
        if scene_id not in self._timings:
            raise KeyError(f"timings.json has no scene '{scene_id}' (have: {', '.join(self._timings)})")
        return self._timings[scene_id][key]

    def beat(self, scene_id, hold=2.0):
        """Hold until narration scene `scene_id` leaves the screen; without timings, wait `hold` seconds."""
        t = self.cue(scene_id, "to")
        if t is None:
            self.wait(hold)
        else:
            self.wait_until(t)
