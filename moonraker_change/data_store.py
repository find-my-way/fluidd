# Klipper data logging and storage storage
#
# Copyright (C) 2020 Eric Callahan <arksine.code@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations
import logging
import time
from collections import deque
from ..common import RequestType

# Annotation imports
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Dict,
    List,
    Deque,
)
if TYPE_CHECKING:
    from ..confighelper import ConfigHelper
    from ..common import WebRequest
    from .klippy_connection import KlippyConnection
    from .klippy_apis import KlippyAPI as APIComp
    GCQueue = Deque[Dict[str, Any]]
    TempStore = Dict[str, Dict[str, Deque[Optional[float]]]]
    PowerStore = Dict[str, Dict[str, Deque[Optional[float]]]]

TEMP_UPDATE_TIME = 1.

def _round_null(val: Optional[float], ndigits: int) -> Optional[float]:
    if val is None:
        return val
    return round(val, ndigits)

class DataStore:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.temp_store_size = config.getint('temperature_store_size', 1200)
        self.gcode_store_size = config.getint('gcode_store_size', 1000)

        # Temperature Store Tracking
        kconn: KlippyConnection = self.server.lookup_component("klippy_connection")
        self.subscription_cache = kconn.get_subscription_cache()
        self.gcode_queue: GCQueue = deque(maxlen=self.gcode_store_size)
        self.temperature_store: TempStore = {}
        self.power_store: PowerStore = {}
        self.temp_monitors: List[str] = []
        self.power_monitors: List[str] = []
        eventloop = self.server.get_event_loop()
        self.temp_update_timer = eventloop.register_timer(
            self._update_temperature_store)
        self.power_update_timer = eventloop.register_timer(
            self._update_power_store
        )

        self.server.register_event_handler(
            "server:gcode_response", self._update_gcode_store)
        self.server.register_event_handler(
            "server:klippy_ready", self._init_sensors)
        self.server.register_event_handler(
            "klippy_connection:gcode_received", self._store_gcode_command
        )

        # Register endpoints
        self.server.register_endpoint(
            "/server/temperature_store", RequestType.GET,
            self._handle_temp_store_request
        )
        self.server.register_endpoint(
            "/server/power_store", RequestType.GET,
            self._handle_power_store_request
        )
        self.server.register_endpoint(
            "/server/gcode_store", RequestType.GET,
            self._handle_gcode_store_request
        )

    async def _init_sensors(self) -> None:
        klippy_apis: APIComp = self.server.lookup_component('klippy_apis')
        # Fetch sensors
        try:
            result: Dict[str, Any]
            result = await klippy_apis.query_objects({'heaters': None, 'powers': None})
        except self.server.error as e:
            logging.info(f"Error Configuring Sensors: {e}")
            return
        heaters: Dict[str, List[str]] = result.get("heaters", {})
        powers: Dict[str, List[str]] = result.get("powers", {})
        temp_sensors_list = heaters.get("available_sensors", []) + heaters.get("available_monitors", [])
        power_sensors_list = powers.get("available_sensors", []) + powers.get("available_monitors", [])
        self.temp_monitors = heaters.get("available_monitors", [])
        self.power_monitors = powers.get("available_monitors", [])
        sensors = list(set(temp_sensors_list + power_sensors_list))

        if sensors:
            # Add Subscription
            sub: Dict[str, Optional[List[str]]] = {s: None for s in sensors}
            try:
                status: Dict[str, Any]
                status = await klippy_apis.subscribe_objects(sub)
            except self.server.error as e:
                logging.info(f"Error subscribing to sensors: {e}")
                return
            logging.info(f"Configuring available sensors: {sensors}")
            valid_fields = ("temperature", "target", "power", "speed", "shunt_voltage", "bus_voltage", "current")
            new_temp_store: TempStore = {}
            new_power_store: PowerStore = {}

            for sensor in sensors:
                reported_fields = [
                    f for f in list(status.get(sensor, {}).keys()) if f in valid_fields
                ]
                if not reported_fields:
                    logging.info(f"No valid fields reported for sensor: {sensor}")
                    continue

                if sensor in power_sensors_list:
                    current_new_store = new_power_store
                    current_old_store = self.power_store
                elif sensor in temp_sensors_list:
                    current_new_store = new_temp_store
                    current_old_store = self.temperature_store
                else:
                    continue

                if sensor in current_old_store:
                    current_new_store[sensor] = current_old_store[sensor]
                    for field in list(current_new_store[sensor].keys()):
                        if field not in reported_fields:
                            current_new_store[sensor].pop(field, None)
                        else:
                            initial_val: Optional[float]
                            initial_val = _round_null(status[sensor][field], 2)
                            current_new_store[sensor][field].append(initial_val)
                else:
                    current_new_store[sensor] = {}
                    
                for field in reported_fields:
                    if field not in current_new_store[sensor]:
                        initial_val = _round_null(status[sensor][field], 2)
                        current_new_store[sensor][field] = deque(
                            [initial_val], maxlen=self.temp_store_size
                        )

            self.temperature_store = new_temp_store
            self.power_store = new_power_store
            self.temp_update_timer.start(delay=1.)
            self.power_update_timer.start(delay=1.)
        else:
            logging.info("No sensors found")
            self.temperature_store = {}
            self.temp_monitors = []
            self.temp_update_timer.stop()
            self.power_store = {}
            self.power_monitors = []
            self.power_update_timer.stop()

    def _update_temperature_store(self, eventtime: float) -> float:
        for sensor_name, sensor in self.temperature_store.items():
            sdata: Dict[str, Any] = self.subscription_cache.get(sensor_name, {})
            for field, store in sensor.items():
                store.append(_round_null(sdata.get(field, store[-1]), 2))
        return eventtime + TEMP_UPDATE_TIME
    
    def _update_power_store(self, eventtime: float) -> float:
        for sensor_name, sensor in self.power_store.items():
            sdata: Dict[str, Any] = self.subscription_cache.get(sensor_name, {})
            for field, store in sensor.items():
                store.append(_round_null(sdata.get(field, store[-1]), 2))
        return eventtime + TEMP_UPDATE_TIME

    async def _handle_temp_store_request(
        self, web_request: WebRequest
    ) -> Dict[str, Dict[str, List[Optional[float]]]]:
        include_monitors = web_request.get_boolean("include_monitors", False)
        store = {}
        for name, sensor in self.temperature_store.items():
            if not include_monitors and name in self.temp_monitors:
                continue
            store[name] = {f"{k}s": list(v) for k, v in sensor.items()}
        return store
    
    async def _handle_power_store_request(
        self, web_request: WebRequest
    ) -> Dict[str, Dict[str, List[Optional[float]]]]:
        include_monitors = web_request.get_boolean("include_monitors", False)
        store = {}
        for name, sensor in self.power_store.items():
            if not include_monitors and name in self.power_monitors:
                continue
            store[name] = {f"{k}s": list(v) for k, v in sensor.items()}
        return store

    async def close(self) -> None:
        self.temp_update_timer.stop()
        self.power_update_timer.stop()

    def _update_gcode_store(self, response: str) -> None:
        curtime = time.time()
        self.gcode_queue.append(
            {'message': response, 'time': curtime, 'type': "response"})

    def _store_gcode_command(self, script: str) -> None:
        curtime = time.time()
        if script.strip():
            self.gcode_queue.append(
                {'message': script, 'time': curtime, 'type': "command"}
            )

    async def _handle_gcode_store_request(self,
                                          web_request: WebRequest
                                          ) -> Dict[str, List[Dict[str, Any]]]:
        count = web_request.get_int("count", None)
        if count is not None:
            gc_responses = list(self.gcode_queue)[-count:]
        else:
            gc_responses = list(self.gcode_queue)
        return {'gcode_store': gc_responses}

def load_component(config: ConfigHelper) -> DataStore:
    return DataStore(config)
