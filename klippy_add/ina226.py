import logging
from . import bus

# INA226 ID
INA226_ID = 0x5449
INA226_DIE_ID = 0x2260

# INA226 address (A0 = 0, A1 = 0)
INA226_I2C_ADDR = 0x40

# INA226 registers
REG_INA226_CONFIG = 0x00
REG_INA226_SHUNT_VOLTAGE = 0x01
REG_INA226_BUS_VOLTAGE = 0x02
REG_INA226_POWER = 0x03
REG_INA226_CURRENT = 0x04
REG_INA226_CALIBRATION = 0x05
REG_INA226_MASK_ENABLE = 0x06
REG_INA226_ALERT_LIMIT = 0x07
REG_INA226_ID = 0xFE
REG_INA226_DIE_ID = 0xFF

AVG_SAMPLES_MAP = {
    1: 0b000,
    4: 0b001,
    16: 0b010,
    64: 0b011,
    128: 0b100,
    256: 0b101,
    512: 0b110,
    1024: 0b111
}

REPORT_TIME = 0.300

class ina226:
    def __init__(self, config): 
        logging.info("ina226: Initializing")
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.name = config.get_name().split()[-1]
        # get config
        self.i2c = bus.MCU_I2C_from_config(
            config, default_addr=INA226_I2C_ADDR, default_speed=400000
        )
        self.mcu = self.i2c.get_mcu()
        self.alert_pin = config.get('alert_pin')
        self.max_current = config.getfloat('max_current', 10.0, minval=1.0)
        self.max_voltage = config.getfloat('max_voltage', 24.0, minval=24.0)
        self.shunt_resistor = config.getfloat('shunt_resistor', 0.1)
        self.avg_samples = config.getint('avg_samples', 16, minval=1, maxval=1024)
        # create variables
        self.shunt_voltage = self.bus_voltage = self.power = self.current = 0.0
        self.current_lsb = 0.0
        # register gcode
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('QUERY_INA226', self.cmd_QUERY_INA226)
        self.sample_timer = self.reactor.register_timer(self._sample_ina226)
        self.printer.add_object("ina226 " + self.name, self)
        self.printer.register_event_handler("klippy:connect", self.handle_connect)

    def get_mcu(self):
        return self.mcu

    def setup_callback(self, cb):
        self._callback = cb

    def get_report_time_delta(self):
        return REPORT_TIME

    def handle_connect(self):
        self._init_ina226()
        self.reactor.update_timer(self.sample_timer, self.reactor.NOW)

    def cmd_QUERY_INA226(self, gcmd):
        self._sample_ina226(self.reactor.monotonic())
        gcmd.respond_info(
            "INA226 [%s] status:\n"
            "Bus Voltage: %.4f V\n"
            "Shunt Voltage: %.6f V\n"
            "Current: %.4f A\n"
            "Power: %.4f W" % (
                self.name, self.bus_voltage, self.shunt_voltage,
                self.current, self.power))
    
    def _twos_comp(self, val, bits):
        if val & (1 << (bits - 1)):
            val -= 1 << bits
        return val
    
    def _init_ina226(self):
        # Device Soft Reset
        self.i2c.i2c_write([REG_INA226_CONFIG, 0x80, 0x00])
        # Wait 10ms after reset
        self.reactor.pause(self.reactor.monotonic() + 0.01)

        # Read and verify Chip ID
        chip_id = self.i2c.i2c_read([REG_INA226_ID], 2)
        response = bytearray(chip_id['response'])
        manufacturer_id = (response[0] << 8) | response[1]
        if manufacturer_id == INA226_ID:
            logging.info("ina226: Found Device with Manufacturer ID 0x%04X" % manufacturer_id)
        else:
            logging.warning("ina226: Unexpected Manufacturer ID 0x%04X" % manufacturer_id)

        # Configure INA226
        config_value = 0x0000
        avg_samples_value = AVG_SAMPLES_MAP.get(self.avg_samples, 0b010)
        config_value |= (avg_samples_value << 9)  # AVG bits
        config_value |= (0b100 << 6)  # VBUSCT bits (1.1ms)
        config_value |= (0b100 << 3)  # VSHCT bits (1.1ms)
        config_value |= 0b111  # MODE bits (Shunt and Bus, Continuous)
        self.i2c.i2c_write([REG_INA226_CONFIG, (config_value >> 8) & 0xFF, config_value & 0xFF])

        # Calculate and write calibration value
        self.current_lsb = self.max_current / 32768.0
        calibration_value = int(0.00512 / (self.current_lsb * self.shunt_resistor))
        self.i2c.i2c_write([REG_INA226_CALIBRATION, (calibration_value >> 8) & 0xFF, calibration_value & 0xFF])

    def _sample_ina226(self, eventtime):
        try: 
            # Read Shunt Voltage, Bus Voltage, Power, and Current
            params = self.i2c.i2c_read([REG_INA226_SHUNT_VOLTAGE], 2)
            response = bytearray(params['response'])
            shunt_voltage_raw_data = (response[0] << 8) | response[1]

            params = self.i2c.i2c_read([REG_INA226_BUS_VOLTAGE], 2)
            response = bytearray(params['response'])
            bus_voltage_raw_data = (response[0] << 8) | response[1]

            params = self.i2c.i2c_read([REG_INA226_POWER], 2)
            response = bytearray(params['response'])
            power_raw_data = (response[0] << 8) | response[1]

            params = self.i2c.i2c_read([REG_INA226_CURRENT], 2)
            response = bytearray(params['response'])
            current_raw_data = (response[0] << 8) | response[1]

            # Convert raw data to physical values
            self.shunt_voltage = self._twos_comp(shunt_voltage_raw_data, 16) * 0.0000025  # 2.5uV per bit
            self.bus_voltage = bus_voltage_raw_data * 0.00125  # 1.25mV per bit
            self.current = self._twos_comp(current_raw_data, 16) * self.current_lsb
            self.power = power_raw_data * (25.0 * self.current_lsb)
            
        except Exception:
            logging.exception("ina226: Error during sampling")
            self.shunt_voltage = self.bus_voltage = self.power = self.current = 0.0
            return self.reactor.NEVER
        
        measured_time = self.reactor.monotonic()
        print_time = self.i2c.get_mcu().estimated_print_time(measured_time)
        self._callback(print_time, self.shunt_voltage, self.bus_voltage, self.power, self.current)
        return measured_time + REPORT_TIME
    
    def get_status(self, eventtime):
        return {
            "shunt_voltage": round(self.shunt_voltage, 6),
            "bus_voltage": round(self.bus_voltage, 4),
            "power": round(self.power, 4),
            "current": round(self.current, 4),
        }
        
def load_config(config):
    p_power_sensor = config.get_printer().load_object(config, "powers")
    p_power_sensor.add_sensor_factory("ina226", ina226)
