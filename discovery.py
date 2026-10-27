import socket
import threading
import time

from zeroconf import Zeroconf, ServiceInfo


SERVICE_TYPE = "_pcremote._tcp.local."
SERVICE_PORT = 5000

IP_CHECK_INTERVAL = 3


class PcDiscovery:

    def __init__(self, port: int):

        self.port = port

        self.hostname = socket.gethostname()

        self.zeroconf = None
        self.service_info = None

        self.current_ip = None

        self.stop_event = threading.Event()
        self.monitor_thread = None

        self.lock = threading.Lock()

    # =========================================================
    # GET CURRENT LAN IP
    # =========================================================

    def get_local_ip(self):

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        try:

            # This does NOT actually send data.
            #
            # It simply asks Windows which local interface
            # would be used to reach this address.

            sock.connect(
                ("8.8.8.8", 80)
            )

            ip = sock.getsockname()[0]

            return ip

        except Exception:

            # Fallback

            try:

                hostname_ips = socket.gethostbyname_ex(
                    self.hostname
                )[2]

                for ip in hostname_ips:

                    if (
                        ip.startswith("192.168.")
                        or ip.startswith("10.")
                        or ip.startswith("172.")
                    ):
                        return ip

            except Exception:
                pass

            return None

        finally:

            sock.close()

    # =========================================================
    # CREATE SERVICE INFO
    # =========================================================

    def create_service_info(
        self,
        ip: str
    ):

        service_name = (
            f"{self.hostname}.{SERVICE_TYPE}"
        )

        return ServiceInfo(

            type_=SERVICE_TYPE,

            name=service_name,

            addresses=[
                socket.inet_aton(ip)
            ],

            port=self.port,

            properties={
                "name": self.hostname.encode(),
                "platform": b"Windows",
                "application": b"PCRemote"
            },

            server=f"{self.hostname}.local."

        )

    # =========================================================
    # START
    # =========================================================

    def start(self):

        with self.lock:

            if self.zeroconf is not None:
                return

            ip = self.get_local_ip()

            if ip is None:

                print(
                    "[DISCOVERY] "
                    "Could not determine local IP"
                )

                return

            print()
            print(
                "[DISCOVERY] Starting PC discovery"
            )

            print(
                f"[DISCOVERY] Hostname : "
                f"{self.hostname}"
            )

            print(
                f"[DISCOVERY] IP       : "
                f"{ip}"
            )

            print(
                f"[DISCOVERY] Port     : "
                f"{self.port}"
            )

            self.current_ip = ip

            self.zeroconf = Zeroconf()

            self.service_info = (
                self.create_service_info(ip)
            )

            try:

                self.zeroconf.register_service(
                    self.service_info
                )

            except Exception as e:

                print(
                    "[DISCOVERY] "
                    f"Registration failed: {e}"
                )

                self.zeroconf.close()

                self.zeroconf = None
                self.service_info = None

                return

            print(
                "[DISCOVERY] "
                "PCRemote service advertised"
            )

            print(
                "[DISCOVERY] "
                f"Service: {self.service_info.name}"
            )

            print()

            # Start IP monitor

            self.stop_event.clear()

            self.monitor_thread = threading.Thread(
                target=self._monitor_ip,
                name="PcRemote-IP-Monitor",
                daemon=True
            )

            self.monitor_thread.start()

    # =========================================================
    # IP MONITOR
    # =========================================================

    def _monitor_ip(self):

        print(
            "[DISCOVERY] "
            "IP monitor started"
        )

        while not self.stop_event.wait(
            IP_CHECK_INTERVAL
        ):

            try:

                new_ip = self.get_local_ip()

                if new_ip is None:
                    continue

                if new_ip == self.current_ip:
                    continue

                old_ip = self.current_ip

                print()
                print(
                    "[DISCOVERY] "
                    "IP ADDRESS CHANGED"
                )

                print(
                    f"[DISCOVERY] Old IP: "
                    f"{old_ip}"
                )

                print(
                    f"[DISCOVERY] New IP: "
                    f"{new_ip}"
                )

                self._update_service(
                    new_ip
                )

            except Exception as e:

                print(
                    "[DISCOVERY] "
                    f"IP monitor error: {e}"
                )

        print(
            "[DISCOVERY] "
            "IP monitor stopped"
        )

    # =========================================================
    # UPDATE mDNS SERVICE
    # =========================================================

    def _update_service(
        self,
        new_ip: str
    ):

        with self.lock:

            if self.zeroconf is None:
                return

            if self.service_info is None:
                return

            try:

                new_service_info = (
                    self.create_service_info(
                        new_ip
                    )
                )

                # Update the existing mDNS record.

                self.zeroconf.update_service(
                    new_service_info
                )

                self.service_info = (
                    new_service_info
                )

                self.current_ip = new_ip

                print(
                    "[DISCOVERY] "
                    "mDNS service updated"
                )

                print(
                    "[DISCOVERY] "
                    f"New IP advertised: "
                    f"{new_ip}"
                )

                print()

            except Exception as e:

                print(
                    "[DISCOVERY] "
                    f"mDNS update failed: {e}"
                )

                # If updating failed, try a full
                # unregister/register cycle.

                self._re_register(
                    new_ip
                )

    # =========================================================
    # FALLBACK RE-REGISTER
    # =========================================================

    def _re_register(
        self,
        new_ip: str
    ):

        try:

            if (
                self.zeroconf is None
                or self.service_info is None
            ):
                return

            print(
                "[DISCOVERY] "
                "Re-registering service..."
            )

            try:

                self.zeroconf.unregister_service(
                    self.service_info
                )

            except Exception:
                pass

            new_service_info = (
                self.create_service_info(
                    new_ip
                )
            )

            self.zeroconf.register_service(
                new_service_info
            )

            self.service_info = (
                new_service_info
            )

            self.current_ip = new_ip

            print(
                "[DISCOVERY] "
                "Service re-registered"
            )

            print(
                "[DISCOVERY] "
                f"New IP: {new_ip}"
            )

        except Exception as e:

            print(
                "[DISCOVERY] "
                f"Re-registration failed: {e}"
            )

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):

        print(
            "[DISCOVERY] "
            "Stopping discovery..."
        )

        self.stop_event.set()

        with self.lock:

            if self.zeroconf is None:
                return

            try:

                if self.service_info is not None:

                    self.zeroconf.unregister_service(
                        self.service_info
                    )

            except Exception as e:

                print(
                    "[DISCOVERY] "
                    f"Unregister error: {e}"
                )

            try:

                self.zeroconf.close()

            except Exception as e:

                print(
                    "[DISCOVERY] "
                    f"Zeroconf close error: {e}"
                )

            self.zeroconf = None
            self.service_info = None
            self.current_ip = None

        if self.monitor_thread is not None:

            self.monitor_thread.join(
                timeout=2
            )

            self.monitor_thread = None

        print(
            "[DISCOVERY] "
            "Discovery stopped"
        )