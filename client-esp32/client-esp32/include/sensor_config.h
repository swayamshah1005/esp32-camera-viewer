#pragma once

// ---- Central sensor configuration ----
//
// Every sampling-rate / I2C-address knob for the sensor rig lives here.
// To retune a rate or try an alternate address, edit this file and
// reflash -- main.cpp's setup/loop logic never needs to change.
//
// Three different rates matter here and they are NOT the same lever:
//   - SD_LOG_INTERVAL_MS: how often we write a full row of every sensor's
//     current reading to the SD card. This is the real, complete dataset --
//     an SD write costs essentially no power compared to a radio TX, so
//     there's no battery reason to run this slower.
//   - MQTT_HEARTBEAT_INTERVAL_MS: how often we key up the WiFi radio at all.
//     Since radio TX is by far the biggest power draw on this board -- much
//     bigger than any I2C read or SD write -- this is the one thing that
//     actually determines battery life, which is why it's slow (30s). It
//     still carries every sensor's current reading (so the dashboard keeps
//     showing real values, just refreshed every 30s instead of continuously)
//     -- "heartbeat" here means "the infrequent radio update", not "empty
//     ping with no data". The SD card gets the complete, finer-grained
//     record (every 1s, full IMU peak/RMS) that the radio never sees.
//   - IMU_SAMPLE_INTERVAL_MS: how often we read the accelerometer/gyro
//     *locally* between SD writes (just an I2C read, no radio, no SD write
//     by itself). Sampling at 100 Hz and reporting the peak/RMS since the
//     last SD write gets fine-grained motion-event detection (e.g. a sudden
//     movement) without writing 100 rows/second to the card.
#define SD_LOG_INTERVAL_MS 1000          // 1-2s per the professor -- full sensor row to SD
#define MQTT_HEARTBEAT_INTERVAL_MS 30000 // 30s -- full sensor reading, just infrequent, to save radio power
#define IMU_SAMPLE_INTERVAL_MS 10        // 100 Hz -- local accumulator only, feeds the SD row

// ---- Shared I2C bus ----
#define I2C_SDA_GPIO 8
#define I2C_SCL_GPIO 9

// ---- SD card (onboard slot on the Freenove ESP32-S3-WROOM CAM board) ----
// Fixed by the board's own design (SDMMC 1-bit mode), not something wired by
// hand -- per Freenove's own docs, not a guess. Doesn't conflict with the
// I2C bus above or with PSRAM (GPIO35-37).
#define SD_CMD_GPIO 38
#define SD_CLK_GPIO 39
#define SD_D0_GPIO 40

// ---- LSM6DS3TR-C (accel + gyro) ----
// Chip's internal output data rate. Adafruit_LSM6DS.h options:
//   LSM6DS_RATE_SHUTDOWN, LSM6DS_RATE_12_5_HZ, LSM6DS_RATE_26_HZ,
//   LSM6DS_RATE_52_HZ, LSM6DS_RATE_104_HZ (library default), LSM6DS_RATE_208_HZ,
//   LSM6DS_RATE_416_HZ, LSM6DS_RATE_833_HZ, LSM6DS_RATE_1_66K_HZ,
//   LSM6DS_RATE_3_33K_HZ, LSM6DS_RATE_6_66K_HZ
#define LSM6DS_ACCEL_RATE LSM6DS_RATE_104_HZ
#define LSM6DS_GYRO_RATE LSM6DS_RATE_104_HZ

// ---- MLX90632 (non-contact IR temperature) ----
// Adafruit_MLX90632.h options:
//   MLX90632_REFRESH_0_5HZ, _1HZ, _2HZ, _4HZ, _8HZ, _16HZ, _32HZ, _64HZ
// 0.5Hz (slowest available) is still ~60x faster than we publish it, so
// there's always a fresh reading waiting -- no reason to run it faster and
// burn extra power on conversions we'd just throw away.
#define MLX90632_REFRESH_RATE MLX90632_REFRESH_0_5HZ

// ---- BME280 (temp/humidity/pressure) ----
// Effective rate is a function of oversampling (more = slower, less noise)
// plus the standby time normal-mode idles between samples. Adafruit_BME280.h
// options -- sensor_sampling: SAMPLING_NONE/X1/X2/X4/X8/X16; standby_duration:
// STANDBY_MS_0_5/10/20/62_5/125/250/500/1000.
#define BME280_MODE Adafruit_BME280::MODE_NORMAL
#define BME280_TEMP_OVERSAMPLING Adafruit_BME280::SAMPLING_X16
#define BME280_PRESSURE_OVERSAMPLING Adafruit_BME280::SAMPLING_X16
#define BME280_HUMIDITY_OVERSAMPLING Adafruit_BME280::SAMPLING_X16
#define BME280_FILTER Adafruit_BME280::FILTER_OFF
#define BME280_STANDBY_DURATION Adafruit_BME280::STANDBY_MS_0_5

// ---- VEML7700 (ambient light) ----
// Longer integration = more sensitive/accurate at low light, but slower.
// Adafruit_VEML7700.h options: VEML7700_IT_25MS, _50MS, _100MS, _200MS,
// _400MS, _800MS.
#define VEML7700_INTEGRATION_TIME VEML7700_IT_100MS

// ---- AS7343 (14-channel spectral) ----
// Integration time (ms) ~= (ATIME+1) * (ASTEP+1) * 2.78us -- these three
// values are Adafruit's own recommended starting point from their
// basic_readings example. Higher gain = more sensitive but slower to avoid
// saturating in bright light.
// Adafruit_AS7343.h gain options: AS7343_GAIN_0_5X, _1X, _2X, _4X, _8X,
// _16X, _32X, _64X, _128X, _256X, _512X, _1024X, _2048X.
// (named *_VALUE/*_SETTING, not AS7343_ATIME/AS7343_ASTEP -- those collide
// with internal register-address macros already #defined by Adafruit_AS7343.h)
#define AS7343_GAIN_SETTING AS7343_GAIN_64X
#define AS7343_ATIME_VALUE 29
#define AS7343_ASTEP_VALUE 599

// ---- SCD41 (true CO2) ----
// The Sensirion library only exposes two fixed cadences, not an arbitrary
// rate: normal periodic mode (~5s/reading) or low-power periodic mode
// (~30s/reading, lower current draw). Low-power mode's ~30s cadence lines
// up almost exactly with SLOW_SENSOR_PUBLISH_INTERVAL_MS, so there's no
// reason to run it faster and throw most readings away.
#define SCD41_LOW_POWER_MODE 1

// ---- ENS160 (air quality) ----
// ScioSense_ENS16x only exposes startStandardMeasure() in the mode we use --
// no rate parameter to configure here. (Listed so its absence is a
// documented choice, not an oversight.)

// ---- I2C addresses ----
// BME280/ENS160 both have a strap pin that picks between two addresses;
// setup tries PRIMARY first, then ALT.
#define BME280_I2C_ADDR_PRIMARY 0x76
#define BME280_I2C_ADDR_ALT 0x77
#define ENS160_I2C_ADDR_PRIMARY 0x52
#define ENS160_I2C_ADDR_ALT 0x53
// Fixed-address chips (no strap pin, listed here for reference/visibility):
#define SCD41_I2C_ADDR SCD41_I2C_ADDR_62
#define VEML7700_I2C_ADDR 0x10 // set internally by Adafruit_VEML7700, not passed explicitly
#define AS7343_I2C_ADDR 0x39   // set internally by Adafruit_AS7343, not passed explicitly
#define LSM6DS3TRC_I2C_ADDR 0x6A // set internally by begin_I2C(), not passed explicitly
#define MLX90632_I2C_ADDR 0x3A   // set internally by Adafruit_MLX90632, not passed explicitly
