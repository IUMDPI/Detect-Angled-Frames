#!/bin/env python
"""
Copyright 2019 Trustees of Indiana University
This file is distributed under the Apache 2 License

Programmed by Brian Wheeler (bdwheele@indiana.edu)

-------

Take the left two pixels of a series of images in order to produce
an image where the perforation edges are visible.  This can
be used to tweak the --perf-line-pct parameter on
detect_angled_frames


"""
from PIL import Image, ImageDraw, ImageColor
import sys

band_width = 2
high_perf = 480 * 0.1
low_perf = 480 * 0.9


if __name__ == "__main__":
    out = Image.new("RGB", (len(sys.argv) * band_width, 480))
    x = 0
    for file in sys.argv[1:]:
        img = Image.open(file)
        dar = img.size[0] / img.size[1]
        new_x = int(dar * 480)
        print(f"Orig: {img.size}, new_x: {new_x}, dar: {dar}")
        resized = img.resize((new_x, 480))
        band = resized.crop((0, 0, band_width, 480))
        out.paste(band, (x, 0))
        x += band_width

    # draw the suggested perf lines
    red = ImageColor.getcolor("red", "RGB")
    draw = ImageDraw.Draw(out)
    draw.line((0, high_perf, out.size[0], high_perf), red)
    draw.line((0, low_perf, out.size[0], low_perf), red)

    out.save("perf_bands.png")


        
        