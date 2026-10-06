# Locked weather gate

The controlled local input is:

`AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw`

Its identity, station metadata, expected SHA-256, source URL, source-year map,
and approved calendar rule are recorded in `weather_manifest.json`. The EPW is
kept out of Git; the loader hard-fails if a local copy differs from the manifest.

The raw TMYx month selections retain historical years and therefore are not
monotonic. Under `CC-001`, the loader verifies all 8,760 source month/day/hour
positions, preserves their order and original timestamps, then assigns a fixed
UTC+10 non-leap 2001 index. It hard-fails on any missing, duplicate, reordered,
leap-day, hash, size, metadata, or source-year-map mismatch.

The filename's nominal period is 2011–2025, while the EPW header reports only
five available source years, 2011–2015. Both facts must remain visible in every
run manifest; the file must not be described as fifteen complete years of
measured station meteorology.
