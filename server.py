import asyncio
import queue
import socket
import threading
import pyautogui
import time

from discovery import PcDiscovery


# =========================================================
# Server configuration
# =========================================================

HOST = "0.0.0.0"
PORT = 5000


# =========================================================
# mDNS / PC discovery
# =========================================================

discovery = PcDiscovery(PORT)
discovery.start()


# =========================================================
# PyAutoGUI configuration
# =========================================================

pyautogui.PAUSE = 0

# PyAutoGUI controls one shared desktop. Serialize calls from client threads so
# movement, button transitions, and scrolling cannot interleave unpredictably.
input_lock = threading.Lock()

MOUSE_BUTTONS = {"left", "right", "middle"}
# All clients control one desktop, so track physical button ownership globally.
mouse_button_owners = {button: set() for button in MOUSE_BUTTONS}


def parse_mouse_button(value):
    """Return a supported mouse button name, or raise ValueError."""
    button = value.strip().lower()
    if button not in MOUSE_BUTTONS:
        raise ValueError(f"unsupported mouse button: {value}")
    return button


# =========================================================
# Client tracking
# =========================================================

clients_lock = threading.Lock()

active_clients = set()


# =========================================================
# Server shutdown event
# =========================================================

server_stop_event = threading.Event()

# =========================================================
# Handle one Android client
# =========================================================

def handle_client(connection, address, transport="tcp"):

    print()
    print(
        f"[CLIENT] Connected: {address}"
    )

    # -----------------------------------------------------
    # TCP configuration
    # -----------------------------------------------------

    if transport == "tcp":
        try:
            connection.settimeout(1.0)
            connection.setsockopt(
                socket.IPPROTO_TCP,
                socket.TCP_NODELAY,
                1
            )
        except Exception as e:
            print(
                f"[CLIENT] TCP socket option error: "
                f"{type(e).__name__}: {e}"
            )


    # -----------------------------------------------------
    # Register client
    # -----------------------------------------------------

    with clients_lock:

        active_clients.add(
            connection
        )

        print(
            f"[CLIENT] Active clients: "
            f"{len(active_clients)}"
        )


    # -----------------------------------------------------
    # TCP receive accumulator
    #
    # IMPORTANT:
    # This is your existing working accumulator.
    # -----------------------------------------------------

    buffer = ""


    try:

        while not server_stop_event.is_set():

            # -------------------------------------------------
            # Receive TCP data
            # -------------------------------------------------

            try:

                data = connection.recv(
                    4096
                )

            except socket.timeout:

                # Give Python a chance to process
                # shutdown while waiting for data.
                continue


            # -------------------------------------------------
            # Client disconnected
            # -------------------------------------------------

            if not data:

                print(
                    "[CLIENT] Client disconnected"
                )

                break


            # -------------------------------------------------
            # Decode received bytes
            # -------------------------------------------------

            buffer += data.decode(
                "utf-8",
                errors="replace"
            )


            # -------------------------------------------------
            # Process complete lines
            # -------------------------------------------------

            while "\n" in buffer:

                message, buffer = buffer.split(
                    "\n",
                    1
                )

                message = message.strip()


                if not message:

                    continue


                print(
                    f"[RX] {message}"
                )


                # -------------------------------------------------
                # Split command
                # -------------------------------------------------

                parts = message.split("|")

                command = parts[0]


                # =================================================
                # MOUSE_MOVE
                # =================================================

                if command == "MOUSE_MOVE":

                    try:

                        dx = int(
                            parts[1]
                        )

                        dy = int(
                            parts[2]
                        )

                    except (
                        IndexError,
                        ValueError
                    ) as e:

                        print(
                            "[PY] Invalid "
                            f"MOUSE_MOVE: {message} "
                            f"({e})"
                        )

                        continue


                    recv_time = (
                        time.perf_counter()
                    )


                    with input_lock:
                        pyautogui.moveRel(dx, dy)


                    done_time = (
                        time.perf_counter()
                    )


                    processing_ms = (
                        done_time -
                        recv_time
                    ) * 1000


                    print(
                        f"[PY] MOUSE "
                        f"dx={dx} "
                        f"dy={dy} "
                        f"processing="
                        f"{processing_ms:.3f}ms"
                    )


                # =================================================
                # LEFT CLICK
                # =================================================

                elif command in {"MOUSE_LEFT_CLICK", "MOUSE_LEFT"}:
                    with input_lock:
                        pyautogui.click(button="left")


                # =================================================
                # RIGHT CLICK
                # =================================================

                elif command in {"MOUSE_RIGHT_CLICK", "MOUSE_RIGHT"}:
                    with input_lock:
                        pyautogui.click(button="right")


                # =================================================
                # MIDDLE CLICK
                # =================================================

                elif command == "MOUSE_MIDDLE_CLICK":
                    with input_lock:
                        pyautogui.click(button="middle")


                # =================================================
                # MOUSE_BUTTON_DOWN / MOUSE_BUTTON_UP
                # Accept generic commands as well as button-specific
                # aliases, for drag and held-button gestures.
                # =================================================

                elif command in {
                    "MOUSE_BUTTON_DOWN", "MOUSE_BUTTON_UP",
                    "MOUSE_DOWN", "MOUSE_UP",
                    "MOUSE_LEFT_DOWN", "MOUSE_LEFT_UP",
                    "MOUSE_RIGHT_DOWN", "MOUSE_RIGHT_UP",
                    "MOUSE_MIDDLE_DOWN", "MOUSE_MIDDLE_UP",
                }:

                    try:
                        if command in {"MOUSE_BUTTON_DOWN", "MOUSE_BUTTON_UP"}:
                            button = parse_mouse_button(parts[1])
                            transition = command.rsplit("_", 1)[1]
                        elif command in {"MOUSE_DOWN", "MOUSE_UP"}:
                            button = parse_mouse_button(parts[1])
                            transition = command.rsplit("_", 1)[1]
                        else:
                            button_name, transition = command[len("MOUSE_"):].rsplit("_", 1)
                            button = parse_mouse_button(button_name)
                        if transition not in {"DOWN", "UP"}:
                            raise ValueError("invalid button transition")
                    except (IndexError, ValueError) as e:
                        print(f"[PY] Invalid mouse button event: {message} ({e})")
                        continue

                    with input_lock:
                        if transition == "DOWN":
                            owners = mouse_button_owners[button]
                            if not owners:
                                pyautogui.mouseDown(button=button)
                            owners.add(connection)
                        else:
                            owners = mouse_button_owners[button]
                            was_owner = connection in owners
                            owners.discard(connection)
                            if was_owner and not owners:
                                pyautogui.mouseUp(button=button)


                # =================================================
                # MOUSE_SCROLL
                # =================================================

                elif command in {"MOUSE_SCROLL", "SCROLL"}:

                    try:
                        if command == "SCROLL":
                            # Compatibility with the older Android serializer,
                            # which sends one vertical scroll amount.
                            dx = 0
                            dy = int(parts[1])
                        else:
                            dx = int(parts[1])
                            dy = int(parts[2])

                    except (
                        IndexError,
                        ValueError
                    ) as e:

                        print(
                            "[PY] Invalid "
                            f"{command}: {message} "
                            f"({e})"
                        )

                        continue


                    with input_lock:
                        if dx:
                            pyautogui.hscroll(dx)
                        if dy:
                            pyautogui.scroll(dy)


                # =================================================
                # KEY_DOWN
                # =================================================

                elif command == "KEY_DOWN":

                    try:

                        key = parts[1]

                    except IndexError:

                        print(
                            f"[PY] Invalid "
                            f"KEY_DOWN: {message}"
                        )

                        continue


                    pyautogui.keyDown(
                        key
                    )


                # =================================================
                # KEY_UP
                # =================================================

                elif command == "KEY_UP":

                    try:

                        key = parts[1]

                    except IndexError:

                        print(
                            f"[PY] Invalid "
                            f"KEY_UP: {message}"
                        )

                        continue


                    pyautogui.keyUp(
                        key
                    )


                # =================================================
                # HELLO
                # =================================================

                elif command == "HELLO":

                    print(
                        "[PY] HELLO received"
                    )


                # =================================================
                # UNKNOWN COMMAND
                # =================================================

                else:

                    print(
                        f"[PY] Unknown command: "
                        f"{command}"
                    )


    # =========================================================
    # Client connection reset
    # =========================================================

    except ConnectionResetError:

        print(
            "[CLIENT] Connection reset by client"
        )


    # =========================================================
    # Broken pipe
    # =========================================================

    except BrokenPipeError:

        print(
            "[CLIENT] Broken pipe"
        )


    # =========================================================
    # Ctrl+C
    # =========================================================

    except KeyboardInterrupt:

        raise


    # =========================================================
    # Other client error
    # =========================================================

    except Exception as e:

        print(
            f"[CLIENT] Error: "
            f"{type(e).__name__}: {e}"
        )


    # =========================================================
    # Client cleanup
    # =========================================================

    finally:

        # A disconnected client may have ended a drag without sending UP.
        # Release a physical button only after its last client lets go.
        with input_lock:
            for button, owners in mouse_button_owners.items():
                if connection in owners:
                    owners.discard(connection)
                    if not owners:
                        try:
                            pyautogui.mouseUp(button=button)
                        except Exception as e:
                            print(f"[PY] Could not release {button} mouse button: {e}")

        with clients_lock:

            active_clients.discard(
                connection
            )

            print(
                f"[CLIENT] Active clients: "
                f"{len(active_clients)}"
            )


        try:

            connection.shutdown(
                socket.SHUT_RDWR
            )

        except Exception:

            pass


        try:

            connection.close()

        except Exception:

            pass


        print(
            f"[CLIENT] Connection closed: "
            f"{address}"
        )


# =========================================================
# Main server
# =========================================================

BLUETOOTH_SERVICE_UUID = "00001101-0000-1000-8000-00805F9B34FB"
BLUETOOTH_SERVICE_NAME = "PCRemote"


def run_bluetooth_server():
    """Advertise the Android app's standard SPP service through Windows WinRT."""
    try:
        asyncio.run(_run_bluetooth_server())
    except ImportError as error:
        print(f"[BLUETOOTH] Disabled: install WinRT dependencies from requirements.txt ({error})")
    except Exception as error:
        if not server_stop_event.is_set():
            print(f"[BLUETOOTH] Listener failed: {type(error).__name__}: {error}")


class BluetoothConnectionAdapter:
    """Expose a WinRT stream socket as the blocking interface handle_client uses."""

    def __init__(self, winrt_socket):
        self.winrt_socket = winrt_socket
        self.incoming = queue.Queue()
        self.pending = bytearray()
        self.closed = False

    def settimeout(self, _timeout):
        pass

    def setsockopt(self, *_args):
        pass

    def feed(self, data):
        if data:
            self.incoming.put(data)

    def finish(self):
        self.incoming.put(None)

    def recv(self, size):
        while not self.pending:
            try:
                chunk = self.incoming.get(timeout=1.0)
            except queue.Empty:
                raise socket.timeout()
            if chunk is None:
                return b""
            self.pending.extend(chunk)
        data = bytes(self.pending[:size])
        del self.pending[:size]
        return data

    def shutdown(self, _how):
        self.close()

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.winrt_socket.close()
            except Exception:
                pass
            self.finish()


async def _run_bluetooth_server():
    from winrt.windows.devices.bluetooth.rfcomm import (
        RfcommServiceId,
        RfcommServiceProvider,
    )
    from winrt.windows.networking.sockets import (
        SocketProtectionLevel,
        StreamSocketListener,
    )
    from winrt.windows.storage.streams import (
        DataReader,
        InputStreamOptions,
        UnicodeEncoding,
    )

    loop = asyncio.get_running_loop()
    incoming = asyncio.Queue()
    listener = None
    provider = None
    event_token = None
    advertising = False
    stage = "creating RFCOMM provider"
    try:
        listener = StreamSocketListener()
        provider = await RfcommServiceProvider.create_async(RfcommServiceId.serial_port)

        def on_connection_received(_sender, event_args):
            loop.call_soon_threadsafe(incoming.put_nowait, event_args.socket)

        stage = "registering connection listener"
        event_token = listener.add_connection_received(on_connection_received)

        stage = "binding RFCOMM service"
        await listener.bind_service_name_with_protection_level_async(
            provider.service_id.as_string(),
            SocketProtectionLevel.BLUETOOTH_ENCRYPTION_ALLOW_NULL_AUTHENTICATION,
        )
        stage = "advertising SPP service"
        provider.start_advertising_with_radio_discoverability(listener, True)
        advertising = True
        print(
            f"[BLUETOOTH] SPP service '{BLUETOOTH_SERVICE_NAME}' ready "
            f"(UUID={BLUETOOTH_SERVICE_UUID})"
        )
        print("[BLUETOOTH] Pair the Android device with this PC, then connect from the app")

        async def read_client(winrt_socket, adapter):
            reader = DataReader(winrt_socket.input_stream)
            reader.unicode_encoding = UnicodeEncoding.UTF8
            reader.input_stream_options = InputStreamOptions.PARTIAL
            try:
                while not server_stop_event.is_set():
                    count = await reader.load_async(4096)
                    if count == 0:
                        break
                    adapter.feed(reader.read_string(count).encode("utf-8"))
            except Exception as error:
                if not adapter.closed and not server_stop_event.is_set():
                    print(f"[BLUETOOTH] Client read error: {type(error).__name__}: {error}")
            finally:
                adapter.finish()
                try:
                    reader.close()
                except Exception:
                    pass
                adapter.close()

        stage = "waiting for Bluetooth clients"
        while not server_stop_event.is_set():
            try:
                winrt_socket = await asyncio.wait_for(incoming.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            peer = winrt_socket.information.remote_address.display_name
            adapter = BluetoothConnectionAdapter(winrt_socket)
            threading.Thread(
                target=handle_client,
                args=(adapter, ("Bluetooth", peer), "bluetooth"),
                name=f"PcRemoteBluetooth-{peer}",
                daemon=True,
            ).start()
            asyncio.create_task(read_client(winrt_socket, adapter))
            print(f"[BLUETOOTH] Client connected: {peer}")
    except Exception as error:
        raise RuntimeError(
            f"{stage}: {type(error).__name__}: {error}"
        ) from error
    finally:
        if provider is not None and advertising:
            try:
                provider.stop_advertising()
            except Exception as error:
                print(f"[BLUETOOTH] Advertisement cleanup error: {error}")
        if listener is not None and event_token is not None:
            try:
                listener.remove_connection_received(event_token)
            except Exception:
                pass
        if listener is not None:
            try:
                listener.close()
            except Exception:
                pass


server = None


try:

    # -----------------------------------------------------
    # Create TCP server socket
    # -----------------------------------------------------

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )


    # -----------------------------------------------------
    # Allow quick restart after shutdown
    # -----------------------------------------------------

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )


    # -----------------------------------------------------
    # Bind to ALL interfaces
    #
    # mDNS advertises the actual LAN IP.
    # TCP listens on every interface.
    # -----------------------------------------------------

    server.bind(
        (
            HOST,
            PORT
        )
    )


    # -----------------------------------------------------
    # Start listening
    # -----------------------------------------------------

    server.listen(
        10
    )


    # -----------------------------------------------------
    # Important for reliable Ctrl+C
    # -----------------------------------------------------

    server.settimeout(
        1.0
    )


    print()
    print(
        "========================================"
    )

    print(
        "        PCRemote Python Server"
    )

    print(
        "========================================"
    )

    print(
        f"Listening on: "
        f"{HOST}:{PORT}"
    )

    print(
        "mDNS discovery: ENABLED"
    )

    print(
        "Multi-client mode: ENABLED"
    )

    print(
        "Waiting for connections..."
    )

    threading.Thread(
        target=run_bluetooth_server,
        name="PcRemoteBluetoothListener",
        daemon=True,
    ).start()

    print()


    # =====================================================
    # Accept clients
    # =====================================================

    while not server_stop_event.is_set():

        try:

            connection, address = (
                server.accept()
            )


        except socket.timeout:

            # -------------------------------------------------
            # Wake up every second so Ctrl+C / shutdown
            # can be processed.
            # -------------------------------------------------

            continue


        except OSError as e:

            if server_stop_event.is_set():

                break

            print(
                f"[SERVER] Accept error: "
                f"{type(e).__name__}: {e}"
            )

            continue


        # -----------------------------------------------------
        # Start a separate thread for this client
        # -----------------------------------------------------

        client_thread = threading.Thread(
            target=handle_client,
            args=(
                connection,
                address
            ),
            name=(
                f"PcRemoteClient-"
                f"{address[0]}:"
                f"{address[1]}"
            ),
            daemon=True
        )


        client_thread.start()


        print(
            f"[SERVER] Client thread started: "
            f"{client_thread.name}"
        )


# =========================================================
# Ctrl+C
# =========================================================

except KeyboardInterrupt:

    print()
    print(
        "[SERVER] Ctrl+C detected"
    )

    print(
        "[SERVER] Server stopping..."
    )


# =========================================================
# Server error
# =========================================================

except Exception as e:

    print()
    print(
        f"[SERVER] Fatal error: "
        f"{type(e).__name__}: {e}"
    )


# =========================================================
# Shutdown
# =========================================================

finally:

    print()
    print(
        "[SERVER] Beginning cleanup..."
    )


    # -----------------------------------------------------
    # Tell client threads to stop
    # -----------------------------------------------------

    server_stop_event.set()

    # -----------------------------------------------------
    # Stop accepting new connections
    # -----------------------------------------------------

    if server is not None:

        try:

            server.close()

        except Exception as e:

            print(
                f"[SERVER] Server close error: "
                f"{type(e).__name__}: {e}"
            )


    # -----------------------------------------------------
    # Close all active client sockets
    # -----------------------------------------------------

    with clients_lock:

        clients = list(
            active_clients
        )


    print(
        f"[SERVER] Closing "
        f"{len(clients)} active client(s)..."
    )


    for connection in clients:

        try:

            connection.shutdown(
                socket.SHUT_RDWR
            )

        except Exception:

            pass


        try:

            connection.close()

        except Exception:

            pass


    # -----------------------------------------------------
    # Stop mDNS discovery
    # -----------------------------------------------------

    print(
        "[SERVER] Stopping mDNS discovery..."
    )


    try:

        discovery.stop()

    except Exception as e:

        print(
            f"[SERVER] Discovery stop error: "
            f"{type(e).__name__}: {e}"
        )


    print(
        "[SERVER] Server stopped."
    )

    print()
