# DroneDaddy goggle branding fork

Fork of hd-zero/hdzero-goggle carrying DroneDaddy branding.

## Done
- Startup splash: DroneDaddy logo on black, shown for two seconds when the app starts (`src/core/main.c`, `mkapp/app/resource/splash.png`).
- Menu header logo replaced for Goggle and Goggle2 (`src/image/goggle*/img_logo.c`).
- Generator scripts for both images under `utilities/`.
- On-screen keyboard symbols page gained & ^ ~ | and backtick (WiFi passwords).

## Next
- Flash on real goggles and confirm the splash timing and header look.
- Tune splash hold time or fade once seen on the OLED.

## Later
- Rebase onto each upstream release and rebuild.
- BoxPro header logo (176x48) if ever needed.
