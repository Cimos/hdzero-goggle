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

## Next
- OSD status icons restyled to the brand (36 px and 54 px sets).
- Flash on real goggles and confirm the splash timing and header look.
- Tune splash hold time or fade once seen on the OLED.

## Later
- Rebase onto each upstream release and rebuild.
- BoxPro header logo (176x48) if ever needed.
