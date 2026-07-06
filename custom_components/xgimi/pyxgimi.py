import asyncio
import logging
from time import monotonic

import asyncudp
from bluez_peripheral.advert import Advertisement
from bluez_peripheral.util import get_message_bus

from .const import (
    ADVANCE_PORT,
    ALIVE_PORT,
    BLE_ADVERTISEMENT_TIMEOUT,
    BLE_COMPANY_ID,
    BLE_POWER_ON_REPEATS,
    BLE_POWER_ON_REPEAT_DELAY,
    BLE_SERVICE_UUID,
    COMMAND_PORT,
    PING_TIMEOUT,
    normalize_manufacturer_data,
)

_LOGGER = logging.getLogger(__name__)

_COMMANDS = {
    "ok": "KEYPRESSES:49",
    "play": "KEYPRESSES:49",
    "pause": "KEYPRESSES:49",
    "power": "KEYPRESSES:116",
    "back": "KEYPRESSES:48",
    "home": "KEYPRESSES:35",
    "menu": "KEYPRESSES:139",
    "right": "KEYPRESSES:37",
    "left": "KEYPRESSES:50",
    "up": "KEYPRESSES:36",
    "down": "KEYPRESSES:38",
    "volumedown": "KEYPRESSES:114",
    "volumeup": "KEYPRESSES:115",
    "poweroff": "KEYPRESSES:30",
    "volumemute": "KEYPRESSES:113",
}

_ADVANCE_COMMANDS = {
    "autofocus",
    "autofocus_new",
    "manual_focus_left",
    "manual_focus_right",
    "motor_left_overstep",
    "motor_left_start",
    "motor_right_overstep",
    "motor_right_start",
    "motor_stop",
    "shortcut_setting",
    "choose_source",
    "hibernate",
    "xmusic",
}

_ADVANCE_COMMAND_TEMPLATE = str(
    {
        "action": 20000,
        "controlCmd": {
            "data": "command_holder",
            "delayTime": 0,
            "mode": 5,
            "time": 0,
            "type": 0,
        },
        "msgid": "2",
    }
)


class XgimiApi:
    def __init__(
        self,
        ip,
        command_port=COMMAND_PORT,
        advance_port=ADVANCE_PORT,
        alive_port=ALIVE_PORT,
        manufacturer_data="",
    ) -> None:
        self.ip = ip
        self.command_port = command_port  # 16735
        self.advance_port = advance_port  # 16750
        self.alive_port = alive_port  # 554
        self.manufacturer_data = normalize_manufacturer_data(manufacturer_data)
        self._is_on = False
        self.last_on = monotonic()
        self.last_off = monotonic()
        self._ble_lock = asyncio.Lock()

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        return self._is_on

    async def async_fetch_data(self):
        if monotonic() - self.last_on < 30:
            self._is_on = True
        elif monotonic() - self.last_off < 30:
            self._is_on = False
        else:
            alive = await self.async_check_alive()
            self._is_on = alive

    async def async_check_alive(self):
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.alive_port), timeout=2
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            return await self.async_check_ping()

    async def async_check_ping(self):
        """Return true if the projector responds to a short ICMP ping."""
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                "1",
                "-W",
                str(PING_TIMEOUT),
                self.ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            return await asyncio.wait_for(proc.wait(), timeout=PING_TIMEOUT + 1) == 0
        except (FileNotFoundError, TimeoutError, OSError):
            if proc and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return False

    async def async_ble_power_on(
        self,
        manufacturer_data: str,
        company_id: int = BLE_COMPANY_ID,
        service_uuid: str = BLE_SERVICE_UUID,
    ):
        bus = await get_message_bus()
        advert = Advertisement(
            localName="Bluetooth 4.0 RC",
            serviceUUIDs=[service_uuid],
            manufacturerData={company_id: bytes.fromhex(manufacturer_data)},
            timeout=BLE_ADVERTISEMENT_TIMEOUT,
            duration=BLE_ADVERTISEMENT_TIMEOUT,
            appearance=961,
        )
        try:
            await advert.register(bus)
            await asyncio.sleep(BLE_ADVERTISEMENT_TIMEOUT + 0.1)
        finally:
            bus.disconnect()

    async def async_robust_ble_power_on(
        self,
        manufacturer_data: str,
        company_id: int = BLE_COMPANY_ID,
        service_uuid: str = BLE_SERVICE_UUID,
    ):
        succeeded = False
        last_error: Exception | None = None
        async with self._ble_lock:
            for attempt in range(BLE_POWER_ON_REPEATS):
                try:
                    await self.async_ble_power_on(
                        manufacturer_data, company_id, service_uuid
                    )
                    succeeded = True
                except Exception as err:  # noqa: BLE001
                    last_error = err
                    _LOGGER.warning(
                        "XGIMI BLE power-on advertisement attempt %s/%s failed: %s",
                        attempt + 1,
                        BLE_POWER_ON_REPEATS,
                        type(err).__name__,
                    )

                if attempt + 1 < BLE_POWER_ON_REPEATS:
                    await asyncio.sleep(BLE_POWER_ON_REPEAT_DELAY)

        if not succeeded and last_error is not None:
            raise last_error

    async def _send_udp(self, port: int, message: str) -> None:
        remote_addr = (self.ip, port)
        sock = await asyncudp.create_socket(remote_addr=remote_addr)
        try:
            sock.sendto(message.encode("utf-8"))
        finally:
            sock.close()

    async def async_send_command(self, command) -> None:
        """Send a command to a device."""
        command = str(command).strip().lower()
        if command in _COMMANDS:
            msg = _COMMANDS[command]
            await self._send_udp(self.command_port, msg)
            if command == "poweroff":
                self._is_on = False
                self.last_off = monotonic()
        elif command == "poweron":
            await self.async_robust_ble_power_on(self.manufacturer_data)
            self._is_on = True
            self.last_on = monotonic()
        elif command in _ADVANCE_COMMANDS:
            msg = _ADVANCE_COMMAND_TEMPLATE.replace("command_holder", command)
            await self._send_udp(self.advance_port, msg)
        else:
            raise ValueError(f"Unsupported XGIMI command: {command}")
