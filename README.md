# A7 IV open gate: field test kit

For the Sony A7 IV on firmware 6.02. Writes temporary settings into the camera's memory only; a cold boot (battery out for
10 seconds) returns it to stock.

android/A7IV-OpenGate.apk: the phone app (USB-C to the camera) both 4K and 5.7K options.
windows/open_gate_4k.cmd: 4K open gate, 3840x2560, rear screen 3:2, C3 de-squeeze preview cycle.
windows/open_gate_5.7k.cmd: 5.7K open gate, 5760x3840, rear screen 3:2, C3 de-squeeze preview cycle.

Windows, once: run "windows/setup.cmd", then install the libusb-win32 driver for the camera with Zadig (camera on, USB
Connection Mode: Mass Storage; again once it has switched to service mode).
