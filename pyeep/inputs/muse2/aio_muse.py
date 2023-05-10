from __future__ import annotations

import functools
import time

import bleak
import muselsl.constants
import muselsl.muse


class Muse(muselsl.muse.Muse):
    """
    muselsl.muse.Muse wrapper specific to bleak and asyncio
    """
    # See https://github.com/alexandrebarachant/muse-lsl.git
    #
    # The low-level calculation methods are preserved from muselsl.muse.Muse
    # while the blocking methods and the bluetooth methods are remplemented in
    # a simplified way, since we can make more assumptions about bleak and
    # asyncio

    def __init__(self, client: bleak.BleakClient):
        self.client = client
        self.callback_eeg = None
        self.callback_telemetry = None
        self.callback_control = None
        self.callback_acc = None
        self.callback_gyro = None
        self.callback_ppg = None
        self.time_func = time.time
        self.last_timestamp = self.time_func()

    async def _write_cmd(self, cmd: list[bytes]):
        """
        Write a command to the Muse device
        """
        await self.client.write_gatt_char(
                0x000e - 1,
                bytearray(cmd),
                False)

    async def _write_cmd_str(self, cmd: str):
        """
        Encode and write a command string to the Muse device
        """
        await self._write_cmd(
                [len(cmd) + 1, *(ord(char) for char in cmd), ord('\n')])

    async def ask_control(self):
        """Send a message to Muse to ask for the control status.

        Only useful if control is enabled (to receive the answer!)

        The message received is a dict with the following keys:
        "hn": device name
        "sn": serial number
        "ma": MAC address
        "id":
        "bp": battery percentage
        "ts":
        "ps": preset selected
        "rc": return status, if 0 is OK
        """
        await self._write_cmd_str('s')

    async def ask_device_info(self):
        """Send a message to Muse to ask for the device info.

        The message received is a dict with the following keys:
        "ap":
        "sp":
        "tp": firmware type, e.g: "consumer"
        "hw": hardware version?
        "bn": build number?
        "fw": firmware version?
        "bl":
        "pv": protocol version?
        "rc": return status, if 0 is OK
        """
        await self._write_cmd_str('v1')

    async def ask_reset(self):
        """Undocumented command reset for '*1'
        The message received is a singleton with:
        "rc": return status, if 0 is OK
        """
        await self._write_cmd_str('*1')

    async def start(self):
        """Start streaming."""
        self.first_sample = True
        self._init_sample()
        self._init_ppg_sample()
        self.last_tm = 0
        self.last_tm_ppg = 0
        self._init_control()
        await self.resume()

    async def resume(self):
        """Resume streaming, sending 'd' command"""
        await self._write_cmd_str('d')

    async def stop(self):
        """Stop streaming."""
        await self._write_cmd_str('h')

    async def keep_alive(self):
        """Keep streaming, sending 'k' command"""
        await self._write_cmd_str('k')

    async def select_preset(self, preset=21):
        """Set preset for headband configuration

        See details here https://articles.jaredcamins.com/figuring-out-bluetooth-low-energy-part-2-750565329a7d
        For 2016 headband, possible choice are 'p20' and 'p21'.
        Untested but possible values include:
          'p22','p23','p31','p32','p50','p51','p52','p53','p60','p61','p63','pAB','pAD'
        Default is 'p21'."""

        if type(preset) is int:
            preset = str(preset)
        if preset[0] == 'p':
            preset = preset[1:]
        if str(preset) != '21':
            print('Sending command for non-default preset: p' + preset)
        preset = bytes(preset, 'utf-8')
        await self._write_cmd([0x04, 0x70, *preset, 0x0a])

    async def _start_notify(self, uuid, callback):
        @functools.wraps(callback)
        def wrap(gatt_characteristic, data):
            value_handle = gatt_characteristic.handle + 1
            callback(value_handle, data)
        await self.client.start_notify(uuid, wrap)

    async def subscribe_eeg(self, callback_eeg):
        """subscribe to eeg stream."""
        self.callback_eeg = callback_eeg
        await self._start_notify(muselsl.constants.MUSE_GATT_ATTR_TP9, callback=self._handle_eeg)
        await self._start_notify(muselsl.constants.MUSE_GATT_ATTR_AF7, callback=self._handle_eeg)
        await self._start_notify(muselsl.constants.MUSE_GATT_ATTR_AF8, callback=self._handle_eeg)
        await self._start_notify(muselsl.constants.MUSE_GATT_ATTR_TP10, callback=self._handle_eeg)
        await self._start_notify(muselsl.constants.MUSE_GATT_ATTR_RIGHTAUX, callback=self._handle_eeg)

    async def subscribe_control(self, callback_control):
        self.callback_control = callback_control
        await self._start_notify(
            muselsl.constants.MUSE_GATT_ATTR_STREAM_TOGGLE, callback=self._handle_control)

        self._init_control()

    async def subscribe_telemetry(self, callback_telemetry):
        self.callback_telemetry = callback_telemetry
        await self._start_notify(
            muselsl.constants.MUSE_GATT_ATTR_TELEMETRY, callback=self._handle_telemetry)

    async def subscribe_acc(self, callback_acc):
        self.callback_acc = callback_acc
        await self._start_notify(
            muselsl.constants.MUSE_GATT_ATTR_ACCELEROMETER, callback=self._handle_acc)

    async def subscribe_gyro(self, callback_gyro):
        self.callback_gyro = callback_gyro
        await self._start_notify(
            muselsl.constants.MUSE_GATT_ATTR_GYRO, callback=self._handle_gyro)

    async def subscribe_ppg(self, callback_ppg):
        self.callback_ppg = callback_ppg
        try:
            """subscribe to ppg stream."""
            await self._start_notify(
                muselsl.contants.MUSE_GATT_ATTR_PPG1, callback=self._handle_ppg)
            await self._start_notify(
                muselsl.contants.MUSE_GATT_ATTR_PPG2, callback=self._handle_ppg)
            await self._start_notify(
                muselsl.contants.MUSE_GATT_ATTR_PPG3, callback=self._handle_ppg)
        except Exception:
            raise Exception(
                'PPG data is not available on this device. PPG is only available on Muse 2'
            )

    async def _disable_light(self):
        await self._write_cmd_str('L0')
