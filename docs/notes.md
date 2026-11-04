# PHN16S-71 on Linux: measured notes

Measured on one PHN16S-71 (BIOS V1.26, Core Ultra 9 275HX, RTX 5070 Ti Laptop), Fedora 45, kernel 7.2.15.

## Firmware power profiles (acer-wmi `platform_profile`)

Load the stock `acer_wmi` with `predator_v4=1` to get `/sys/class/platform-profile`. Limits read from
`intel-rapl-mmio` (the firmware sets these, not the MSR RAPL interface) and `nvidia-smi`:

| platform_profile        | Acer name   | CPU PL1 / PL2 | GPU limit |
|-------------------------|-------------|---------------|-----------|
| `low-power`             | Eco         | 45 W / 50 W   | 70 W      |
| `quiet`                 | Quiet       | 45 W / 140 W  | 70 W      |
| `balanced`              | Balanced    | 65 W / 140 W  | 70 W      |
| `balanced-performance`  | Performance | 75 W / 140 W  | 85 W      |
| `performance`           | Turbo       | 85 W / 140 W  | 100 W     |

- **thermald**: on this CPU it only runs with `--adaptive`, and in that mode it overwrote Eco's limits
  back to 65 W / 140 W within ~3 s. Disabling thermald lets the firmware limits stand.
- **tuned / power-profiles**: tuned-ppd follows changes to `platform_profile` and does not override them.

## Mode key

The key above the keyboard sends report `04 85 ff` on the I2C HID device `1025:174B` (vendor usage page
0x88, so the kernel maps it to nothing; no input event, no ACPI event). `extras/acer-mode-key` reads the
hidraw node directly.

## Fans

- The stock `acer_wmi` does not enable fan control for this model. Loading it with
  `force_caps=0x1C20` (platform profile + hwmon + set-function-mode + PWM) exposes `pwm1`/`pwm2` and
  `pwm*_enable` (0 = max, 1 = manual, 2 = firmware auto), and they work.
- Duty → RPM: 20 % ≈ 1300, 40 % ≈ 2650, 60 % ≈ 3950, 80 % ≈ 5250, 100 % ≈ 6300.
- Firmware auto stops the fans at idle, waits ~7 s at ~97 °C before ramping, and ramps ~100 RPM/s
  (Balanced tops out ~3580 RPM, Turbo ~5480 RPM after ~60 s).
- In manual mode the EC still raises the fans when hot (a 60 % request ran ~5000 RPM at 97 °C).
- A faster custom curve did **not** improve CPU performance: the CPU sits at ~97 °C during the PL2 burst
  regardless of fan speed, then is capped by PL1. Turbo, 90 s all-core load: average CPU power 97.5 W with
  firmware fans vs 94.9 W with fans at 100 %. So the slow firmware ramp costs noise, not performance.

## Display

- Factory EDID: one timing (2560x1600 @ 240 Hz), base-block range 48–240 Hz, Adaptive Sync block 60–240 Hz.
- PSR1 is supported and active on i915.
- The panel can also be routed to the RTX (`eDP-2` on the NVIDIA card = hardware mux / Advanced Optimus).
  The Acer WMI "GPU mode" setting used by some Linux tools does not answer on this model. NVIDIA's README
  states automatic mux switching works on X11 only; no Wayland compositor supports it yet.

## Battery and sleep

- Battery health mode (~80 % charge limit): `/sys/bus/wmi/drivers/acer-wmi-battery/health_mode`
  (out-of-tree `acer-wmi-battery` module).
- Sleep is s2idle only and reaches S0ix. With the NVIDIA driver, set
  `options nvidia NVreg_EnableS0ixPowerManagement=1`.
- The RTX runtime-suspends (RTD3) at idle; note that running `nvidia-smi` wakes it for ~30 s.
