# Video parameters

## Destinations and sizes
| Destination | Size | Flags | Notes |
|---|---|---|---|
| LinkedIn / X / Instagram feed | 1080×1080 | `--width 1080 --height 1080` | Default. Square holds the most feed space on phones and desktop. |
| LinkedIn / Instagram feed, taller | 1080×1350 (4:5) | `--width 1080 --height 1350` | Even more of a phone screen. Keep key content inside the central 1080×1080. |
| YouTube, decks, websites, email links | 1920×1080 (16:9) | `--width 1920 --height 1080` | Lay out for landscape: wide headline left, visual right. |
| Stories, Reels, Shorts, TikTok | 1080×1920 (9:16) | `--width 1080 --height 1920` | Keep the top ~250 px and bottom ~350 px clear of essentials; the app's UI covers them. |

Size the stage with `window.VIDEO.width/height`. An SVG `viewBox` matching the frame keeps coordinates simple; design one layout per aspect ratio rather than stretching one.

**Frame rate:** 30 fps is the default and right for nearly everything. 24 fps is fine for slow, illustrative pieces and is ~20% smaller. 60 fps is rarely worth the size.

## Pacing
- **Speech rate:** about **150 words per minute** overall, including pauses. Kokoro at `speed 1.0` speaks quickly (~190 wpm while talking); `--speed 0.9` with a `gap` of 0.45–0.6 s lands near 150 wpm overall. `tts.py` prints the rate.
- **Scenes:** 3–8 s each, one idea per scene, 8–20 spoken words. A 30-second video is about 75 words in 5–6 scenes; 45 seconds is about 110 words.
- **Total length:** 30–45 s for a feed post, 60–90 s for an explainer, under 60 s for Shorts/Reels.
- **Gaps:** `gap` (default 0.35 s) is the silence between lines. The picture cuts in the middle of it, so the new scene lands a beat before its line starts. Use 0.5–0.7 s for a calmer read.
- **Lead-in and tail:** `leadIn` (0.6 s) gives frame 0 a moment before the voice starts; `tail` (1.2 s) lets the last frame breathe before the video ends.
- **Hold times:** text on screen ≥ 1.5 s; the closing line or URL ≥ 2 s after it's said.

## Always captioned
Most feed video is watched with the sound off, and captions also serve viewers who are deaf or hard of hearing, in noisy places, or not native speakers. The renderer always writes `.vtt` and `.srt`:
- ≤ 2 lines per cue, ≤ 42 characters per line, cues ≤ ~6 s, split at sentence then clause boundaries, timed by each piece's share of the characters in its line (so timing is approximate within a scene, but cues never cross scene boundaries or overlap).
- **Upload the `.srt` as a caption track** on LinkedIn, YouTube, and most platforms; viewers can toggle it and it's indexed for search.
- Use `--burn-captions` when the destination can't take a caption file (some chat apps, Stories, embedded autoplay). Keep the bottom ~15% of the layout free so burned captions don't cover content.
- On-screen headlines are not captions. Keep them short and complementary to the spoken line.

## Audio loudness
- **Target −16 LUFS integrated**, true peak ≤ −1.5 dBTP, for social and web. This is the default (`--lufs -16 --true-peak -1.5`). Use `--lufs -14` for a louder YouTube-style master, or `--lufs -23` for broadcast (EBU R128).
- The renderer measures the joined narration, then applies `loudnorm` in linear mode (one fixed gain, no pumping) and resamples to 48 kHz for AAC. It re-measures the finished MP4 with `ebur128` and reports integrated loudness, loudness range, and peak.
- Narration only is the default. If you add music, mix it at least 18–20 dB under the voice and duck it while lines are spoken.

## Voices (Kokoro-82M)
Run `python3 scripts/tts.py --list-voices`. English voices, with `af_heart` and `af_bella` rated highest in Kokoro's voice card:

| Accent | Female | Male |
|---|---|---|
| American (`a`) | `af_heart` (default), `af_bella`, `af_nicole`, `af_aoede`, `af_kore`, `af_sarah`, `af_nova`, `af_sky`, `af_alloy`, `af_jessica`, `af_river` | `am_michael`, `am_fenrir`, `am_puck`, `am_echo`, `am_eric`, `am_liam`, `am_onyx`, `am_adam` |
| British (`b`) | `bf_emma`, `bf_isabella`, `bf_alice`, `bf_lily` | `bm_george`, `bm_fable`, `bm_lewis`, `bm_daniel` |

- The voices are fixed presets. There is no cloning or emotion control; pick the voice that fits and steer delivery with punctuation (commas add small pauses, periods add longer ones) and `speed`.
- English is by far the best supported. Kokoro has other languages, but they need extra phonemizer packages and aren't set up by this skill.
- Mispronounced word? Respell it phonetically in `say` (an unusual name might need something like "Sen-uh-kuh"), or rephrase. Only changed scenes re-synthesize.
- Kokoro is Apache-2.0, so the generated audio is free to use commercially.

## File size
- Flat-color motion graphics compress very well: a 35 s, 1080×1080, 30 fps video is typically 1–4 MB at the default `--crf 20`.
- Budgets: LinkedIn and X allow far more, but **≤ 10 MB** keeps uploads fast and email/chat attachments working. The renderer warns over `--budget-mb` (default 10).
- If it's over: raise `--crf` to 23–26, use `--fps 24`, or reduce full-frame motion (moving backgrounds, gradients, blur, noise, and photos are expensive).
- Audio at 128 kb/s AAC adds about 1 MB per minute.

## Format (portable everywhere)
- H.264 High profile, `yuv420p` (required by most players and platforms), AAC-LC 48 kHz, MP4 with `+faststart` so playback starts before the download finishes.
- Even dimensions are required for `yuv420p`.
- Video and audio are cut to exactly the same duration (whole frames).
