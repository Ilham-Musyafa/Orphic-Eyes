# Stage 5c evidence

## Step 0: exact horizontal move

Baseline `tests/fixtures/move_104.html` and after `move_74.html`: a flat-color,
borderless, square-corner 190x48 button, y=180, left 104 -> 74. Captured through
`baseline` then `compare` using local file URLs in Edge 156.0.4314.58.

Raw boxes:
```json
[{"id":1,"x":74,"y":180,"w":30,"h":48,"zone":"top-left","percent":0.141,"label":"unexpected","approved":false},{"id":2,"x":264,"y":180,"w":30,"h":48,"zone":"top-left","percent":0.141,"label":"unexpected","approved":false}]
```

Changed pixels: 2880. The union's bounds are x=74..294, width=220. Boxes bound
changed pixel clusters, not DOM elements: the overlapping flat interior does not
change. No too-narrow-box engine bug was reproduced, so no box algorithm change
was made. The original observed page/capture is unavailable: its contents and
the cause of its single 190px box are **UNVERIFIED**. Regression tests pin the
two edge strips, not an invented DOM-element union box.

Before changes: 73 tests, OK (1 Windows symlink privilege skip), Python 3.12.10.
