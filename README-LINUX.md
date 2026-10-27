# Linux build

Build the server executable on the Linux machine where it will run. PyInstaller
does not cross-compile a Linux executable from Windows.

```bash
chmod +x build_linux.sh
./build_linux.sh
./dist/linux/PcRemoteServer
```

The build creates its own `.venv-linux` environment and writes the executable
to `dist/linux/PcRemoteServer`; it does not overwrite the Windows build.

The Linux server supports TCP remote control and mDNS discovery. Bluetooth SPP
in `server.py` currently uses Windows WinRT and is not enabled in this Linux
build. Mouse input requires an active graphical desktop session. On Linux,
PyAutoGUI works best with X11; Wayland may block synthetic input. Install the
distribution's Python Tk and X11 dependencies if PyAutoGUI reports missing
system libraries (commonly `python3-tk`, `python3-xlib`, and `scrot`).
