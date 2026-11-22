# THE WORLD TODAY — Saturday 21 November 2026

A newspaper front page that sums up the world's news of Saturday
21 November 2026 in a single image: Iran's strike on US bases in
Bahrain, the capture of cartel boss "El Chapo Isidro" in Mexico, the
Russian missile strike on Zelenskyy's hometown Kryvyi Rih, COP31
climate talks running into overtime in Antalya, Wall Street sliding
into correction on the AI sell-off, and the Wolbachia mosquito trial
that cut dengue infections 69% in Brazil — plus an "Also today" box.

## How it works

`main.py` is a pure-standard-library Python 3 program. It draws the
front page (masthead, date banner, hero story, five story panels,
"Also today" box, per-story source tags) into an RGB buffer and
writes a deterministic PNG. Text is rendered from a hand-drawn 5x7
pixel font defined in the file itself (every glyph written out by
hand in this session); bold text is drawn with a one-unit horizontal
thicken. Illustrations are flat pictograms drawn from primitives
(rectangles, circles, lines, polygons). No network, no randomness,
no clock: two runs write byte-identical output.

## Run it

```sh
mkdir -p output
MAKEFUN_OUTPUT_DIR=output python3 main.py
```

That writes `output/entry.png` (1024×1024, well under the 1 MiB
limit — about 24 KB). Without `MAKEFUN_OUTPUT_DIR` it writes to
`./output/entry.png`.

## Layout

The masthead and the black date banner name the day up front, so the
image reads as one day's news even at 300 pixels across. The hero
story (Iran–Bahrain) takes the top half of the page with a
pictogram of the strike; the other five stories sit in two rows of
two panels plus a wide dengue panel beside the "Also today" box.
Every story carries its own source tag, and claims are attributed
(Iran's account of the strike, the Riemann proof claim).

## Verify it

```sh
MAKEFUN_OUTPUT_DIR=out1 python3 main.py
MAKEFUN_OUTPUT_DIR=out2 python3 main.py
cmp out1/entry.png out2/entry.png   # byte-identical
```

## Sources

See `SOURCES.md` for the reporting behind every story, with links.
