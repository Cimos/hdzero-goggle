# DroneDaddy goggle branding fork

Fork of hd-zero/hdzero-goggle carrying DroneDaddy branding.

## Done
- Startup splash: DroneDaddy logo on black, shown for two seconds when the app starts (`src/core/main.c`, `mkapp/app/resource/splash.png`).
- Menu header logo replaced for Goggle and Goggle2 (`src/image/goggle*/img_logo.c`).
- Generator scripts for both images under `utilities/`.
- On-screen keyboard symbols page gained & ^ ~ | and backtick (WiFi passwords).
- WiFi hotspot defaults to DroneDaddy / dronedaddy, which also names the goggles on the router.
- Autoscan defaults to Last, so fresh goggles skip the full scan at boot.
- Splash holds 3 s, then fades out over 1 s.
- Menu accents in DroneDaddy blue #20A7FF and pink #F49ABA.
- Betaflight OSD font: text in the CubePilot typeface, DroneDaddy logo in the boot and arming cells (`utilities/make_osd_font.py`).
- Race-day features from bolagnaise/hdzero-goggle: recordings named after the race (MSP 0x030F from an ELRS Backpack timer), timer switches Raceband and Lowband, smooth 60 and 90 fps DVR playback.
- Goggle OSD status icons recoloured to the brand at 36 px and 54 px, grey halo removed, warning icons kept red (`utilities/make_osd_icons.py`).
- INAV and ArduPilot goggle fonts in CubePilot, including the packed decimal-point digits; INAV boot and pilot logos carry DroneDaddy. ArduPilot has no logo (`utilities/make_inav_fonts.py`, `utilities/make_ardu_fonts.py`).
- Analog OSD fonts for Betaflight, INAV and ArduPilot in `utilities/fonts/analog/`: load through Betaflight or INAV Configurator, or copy `ardupilot_sd/font0.bin` to the flight controller's SD card root.
- Flashed on Goggles 2 and confirmed working.

## Next
- Load the analog fonts onto a real OSD chip and check them over video.
- Tune splash hold time or fade if wanted.

## Later
- Rebase onto each upstream release and rebuild.
- BoxPro header logo (176x48) if ever needed.
