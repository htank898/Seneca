"""The character, as code. scene.py calls build(arm) after the armature exists.

Start from the preset, then change what the concept turnaround sheet shows: colours from the
sheet's palette, mask style, bulk, which parts exist and where. Every part is rigidly parented
to a bone (see parts.py / ai-animate's bodies.py for the bone-local axes), so whatever you add moves
with the capture. Needs both paths: --pypath ../animate/scripts --pypath scripts.
"""
import bkit as k
import parts as p


def build(arm):
    pal = p.palette(
        armor="#b8321f",   # main shell colour, sampled from the concept sheet
        accent="#e0a526",  # secondary armour / trim
        frame="#34363b",   # inner skeleton
        joint="#8d9096",   # ball joints, pistons
        eyes="#5df2ff",    # emissive eye colour
    )
    objs = p.biomech(arm, pal, bulk=1.0, style="hau", crest_fins=3, back_spikes=3)
    # Custom pieces go here, e.g. a weapon on the right hand:
    # objs.append(p.rod(arm, "hand.R", r=0.012, a=0.5, b=6.0, mat=pal["accent"], name="staff"))
    return objs, pal
