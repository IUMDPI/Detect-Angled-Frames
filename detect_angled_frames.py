#!/bin/env python
"""
Copyright 2019 Trustees of Indiana University
This file is distributed under the Apache 2 License

Programmed by Brian Wheeler (bdwheele@indiana.edu)

-------

This will detect the perforations in a frame image and 
determine the top edge of the upper perf, the
bottom edge of the lower perf, and the right edge of
both of them. 

Then, an angle can be computed to determine if the frame
was digitized at an angle.

If an output directory is specified, a marked-up version of
the frame image with the edge lines, original filename, and
the difference angle rendered onto it.
"""
import sys
from PIL import Image, ImageDraw, ImageColor, ImageFont
import math
import argparse
from multiprocessing import Pool
import os.path
import re

def same_color(c1, c2, tolerance):
    """ 
    Return true if the two colors are nearly the same, within a
    percentage tolerance
    """    
    t = int((tolerance * 256) + 0.5)
    for i in range(3):
        if abs(c1[i] - c2[i]) > t:
            return False
    return True


def detect_edges(image, baselight, x, y, tolerance):
    """
    Detect the edges of an area starting at (x,y) that
    match the baselight color within a tolerance.  

    This will return 4 lists -- one for each edge:  N, S, E, W.
    Each the list indexes are in the axis opposite the direction
    (N & S indexes are on the X axis, E & W on the Y axis) and
    the values are on the corresponding axis (N & S values are
    on the Y axis and E & W on the X axis)
    
    This algorithm uses a variant of the 4-way flood fill 
    algorithm, so it should be able to move around dirt in
    the perfs.
    """
    base_x = x
    base_y = y
    limit_x = 0.20 * image.size[0]
    limit_y = 0.20 * image.size[1]
    todo = [(x,y)]
    seen = {}
    result = {'N': [None] * image.size[0], 'S': [None] * image.size[0], 
              'E': [None] * image.size[1], 'W': [None] * image.size[1]}
    while len(todo):
        point = todo.pop()
        if not same_color(image.getpixel(point), baselight, tolerance):
            continue
        x, y = point

        # check to see if we've leaked
        # * the X coordinate can't be beyond 10% of the width from the basepoint
        # * the Y coordinate can't be beyond 10% of the height from the basepoint
        if abs(base_x - x) > limit_x:
            raise ValueError(f"Horizontal fill leak: {base_x}, {limit_x}, {x}")            
        if abs(base_y - y) > limit_y:
            raise ValueError(f"Vertical fill leak: {base_y}, {limit_y}, {y}")

        new = []
        # check north        
        if y > 0 and same_color(image.getpixel((x, y - 1)), baselight, tolerance):
            result['N'][x] = y - 1 if result['N'][x] is None else min(y - 1, result['N'][x])
            new.append((x, y - 1))
        # check south
        if y < image.size[1] - 1 and same_color(image.getpixel((x, y + 1)), baselight, tolerance):
            result['S'][x] = y + 1 if result['S'][x] is None else max(y + 1, result['S'][x])
            new.append((x, y + 1))
        # check east
        if x < image.size[0] - 1 and same_color(image.getpixel((x + 1, y)), baselight, tolerance):
            result['E'][y] = x + 1 if result['E'][y] is None else max(x + 1, result['E'][y])
            new.append((x + 1, y))
        # check west
        if x > 0 and same_color(image.getpixel((x - 1, y)), baselight, tolerance):
            result['W'][y] = x - 1 if result['W'][y] is None else min(x - 1, result['W'][y])
            new.append((x - 1, y))

        for p in new:
            if p not in seen:
                todo.append(p)
                seen[p] = 1


    return result


def decorate_perf_edges(image, edges):
    """
    Draw the edge points onto an image.  N&S are red, E&W are blue.
    """
    red = ImageColor.getcolor("red", "RGB")
    blue = ImageColor.getcolor("blue", "RGB")
    draw = ImageDraw.Draw(image, "RGB")
    for x in range(len(edges['N'])):
        for c in ('N', 'S'):
            if edges[c][x] is not None:
                draw.point((x, edges[c][x]), red)
    for y in range(len(edges['E'])):
        for c in ('E', 'W'):
            if edges[c][y] is not None:
                draw.point((edges[c][y], y), blue)


def trim_list(lst):
    """
    Remove leading and trailing None values from a list
    """
    result = lst.copy()
    while result[0] is None:
        result.pop(0)
    while result[-1] is None:
        result.pop()
    return result


def get_average(series, range_percent=1, center=False):
    """
    Get the average value from a series.  

    The range_percent selects a portion (0.0 - 1.0) of the values, 
    either from the center of the series (when center is True) or
    from the left (when center is False)

    Note:  I know this isn't perfect and there are weird corner
    cases, but for what I'm doing, it should be OK.
    """
    count = int(len(series) * range_percent) + 1
    sum = 0
    if not center:
        for x in range(count):
            if series[x] is not None:
                sum += series[x]
    else:
        mid = int(len(series) / 2)
        for x in range(int(count / 2)):
            if series[mid + x] is not None and series[mid - x] is not None:
                sum += series[mid + x] + series[mid - x]
    return int((sum / count) + 0.5)



def get_perf_corners(upper_edges, lower_edges):
    """
    Return the perf corners that will be used for determining
    the frame angle.

    Effectively, it is the NE corner of the upper perf and
    the SE corner of the lower perf.

    The corner, however, has to be computed so it doesn't
    include the curvature of the perf itself...

    This will return a single corners value, which
    consists of the two points described above.
    """

    # find the average north boundary of the upper
    # perf and the average south boundary of the
    # lower perf.  Specifically, we're going to 
    # use the average of the leftmost 75% of the points
    upper_north = get_average(trim_list(upper_edges['N']), 0.75)
    lower_south = get_average(trim_list(lower_edges['S']), 0.75)

    # find the average east boundary of the upper and
    # lower perfs.  The center 75% is used
    upper_east = get_average(trim_list(upper_edges['E']), 0.75, True)
    lower_east = get_average(trim_list(lower_edges['E']), 0.75, True)

    return [(upper_east, upper_north), (lower_east, lower_south)]


def compute_angle(points):
    """
    Compute the angle between the first two points in a list,
    """
    rise = points[0][1] - points[1][1]
    run = points[0][0] - points[1][0]
    return math.degrees(math.atan2(rise, run))




def decorate_angle_data(image, corners=None, angle=None, filename=None):
    """
    Draw the perf corners, angle, and the filename onto the image.
    """
    red = ImageColor.getcolor("magenta", "RGB")
    blue = ImageColor.getcolor("cyan", "RGB")
    green = ImageColor.getcolor("green", "RGB")
    white = ImageColor.getcolor("white", "RGB")    
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 25)    
    draw = ImageDraw.Draw(image, "RGB")
    if corners is not None:
        draw.line((0, corners[0][1], image.size[0], corners[0][1]), red)
        draw.line((0, corners[1][1], image.size[0], corners[1][1]), red)
        draw.line((corners[0][0], 0, corners[0][0], image.size[1]), blue)
        draw.line((corners[1][0], 0, corners[1][0], image.size[1]), blue)
    if filename is not None or angle is not None:
        text = ""
        if filename is not None:
            text = f"File: {filename}\n"
        if angle is not None:
            text += f"Angle: {angle:.3f}"
        corner = [image.size[0] * 0.1, image.size[1] / 2]        
        draw.multiline_text(corner, text, fill=green, font=font)
        corner[0] += 2
        corner[1] += 2
        draw.multiline_text(corner, text, fill=white, font=font)


def process_file(file, perf_line_pct, color_tolerance, output_dir=None):
    """
    Process a single file and return a data structure
    describing the result

    perf_line_pct is the percentage of the image height from the top and bottom
    that is used as a starting point when looking for the perfs  (0.0 - 0.49)

    color_tolerance is the percentage difference for a single component when
    trying to match similar colors (0.0 - 1.0)

    output_dir, if set, is where an annotated version of this image should be
    written after processing.
    """

    try:
        image = Image.open(file)
        # Get the baselight colors for the two perfs.
        # if they are different, then we're probably
        # not looking at two perfs, and we should skip the
        # image.
        upper_perf_line = int(image.size[1] * perf_line_pct)
        lower_perf_line = int(image.size[1] * (1 - perf_line_pct))
        b1 = image.getpixel((0, upper_perf_line))
        b2 = image.getpixel((0, lower_perf_line))
        if not same_color(b1, b2, color_tolerance):
            return {
                'file': file,
                'success': False,
                'message': f"The baselight colors aren't the same:  {b1}, {b2}"
            }

        # detect the edges of the upper and lower perfs
        upper_edges = detect_edges(image, b1, 0, upper_perf_line, color_tolerance)
        lower_edges = detect_edges(image, b2, 0, lower_perf_line, color_tolerance)

        # get the corners we care about
        corners = get_perf_corners(upper_edges, lower_edges)

        # get the angle between the two corners
        angle =  90 + compute_angle(corners) 

        result = {
            'file': file,
            'success': True,
            'angle': angle,
            'annotated_file': None
        }

        if output_dir is not None:
            out = os.path.join(output_dir, os.path.basename(file)) + ".png"
            decorate_perf_edges(image, upper_edges)
            decorate_perf_edges(image, lower_edges)
            decorate_angle_data(image, corners, angle, os.path.basename(file))
            image.save(out, "PNG")
            result['annotated_file'] = out

        return result
    except Exception as e:
        return {
            'file': file,
            'success': False,
            'message': e
        }

def process_file_thunk(file):
    """
    pull default values from args and call the real process_file function
    """
    return process_file(file, args.perf_line_pct, args.color_tolerance, args.outdir)



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, help="Number of threads", default=1)
    parser.add_argument("images", nargs="+", help="images to process")
    parser.add_argument("--min", type=float, default=None, help="minimum angle to report")
    parser.add_argument("--outdir", default=None, help="Output directory for diagnostic images")
    parser.add_argument("--color_tolerance", type=float, default=0.10, help="Color channel tolerance for baselight")
    parser.add_argument("--perf_line_pct", type=float, default=0.10, help="Percentage from top and bottom for perf location")
    args = parser.parse_args()

    results = []
    if args.threads == 1:
        for file in args.images:
            results.append(process_file_thunk(file))

    else:
        with Pool() as p:
            results = p.map(process_file_thunk, args.images)

    
    print(f"Processed {len(results)} files.")
    # dump out the unsuccessful ones...and drop the ones with no angle.
    nresults = []
    for r in results:
        if not r['success']:
            print(f"{r['file']} failed: {r['message']}")
        else:
            nresults.append(r)
    print(f"There are {len(nresults)} files left after filtering errors")

    nresults = [x for x in nresults if x['angle'] != 0]
    print(f"There are {len(nresults)} files left after filtering straight images")

    
    if args.min is not None:
        nresults = [x for x in nresults if abs(x['angle']) >= args.min]
        print(f"There are {len(nresults)} files left after filtering angles less than {args.min}")


    print("Results:\n=========\n")
    
    for r in sorted(nresults, key=lambda r: abs(r['angle']), reverse=True):
        m = re.search(r"MDPI_(\d+)", r['file'])
        barcode = m.group(0)
        print(f"{barcode}: {r['angle']:.3f}")

