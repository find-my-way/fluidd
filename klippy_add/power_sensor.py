class PrinterPowerSensorGeneric:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        ppower = self.printer.load_object(config, 'powers')
        self.sensor = ppower.setup_sensor(config)
        self.sensor.setup_callback(self.power_callback)
        ppower.register_sensor(config, self)
        self.last_shunt_voltage = 0.
        self.last_bus_voltage = 0.
        self.last_power = 0.
        self.last_current = 0.

    def power_callback(self, read_time, shunt_voltage, bus_voltage, power, current):
        self.last_shunt_voltage = shunt_voltage
        self.last_bus_voltage = bus_voltage
        self.last_power = power
        self.last_current = current

    def get_power(self):
        return self.last_shunt_voltage, self.last_bus_voltage, self.last_power, self.last_current
    
    def stats(self, eventtime):
        return False, '%s: shunt_voltage=%.6f bus_voltage=%.4f power=%.4f current=%.4f' % (self.name, self.last_shunt_voltage, self.last_bus_voltage, self.last_power, self.last_current)
    
    def get_status(self, eventtime):
        return {
            "shunt_voltage": round(self.last_shunt_voltage, 6),
            "bus_voltage": round(self.last_bus_voltage, 4),
            "power": round(self.last_power, 4),
            "current": round(self.last_current, 4),
        }
    
def load_config_prefix(config):
    return PrinterPowerSensorGeneric(config)
