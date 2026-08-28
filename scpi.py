#!/usr/bin/env python3
# SCPI - Spectral Color Pace Index
# Copyright (C) 2026 fne@neudecker.net
#
# SPDX-License-Identifier: GPL-3.0-only

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


VERSION = "0.1.0"

SLICES = 12
SPECTROGRAM_WIDTH = 1024

# The slices used by the original MohsradioZ SCPI formula
SCPI_SLICES = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)

# RED, PINK, DO, ORANGE, YELLOW, LY, PY
SCPI_COLOR_INDEXES = (5, 6, 7, 8, 9, 10, 11)

SCPI_OFFSET = 2.0
SCPI_SCALE = 1.236111111


# ----------------------------------------------------------------------
# Exact original SCPI palette
# ----------------------------------------------------------------------

COLORS = [
    (0,   0,   0),    # BLACK
    (0,   0,  85),    # VDB
    (85,  0,  85),    # VDM
    (85,  0, 170),    # DV
    (170, 0,  85),    # DP
    (255, 0,   0),    # RED
    (255, 0,  85),    # PINK
    (255, 85,  0),    # DO
    (255, 170, 0),    # ORANGE
    (255, 255, 0),    # YELLOW
    (255, 255, 85),   # LY
    (255, 255, 170),  # PY
]

COLOR_NAMES = [
    "BLACK",
    "VDB",
    "VDM",
    "DV",
    "DP",
    "RED",
    "PINK",
    "DO",
    "ORANGE",
    "YELLOW",
    "LY",
    "PY",
]


PALETTE_TEXT = """# ImageMagick pixel enumeration: 12,1,255,rgb
0,0: (  0,  0,  0) #000000 BLACK
1,0: (  0,  0, 85) #000055 VERY_DARK_BLUE
2,0: ( 85,  0, 85) #550055 VERY_DARK_MAGENTA
3,0: ( 85,  0,170) #5500AA DARK_VIOLET
4,0: (170,  0, 85) #AA0055 DARK_PINK
5,0: (255,  0,  0) #FF0000 RED
6,0: (255,  0, 85) #FF0055 PINK
7,0: (255, 85,  0) #FF5500 DARK_ORANGE
8,0: (255,170,  0) #FFAA00 ORANGE
9,0: (255,255,  0) #FFFF00 YELLOW
10,0:(255,255, 85) #FFFF55 LIGHT_YELLOW
11,0: (255,255,170) #FFFFAA PALE_YELLOW
"""


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="SCPI perceived musical speed estimator"
    )

    parser.add_argument(
        "file",
        help="audio file to analyse"
    )

    parser.add_argument(
        "--path-to-sox",
        metavar="PATH",
        help="path or command name for SoX"
    )

    parser.add_argument(
        "--path-to-convert",
        metavar="PATH",
        help="path or command name for ImageMagick convert/magick"
    )

    parser.add_argument(
        "--details",
        action="store_true",
        help="show intermediate SCPI slice information"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"scpi {VERSION}"
    )

    return parser


# ----------------------------------------------------------------------
# TOOL LOOKUP
# ----------------------------------------------------------------------

def resolve_tool(value, candidates):
    """
    Resolve either:
      --path-to-sox=/usr/local/bin/sox

    or:
      --path-to-sox=sox

    If nothing was supplied, search PATH.
    """

    if value:
        if os.sep in value:
            path = Path(value).expanduser()

            if path.is_file() and os.access(path, os.X_OK):
                return str(path)

            return None

        return shutil.which(value)

    for candidate in candidates:
        found = shutil.which(candidate)

        if found:
            return found

    return None


# ----------------------------------------------------------------------
# PALETTE
# ----------------------------------------------------------------------

def write_palette_file():
    """
    ImageMagick -remap expects an image/palette file.

    We embed the historical palette in this script and create only this
    tiny temporary text file.

    No spectrogram PNG is written to disk.
    """

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="ascii",
        suffix=".txt",
        prefix="scpi_palette_",
        delete=False
    )

    try:
        tmp.write(PALETTE_TEXT)
        return tmp.name

    finally:
        tmp.close()


# ----------------------------------------------------------------------
# SOX -> IMAGEMAGICK PIPE
# ----------------------------------------------------------------------

def generate_remapped_ppm(
    audio_file,
    sox_bin,
    convert_bin,
    palette_file
):
    """
    Pipeline:

        audio
          |
          v
        SoX spectrogram PNG to stdout
          |
          v
        ImageMagick palette remap
          |
          v
        binary PPM to Python

    PPM is used because it is trivial to parse without Pillow,
    NumPy, OpenCV or any other Python package.
    """

    sox_cmd = [
        sox_bin,
        audio_file,
        "-n",
        "spectrogram",
        "-x",
        str(SPECTROGRAM_WIDTH),
        "-r",
        "-o",
        "-"
    ]

    imagemagick_cmd = [
        convert_bin,
        "png:-",
        "-remap",
        palette_file,
        "-depth",
        "8",
        "ppm:-"
    ]

    sox = subprocess.Popen(
        sox_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:

        imagemagick = subprocess.Popen(
            imagemagick_cmd,
            stdin=sox.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Important:
        # allow ImageMagick to see EOF when SoX finishes.
        assert sox.stdout is not None
        sox.stdout.close()

        ppm_data, imagemagick_stderr = imagemagick.communicate()

        if sox.stderr:
            sox_stderr = sox.stderr.read()
        else:
            sox_stderr = b""

        sox_rc = sox.wait()

        if sox_rc != 0:
            message = sox_stderr.decode(
                errors="replace"
            ).strip()

            raise RuntimeError(
                f"SoX failed (exit {sox_rc}):\n{message}"
            )

        if imagemagick.returncode != 0:
            message = imagemagick_stderr.decode(
                errors="replace"
            ).strip()

            raise RuntimeError(
                "ImageMagick failed "
                f"(exit {imagemagick.returncode}):\n"
                f"{message}"
            )

        if not ppm_data:
            raise RuntimeError(
                "ImageMagick returned no image data"
            )

        return ppm_data

    finally:

        if sox.poll() is None:
            sox.kill()
            sox.wait()


# ----------------------------------------------------------------------
# BASIC PPM READER
# ----------------------------------------------------------------------

def parse_ppm(data):
    """
    Read ImageMagick's binary PPM (P6) output.

    No external Python image library is required.
    """

    pos = 0
    length = len(data)

    whitespace = b" \t\r\n"

    def next_token():

        nonlocal pos

        while True:

            while (
                pos < length
                and data[pos] in whitespace
            ):
                pos += 1

            # PPM comments
            if (
                pos < length
                and data[pos] == ord("#")
            ):
                while (
                    pos < length
                    and data[pos] not in b"\r\n"
                ):
                    pos += 1

                continue

            break

        start = pos

        while (
            pos < length
            and data[pos] not in whitespace
        ):
            pos += 1

        if start == pos:
            raise ValueError(
                "Invalid PPM header"
            )

        return data[start:pos]

    magic = next_token()

    if magic != b"P6":
        raise ValueError(
            f"Expected binary PPM (P6), got {magic!r}"
        )

    width = int(next_token())
    height = int(next_token())
    maxval = int(next_token())

    if maxval != 255:
        raise ValueError(
            "Expected 8-bit PPM "
            f"(maxval 255), got {maxval}"
        )

    # Exactly one whitespace separator follows maxval.
    if (
        pos >= length
        or data[pos] not in whitespace
    ):
        raise ValueError(
            "Malformed PPM header"
        )

    if data[pos:pos + 2] == b"\r\n":
        pos += 2
    else:
        pos += 1

    expected = width * height * 3

    pixels = data[
        pos:
        pos + expected
    ]

    if len(pixels) != expected:
        raise ValueError(
            "Truncated PPM pixel data: "
            f"expected {expected} bytes, "
            f"got {len(pixels)}"
        )

    return width, height, pixels


# ----------------------------------------------------------------------
# ORIGINAL V12 COLOR / SLICE ANALYSIS
# ----------------------------------------------------------------------

def analyse_pixels(
    width,
    height,
    pixels
):
    """
    Reproduce the historical SPECTRO_V12 calculation.

    Important:
    this intentionally preserves the original slice mathematics.
    """

    slice_width = max(
        width // SLICES,
        1
    )

    counts = [
        [0] * len(COLORS)
        for _ in range(SLICES)
    ]

    palette_lookup = {
        (r << 16) | (g << 8) | b: index
        for index, (r, g, b)
        in enumerate(COLORS)
    }

    unknown_pixels = 0
    first_unknown = None

    offset = 0

    for _y in range(height):

        for x in range(width):

            r = pixels[offset]
            g = pixels[offset + 1]
            b = pixels[offset + 2]

            offset += 3

            rgb = (
                (r << 16)
                | (g << 8)
                | b
            )

            color_index = palette_lookup.get(
                rgb
            )

            if color_index is None:

                unknown_pixels += 1

                if first_unknown is None:
                    first_unknown = (
                        r,
                        g,
                        b
                    )

                continue

            slice_index = (
                x // slice_width
            )

            if slice_index >= SLICES:
                slice_index = (
                    SLICES - 1
                )

            counts[
                slice_index
            ][
                color_index
            ] += 1

    # After -remap this should never happen.
    if unknown_pixels:

        raise ValueError(
            f"ImageMagick produced "
            f"{unknown_pixels} pixels "
            f"outside the SCPI palette; "
            f"first unknown RGB="
            f"{first_unknown}"
        )

    # Preserve the original V12 denominator math.
    slice_pixels = (
        slice_width
        * height
    )

    results = []

    for slice_index in range(SLICES):

        black = counts[
            slice_index
        ][0]

        percentages = []

        for color_index, value in enumerate(
            counts[slice_index]
        ):

            if slice_pixels == 0:

                percentage = 0.0

            elif color_index == 0:

                # BLACK uses all pixels.
                percentage = (
                    value
                    * 100.0
                    / slice_pixels
                )

            else:

                # All other colors are normalized
                # against non-black pixels.
                denominator = (
                    slice_pixels
                    - black
                )

                if denominator > 0:
                    percentage = (
                        value
                        * 100.0
                        / denominator
                    )
                else:
                    percentage = 0.0

            # Preserve database precision.
            percentages.append(
                round(
                    float(percentage),
                    2
                )
            )

        results.append(
            percentages
        )

    return results


# ----------------------------------------------------------------------
# ORIGINAL SCPI FORMULA
# ----------------------------------------------------------------------

def calculate_scpi(results):
    """
    Original MohsradioZ SCPI formula:

      slices 2,4,6,8,10

      RED
      PINK
      DARK_ORANGE
      ORANGE
      YELLOW
      LIGHT_YELLOW
      PALE_YELLOW

    Average those five slice values,
    multiply by 1.236111111,
    add 2.
    """

    selected_values = []

    for slice_index in SCPI_SLICES:

        warm_colors = sum(
            results[
                slice_index
            ][
                color_index
            ]
            for color_index
            in SCPI_COLOR_INDEXES
        )

        selected_values.append(
            warm_colors
        )

    average = (
        sum(selected_values)
        / len(selected_values)
    )

    scpi = round(
        SCPI_OFFSET
        + (
            average
            * SCPI_SCALE
        ),
        2
    )

    return (
        scpi,
        selected_values,
        average
    )


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():

    parser = build_parser()

    args = parser.parse_args()

    audio_file = Path(
        args.file
    ).expanduser()

    if not audio_file.is_file():

        parser.error(
            "audio file not found: "
            f"{audio_file}"
        )

    # --------------------------------------------------------------
    # Find SoX
    # --------------------------------------------------------------

    sox_bin = resolve_tool(
        args.path_to_sox,
        ["sox"]
    )

    if not sox_bin:

        parser.error(
            "\n"
            "SoX was not found.\n"
            "\n"
            "Install it, for example on Debian/Ubuntu:\n"
            "\n"
            "  sudo apt install sox libsox-fmt-all\n"
            "\n"
            "or specify its location:\n"
            "\n"
            "  scpi --path-to-sox=/opt/sox/bin/sox "
            "\"song.mp3\"\n"
        )

    # --------------------------------------------------------------
    # Find ImageMagick
    # --------------------------------------------------------------

    convert_bin = resolve_tool(
        args.path_to_convert,
        [
            "convert",
            "magick"
        ]
    )

    if not convert_bin:

        parser.error(
            "\n"
            "ImageMagick was not found.\n"
            "\n"
            "Install it, for example on Debian/Ubuntu:\n"
            "\n"
            "  sudo apt install imagemagick\n"
            "\n"
            "or specify its location:\n"
            "\n"
            "  scpi "
            "--path-to-convert=/opt/imagemagick/bin/convert "
            "\"song.mp3\"\n"
        )

    palette_file = write_palette_file()

    try:

        ppm_data = generate_remapped_ppm(
            str(audio_file),
            sox_bin,
            convert_bin,
            palette_file
        )

        width, height, pixels = parse_ppm(
            ppm_data
        )

        results = analyse_pixels(
            width,
            height,
            pixels
        )

        scpi, selected_values, average = (
            calculate_scpi(
                results
            )
        )

    except (
        OSError,
        RuntimeError,
        ValueError
    ) as exc:

        print(
            f"scpi: error: {exc}",
            file=sys.stderr
        )

        return 1

    finally:
scpi.py 
        try:
            os.unlink(
                palette_file
            )
        except OSError:
            pass

    # --------------------------------------------------------------
    # Output
    # --------------------------------------------------------------

    if args.details:

        print(
            f"File: {audio_file}"
        )

        print(
            f"Image: "
            f"{width}x{height}"
        )

        print(
            f"Slices: {SLICES}"
        )

        print(
            f"Slice width: "
            f"{width // SLICES}"
        )

        print(
            f"SoX: {sox_bin}"
        )

        print(
            f"ImageMagick: "
            f"{convert_bin}"
        )

        print()

        for (
            slice_index,
            value
        ) in zip(
            SCPI_SLICES,
            selected_values
        ):

            print(
                f"SL{slice_index}: "
                f"RED..PY = "
                f"{value:.2f}%"
            )

        print()

        print(
            f"Average: "
            f"{average:.2f}%"
        )

        print(
            f"SCPI: "
            f"{scpi:.2f}"
        )

    else:

        # Deliberately machine-friendly:
        #
        # value=$(scpi "song.mp3")
        #
        print(
            f"{scpi:.2f}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )

