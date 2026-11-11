# Demo video builder

Copy `make_demo.py` into the folder that holds `clip1.mp4` and `clip2.mp4`, then:

```
winget install Gyan.FFmpeg      # only if ffmpeg is missing (open a new terminal after)
pip install pillow
python make_demo.py --probe     # out/probe/*_sheet_*.jpg: 1 labelled frame per second, check timestamps
python make_demo.py             # out/orphic-eyes-demo.mp4 + ffprobe report + 6 check frames in out/check/
```

All cut points, speeds and zoom focus points (`fx`/`fy`, 0..1 of the frame) are in the
`SHOTS` list at the top of the script. Edit and re-run (~1 min).
