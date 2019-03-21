# Detect-Frame-Angle
A command line utility (and library) which will determine whether a 16mm frame has been digitized at an angle

```
usage: detect_angled_frames.py [-h] [--threads THREADS] [--min MIN]
                               [--outdir OUTDIR]
                               [--color_tolerance COLOR_TOLERANCE]
                               [--perf_line_pct PERF_LINE_PCT]
                               images [images ...]

positional arguments:
  images                images to process

optional arguments:
  -h, --help            show this help message and exit
  --threads THREADS     Number of threads
  --min MIN             minimum angle to report
  --outdir OUTDIR       Output directory for diagnostic images
  --color_tolerance COLOR_TOLERANCE
                        Color channel tolerance for baselight
  --perf_line_pct PERF_LINE_PCT
                        Percentage from top and bottom for perf location
```
