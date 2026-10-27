import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox


APP_NAME = "PC Remote Server"


def install():
    payload = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    source = os.path.join(payload, "PcRemoteServer.exe")
    if not os.path.isfile(source):
        messagebox.showerror(APP_NAME, "The server executable is missing from this setup package.")
        return

    install_dir = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "PCRemoteServer")
    os.makedirs(install_dir, exist_ok=True)
    target = os.path.join(install_dir, "PcRemoteServer.exe")
    try:
        shutil.copy2(source, target)
        shortcut = os.path.join(
            os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs",
            "PCRemote Server.lnk",
        )
        os.makedirs(os.path.dirname(shortcut), exist_ok=True)
        ps = (
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut}');"
            "$s.TargetPath='{target}';$s.WorkingDirectory='{directory}';"
            "$s.Description='Start the PC Remote server';$s.Save()"
        ).format(
            shortcut=shortcut.replace("'", "''"),
            target=target.replace("'", "''"),
            directory=install_dir.replace("'", "''"),
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"Installation failed:\n{exc}")
        return

    messagebox.showinfo(
        APP_NAME,
        f"Installed successfully to:\n{install_dir}\n\n"
        "Start it from the PCRemote Server shortcut in the Start menu.",
    )
    root.destroy()


root = tk.Tk()
root.title("PC Remote Server Setup")
root.resizable(False, False)
root.geometry("390x165")
tk.Label(root, text="PC Remote Server", font=("Segoe UI", 16, "bold")).pack(pady=(20, 6))
tk.Label(root, text="Install the server for the current Windows user.", font=("Segoe UI", 10)).pack()
tk.Button(root, text="Install", width=18, command=install).pack(pady=20)
root.mainloop()
