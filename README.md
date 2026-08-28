# SCPI — Spectral Color Pace Index

SCPI is a small command-line tool that estimates the **perceived musical pace** of an audio track from its spectral color distribution.

It is **not a BPM detector**.

Traditional BPM tools attempt to identify a periodic beat or metrical pulse. SCPI instead analyses the spectral structure of the complete recording and produces a numeric pace index.

This distinction is particularly visible with music where a formal or detected BPM can be very different from how fast the music actually feels.

For example, a slow classical recording may receive a conventional BPM estimate well above 100 BPM while SCPI produces a much lower value.

---

## Why SCPI exists

SCPI originated in the **MohsradioZ** music-selection system.

MohsradioZ originally used conventional BPM metadata for sequencing tracks, but practical listening tests showed that BPM alone was often not a useful representation of perceived musical speed.

This was especially noticeable with:

- classical music
- ambient music
- sparse arrangements
- dub and reggae
- intros and interludes
- rhythmically complex recordings

A slow piece can contain enough regularly spaced musical events for a BPM detector to identify a high pulse rate while the recording itself still feels very slow.

SCPI was developed as an alternative metric for music selection.

The algorithm has been used on a large music archive for several years before being extracted into this standalone utility.

---

## What SCPI measures

SCPI should not be interpreted as:

```text
beats per minute
```

It is better understood as:

```text
Spectral Color Pace Index
```

A higher SCPI value generally represents a spectrally more active / faster-feeling recording.

A lower SCPI value generally represents a calmer / slower-feeling recording.

There is deliberately no requirement that SCPI and BPM agree.

For example:

```text
BPM  : 139
SCPI : 20
```

can be a completely reasonable result for a slow classical recording.

---

## Example comparison

The following examples were measured using:

- [`bpm-tag`](https://www.pogo.org.uk/~mark/bpm-tools/) — conventional BPM estimation
- [`DeepRhythm`](https://github.com/bleugreen/deeprhythm) — neural-network-based BPM estimation
- **SCPI** — Spectral Color Pace Index


The purpose of the table is **not** to show that SCPI is a better BPM detector.

It demonstrates that SCPI measures something different from conventional tempo estimation.

| Artist / Track | Genre | bpm-tag | DeepRhythm | SCPI |
|---|---|---:|---:|---:|
| Max Richter — Dream 1 | Ambient / Classical | 141.512 | 80 | **15.02** |
| Crown & Damon Grey — Moving To The Bassline | House | 124.011 | 123 | **99.67** |
| Mozart — Laudate Dominum | Classical | 139.370 | 120 | **19.64** |
| Pixies — Holiday Song | Alternative | 108.821 | 80 | **98.34** |
| The Scientist — Elasticated | Dub / Reggae | 127.605 | 128 | **67.07** |

The contrast is intentional.

One practical use case for SCPI is playlist ordering.

If a playlist should gradually move from **slow-feeling** tracks to **fast-feeling** tracks, sorting by SCPI can produce a more natural progression than sorting by BPM alone.

Conventional BPM may place a slow classical or ambient track surprisingly high because it detects a fast internal pulse or subdivision.

SCPI instead tries to reflect the overall perceived pace of the recording.

For this kind of playlist sequencing:


```
slow
  ↓
medium
  ↓
fast
```


For the two slow classical examples, conventional tempo estimators return comparatively high BPM values:

```text
Max Richter — Dream 1

bpm-tag     : 141.512
DeepRhythm  : 80
SCPI        : 15.02
```

```text
Mozart — Laudate Dominum

bpm-tag     : 139.370
DeepRhythm  : 120
SCPI        : 19.64
```

A rhythmically dense house track, meanwhile, receives a much higher SCPI value:

```text
Crown & Damon Grey — Moving To The Bassline

bpm-tag     : 124.011
DeepRhythm  : 123
SCPI        : 99.67
```

This is the basic idea behind SCPI.

---

## How it works

SCPI uses a deterministic signal-processing pipeline.

There is:

- no neural network
- no trained model
- no GPU requirement
- no database requirement

The current processing chain is:

```text
audio file
    ↓
SoX spectrogram
    ↓
ImageMagick palette remapping
    ↓
12 temporal slices
    ↓
spectral color distribution
    ↓
SCPI calculation
```

### 1. Spectrogram generation

SCPI uses SoX to generate a 1024-pixel-wide spectrogram:

```bash
sox INPUT -n spectrogram -x 1024 -r -o -
```

The spectrogram is streamed directly to ImageMagick.

No intermediate spectrogram file is required.

### 2. Spectral color reduction

The spectrogram is remapped to a fixed 12-color palette:

```text
BLACK
VERY_DARK_BLUE
VERY_DARK_MAGENTA
DARK_VIOLET
DARK_PINK
RED
PINK
DARK_ORANGE
ORANGE
YELLOW
LIGHT_YELLOW
PALE_YELLOW
```

The exact RGB palette is:

```text
#000000
#000055
#550055
#5500AA
#AA0055
#FF0000
#FF0055
#FF5500
#FFAA00
#FFFF00
#FFFF55
#FFFFAA
```

### 3. Temporal slicing

The resulting image is divided into 12 time slices:

```text
SL0 ... SL11
```

For every slice, SCPI measures the percentage occupied by each spectral color.

Black pixels are measured against the complete slice.

All other colors are normalized against the non-black part of the slice.

### 4. Pace calculation

SCPI uses slices:

```text
SL2
SL4
SL6
SL8
SL10
```

and the higher-energy palette regions:

```text
RED
PINK
DARK_ORANGE
ORANGE
YELLOW
LIGHT_YELLOW
PALE_YELLOW
```

The values are averaged and scaled to produce the final SCPI value.

The current formula is intentionally simple.

Most of the behaviour of SCPI comes from the preceding spectrogram, palette reduction, temporal slicing, and normalization steps.

---

## Supported audio formats

SCPI relies on SoX for audio decoding.

Any audio format that can be read by the installed SoX build can be processed by SCPI.

Typical examples include:

- MP3
- FLAC
- WAV
- OGG
- AIFF

Actual format support depends on how SoX was built and which codec libraries are installed on the system.

## Requirements

SCPI itself uses only the Python standard library.

External tools required:

```text
Python 3
SoX
ImageMagick
```

On Debian / Ubuntu:

```bash
sudo apt install sox libsox-fmt-all imagemagick
```

No Python packages are currently required.

---

## Installation

For the current standalone version, simply copy `scpi.py` somewhere in your path:

```bash
sudo install -m 755 scpi.py /usr/local/bin/scpi
```

Then run:

```bash
scpi "music/song.mp3"
```

Example:

```text
65.38
```

The normal output intentionally contains only the SCPI number so it can easily be used by scripts:

```bash
VALUE=$(scpi "$filename")
```

---

## Filenames and shell quoting

SCPI supports filenames containing spaces and shell-special characters.

Quote paths normally:

```bash
scpi "/storage/music/Artist - Song (Live) [2026].mp3"
```

For a filename beginning with `-`, use the standard `--` separator:

```bash
scpi -- "-strange filename.mp3"
```

Internally, SCPI does not construct shell command strings. Arguments are passed directly to SoX and ImageMagick.

---

## Non-standard SoX / ImageMagick locations

SCPI searches for the required tools in `$PATH`.

Custom locations can also be supplied:

```bash
scpi \
    --path-to-sox=/opt/sox/bin/sox \
    --path-to-convert=/opt/imagemagick/bin/convert \
    "song.mp3"
```

If either program cannot be found, SCPI prints an installation/help message instead of attempting analysis.

---

## Detailed output

For debugging or experimentation:

```bash
scpi --details "song.mp3"
```

Example:

```text
File: song.mp3
Image: 1024x513
Slices: 12
Slice width: 85
SoX: /usr/bin/sox
ImageMagick: /usr/bin/convert

SL2: RED..PY = 43.22%
SL4: RED..PY = 44.81%
SL6: RED..PY = 46.03%
SL8: RED..PY = 43.77%
SL10: RED..PY = 44.62%

Average: 44.49%
SCPI: 56.99
```

---

## Performance

SCPI is CPU-based.

On the development system, individual tracks typically complete in roughly one to several seconds depending on track length, storage performance, audio format, and CPU speed.

Example measurements:

| Track | SCPI runtime |
|---|---:|
| Max Richter — Dream 1 | 5.92 s |
| Crown & Damon Grey — Moving To The Bassline | 2.66 s |
| Mozart — Laudate Dominum | 2.00 s |
| Pixies — Holiday Song | 1.34 s |
| The Scientist — Elasticated | 1.41 s |

These measurements include audio decoding, SoX spectrogram generation, ImageMagick remapping, and SCPI analysis.

No GPU acceleration is currently used.

---

## SCPI versus BPM

SCPI and BPM should not be compared as if they were two implementations of the same measurement.

BPM attempts to describe periodic musical tempo.

SCPI attempts to describe perceived musical pace using spectral characteristics.

Depending on the recording, the two values may:

- roughly agree
- differ moderately
- differ dramatically

That behaviour is expected.

A value such as:

```text
BPM  = 140
SCPI = 15
```

does not automatically indicate an error.

It can describe a recording containing relatively fast periodic musical events while still having a very slow overall perceived pace.

---

## Current status

SCPI is currently an experimental standalone extraction of a metric originally developed for MohsradioZ.

The algorithm itself has been used operationally for music selection, but the standalone implementation is new.

At this stage the project should be considered:

```text
experimental / pre-release
```

The immediate goals are:

- reproduce the established SCPI behaviour outside MohsradioZ
- test across very different genres
- document its behaviour
- compare it with conventional BPM estimation
- determine whether the metric is useful outside its original radio-automation use case

---

## Limitations

SCPI is not intended to:

- detect beat positions
- generate a beat grid
- determine time signatures
- replace DJ beat matching
- identify downbeats
- provide a musically authoritative BPM value

SCPI is a single numeric descriptor intended primarily for **relative musical pace comparison**.

Its behaviour across very different production styles and genres still needs broader independent evaluation.

---

## History

SCPI originated as `FBPM` (FarbenBeatsPerMinute) inside MohsradioZ.

The original metric was developed after conventional BPM values proved insufficient for selecting tracks according to perceived pace.

The original processing pipeline evolved over many years and used:

- SoX spectrograms
- ImageMagick color remapping
- spectral color analysis
- temporal slicing
- database-backed music selection

In 2026 the relevant processing stages were extracted into a standalone Python implementation.

At that point the metric was renamed from `FBPM` to:

```text
SCPI — Spectral Color Pace Index
```

to avoid implying that the output represents Beats Per Minute.

---

## License

SCPI is released under the GNU General Public License v3.0.
See [LICENSE](LICENSE) for details.

---

## Author / project

SCPI was developed as part of the MohsradioZ music-selection project by fne@neudecker.net.

---

## Acknowledgements

ChatGPT helped with the cleanup and transfer of the original PHP/Bash implementation into the current standalone Python application.

The SCPI concept, processing logic, palette, spectral slicing method, and pace calculation originate from the MohsradioZ project.

SCPI relies on:

- [SoX — Sound eXchange](https://github.com/chirlu/sox) for audio decoding and spectrogram generation
- [ImageMagick](https://imagemagick.org) for spectral palette remapping

Without these projects, the standalone SCPI implementation would be considerably more complicated.
