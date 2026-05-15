import os, logging, threading

class PowerSensor:
    def __init__(self, config, sensor):
        self.printer = config.get_printer()
        self.name = config.get_name()
        self.short_name = self.name.split()[-1]
        # Setup sensor
        self.sensor = sensor
        self.mcu = sensor.get_mcu()
        self.sensor.setup_callback(self.power_callback)
        # Setup temperature checks
        self.smooth_time = config.getfloat('smooth_time', 1., above=0.)
        self.inv_smooth_time = 1. / self.smooth_time
        self.lock = threading.Lock()
        self.last_shunt_voltage = self.smoothed_shunt_voltage = 0.0
        self.last_bus_voltage = self.smoothed_bus_voltage = 0.0
        self.last_power = self.smoothed_power = 0.0
        self.last_current = self.smoothed_current = 0.0
        self.last_sample_time = 0.0
        
    def power_callback(self, read_time, shunt_voltage, bus_voltage, power, current):
        with self.lock:
            time_diff = read_time - self.last_sample_time
            self.last_shunt_voltage = shunt_voltage
            self.last_bus_voltage = bus_voltage
            self.last_power = power
            self.last_current = current
            self.last_sample_time = read_time
            shunt_voltage_diff = shunt_voltage - self.smoothed_shunt_voltage
            bus_voltage_diff = bus_voltage - self.smoothed_bus_voltage
            power_diff = power - self.smoothed_power
            current_diff = current - self.smoothed_current
            adj_time = min(time_diff * self.inv_smooth_time, 1.)
            self.smoothed_shunt_voltage += shunt_voltage_diff * adj_time
            self.smoothed_bus_voltage += bus_voltage_diff * adj_time
            self.smoothed_power += power_diff * adj_time
            self.smoothed_current += current_diff * adj_time

    def get_name(self):
        return self.name
    
    def get_smooth_time(self):
        return self.smooth_time
    
    def get_power(self, eventtime):
        print_time = self.mcu.estimated_print_time(eventtime) - 5.
        with self.lock:
            if self.last_sample_time < print_time:
                return 0., 0., 0., 0.
            return self.smoothed_shunt_voltage, self.smoothed_bus_voltage, self.smoothed_power, self.smoothed_current
        
    def stats(self, eventtime):
        with self.lock:
            last_shunt_voltage = self.last_shunt_voltage
            last_bus_voltage = self.last_bus_voltage
            last_power = self.last_power
            last_current = self.last_current
        is_active = last_current > 0.01 or last_bus_voltage > 1.0
        return is_active, '%s: shunt_voltage=%.6f bus_voltage=%.4f power=%.4f current=%.4f' % (self.short_name, last_shunt_voltage, last_bus_voltage, last_power, last_current)
    
    def get_status(self, eventtime):
        with self.lock:
            smoothed_shunt_voltage = self.smoothed_shunt_voltage
            smoothed_bus_voltage = self.smoothed_bus_voltage
            smoothed_power = self.smoothed_power
            smoothed_current = self.smoothed_current
        return {
            'shunt_voltage': round(smoothed_shunt_voltage, 6),
            'bus_voltage': round(smoothed_bus_voltage, 4),
            'power': round(smoothed_power, 4),
            'current': round(smoothed_current, 4),
        }

class PrinterPowerSensors:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.sensor_factories = {}
        self.powers = {}
        self.gcode_id_to_sensor = {}
        self.available_powers = []
        self.available_sensors = []
        self.available_monitors = []
        self.has_started = self.have_load_sensors = False
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        
    def load_config(self, config):
        logging.info("Loading Power Sensors config")
        self.have_load_sensors = True
        # Load default power sensors
        pconfig = self.printer.lookup_object('configfile')
        dir_name = os.path.dirname(__file__)
        filename = os.path.join(dir_name, 'power_sensors.cfg')
        try:
            dconfig = pconfig.read_config(filename)
        except Exception:
            logging.exception("Unable to load power_sensors.cfg")
            raise config.error("Cannot load config '%s'" % (filename,))
        for c in dconfig.get_prefix_sections(''):
            self.printer.load_object(dconfig, c.get_name())

    def add_sensor_factory(self, sensor_type, sensor_factory):
        logging.info("add_sensor_factory")
        self.sensor_factories[sensor_type] = sensor_factory

    def setup_powers(self, config, gcode_id=None):
        logging.info("setup_power_sensor")
        powers_name = config.get_name().split()[-1]
        if powers_name in self.powers:
            raise config.error("Power Sensors %s already registered" % (powers_name,))
        # Setup sensor
        sensor = self.setup_sensor(config)
        # Create power sensor
        self.powers[powers_name] = power_sensor = PowerSensor(config, sensor)
        self.register_sensor(config, power_sensor, gcode_id)
        self.powers.append(config.get_name())
        return power_sensor
    
    def powers(self):
        return self.available_powers
    
    def lookup_power_sensor(self, power_sensor_name):
        if power_sensor_name not in self.powers:
            raise self.printer.config_error(
                "Unknown power sensor '%s'" % (power_sensor_name,))
        return self.powers[power_sensor_name]
    
    def setup_sensor(self, config):
        logging.info("setup_sensor")
        if not self.have_load_sensors:
            logging.info("Loading Power Sensors config")
            self.load_config(config)
        sensor_type = config.get('sensor_type')
        if sensor_type not in self.sensor_factories:
            raise self.printer.config_error(
                "Unknown power sensor '%s'" % (sensor_type,))
        return self.sensor_factories[sensor_type](config)
    
    def register_sensor(self, config, psensor, gcode_id=None):
        self.available_sensors.append(config.get_name())
        if gcode_id is None:
            gcode_id = config.get('gcode_id', None)
            if gcode_id is None:
                return
        if gcode_id in self.gcode_id_to_sensor:
            raise self.printer.config_error(
                "G-Code sensor id %s already registered" % (gcode_id,))
        self.gcode_id_to_sensor[gcode_id] = psensor

    def register_monitor(self, config):
        self.available_monitors.append(config.get_name())

    def get_status(self, eventtime):
        return {'available_powers': self.available_powers,
                'available_sensors': self.available_sensors,
                'available_monitors': self.available_monitors}
    
    def _handle_ready(self):
        self.has_started = True

def load_config(config):
    return PrinterPowerSensors(config)
