# Fluidd (Power Monitor)

[English](#english) | [中文](#chinese)

---

<a name="chinese"></a>
## 🇨🇳 中文说明

### 🌟 功能特性
此分支在 Fluidd 官方版本的基础上，针对功率传感器（如 INA219, INA226, INA233 等）进行了数据接口适配和图表展示, 暂时只有INA226驱动, 可以根据INA226驱动代码修改.
(注意: 语言只做了中文和英文适配, 如果要显示其他语言去src/locales找对应语言的yaml修改)

### 📸 界面展示
<img width="880" height="433" alt="image" src="https://github.com/user-attachments/assets/4d9fb5c1-d638-4dae-8231-8cbb4af1de20" />
<img width="355" height="152" alt="image" src="https://github.com/user-attachments/assets/57150a49-94b1-452f-9b17-f7b4cea1017c" />


### 🛠 如何安装
#### 1. 复制klippy_add里的文件到打印机的klipper/klippy/extras里
#### 2. 将打印机的moonraker/moonraker/components/data_store.py替换成moonraker_change/data_store.py
#### 3. 下载fluidd_power_monitor.zip下载到打印机里, 替换掉fluidd/
#### 4. 在printer.cfg中添加
```
#####################################################################
#  INA226 Settings
#####################################################################
[power_sensor mb]
sensor_type: ina226
i2c_address: 64
i2c_mcu: mcu
i2c_bus: i2c2_PB10_PB11
i2c_speed: 400000
alert_pin: PE8          #需要有这一行, 但是没有任何功能
max_current: 10.0
max_voltage: 25.0
shunt_resistor: 0.002
avg_samples: 16
```

### 🛠 如何编译
#### 1. 拉取源代码后
#### 2. npm install
#### 3. npm run build

---

<a name="english"></a>
## 🇺🇸 English Description

### 🌟 Key Features
This branch is a customized fork of Fluidd, specifically optimized for Power Sensor data interfaces and chart displays (e.g., INA219, INA226, INA233):

- **Driver Support**: Currently includes full support for the **INA226** driver. Other drivers can be adapted based on the INA226 implementation.
- **Multi-language**: Currently supports **English** and **Chinese**. 
  *(Note: To add other languages, please modify the corresponding YAML files in `src/locales`.)*

### 📸 Screenshot
<img width="880" height="433" alt="image" src="https://github.com/user-attachments/assets/4d9fb5c1-d638-4dae-8231-8cbb4af1de20" />
<img width="355" height="152" alt="image" src="https://github.com/user-attachments/assets/ce44a9a6-5afc-4247-b2c2-4b585ed78033" />


### 🛠 Installation
#### 1. Copy the files from `klippy_add` to your printer's `klipper/klippy/extras` directory.
#### 2. Replace `moonraker/moonraker/components/data_store.py` on your printer with the version from `moonraker_change/data_store.py`.
#### 3. Download `fluidd_power_monitor.zip` to your printer and replace the contents of the `fluidd/` directory.
#### 4. printer.cfg
```
#####################################################################
#  INA226 Settings
#####################################################################
[power_sensor mb]
sensor_type: ina226
i2c_address: 64
i2c_mcu: mcu
i2c_bus: i2c2_PB10_PB11
i2c_speed: 400000
alert_pin: PE8          #This line is required but has no functional effect
max_current: 10.0
max_voltage: 25.0
shunt_resistor: 0.002
avg_samples: 16
```

### 🛠 How to Build
#### 1. Clone the source code.
#### 2. Run `npm install`.
#### 3. Run `npm run build`.
