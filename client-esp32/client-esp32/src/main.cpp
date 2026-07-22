#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <SensirionI2cScd4x.h>
#include <ScioSense_ENS16x.h>
#include <Adafruit_VEML7700.h>
#include <Adafruit_AS7343.h>
#include <Adafruit_LSM6DS3TRC.h>
#include <Adafruit_MLX90632.h>
#include <FS.h>
#include <SD_MMC.h>
#include "sensor_config.h"
#include "secrets.h" // gitignored -- see secrets.h.example

// The camera's parallel data bus uses GPIO 8/9 (Y4/Y3, see below) -- the same
// pins the BME280 is wired to over I2C (SDI->8, SCK->9). The two can't be
// active at once on this board, so the camera is disabled while the BME280
// is wired here. Flip back to 1 (and rewire the BME280 to free GPIOs) to
// bring the camera back.
//
// esp_camera.h and Adafruit_Sensor.h both typedef a `sensor_t`, so
// esp_camera.h (and everything that only exists to support it) must not be
// included at all while the camera is disabled, not just left uncalled.
#define ENABLE_CAMERA 0

#if ENABLE_CAMERA
#include "esp_camera.h"
#include <HTTPClient.h>
#endif

// ssid, password, mqttBroker, serverUrl all come from secrets.h (gitignored)

// MQTT
const int mqttPort = 1883;
const char* mqttTopic = "esp32/status";
const char* sensorTopic = "aether/esp32_01/sensor"; // matches backend/mqtt_bridge.py's subscription

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

#if ENABLE_CAMERA
int framesUploaded = 0;
int lastHttpCode = 0;
#endif

// Shared I2C bus -- every sensor below hangs off these same two pins, each at
// its own fixed/strapped address. SDI(SDA)->GPIO8, SCK(SCL)->GPIO9.
// Pins, addresses, and sampling rates all live in include/sensor_config.h.

// ---- BME280 (env: temp/humidity/pressure) -- SDO strap picks 0x76/0x77 ----
Adafruit_BME280 bme;
bool bmeReady = false;

// ---- SCD41 (true CO2, I2C) -- fixed address 0x62 ----
SensirionI2cScd4x scd4x;
bool scdReady = false;
uint16_t scdCo2Cached = 0;

// ---- ENS160 (air quality, I2C) -- ADDR strap picks 0x52/0x53 ----
ENS160 ens160;
bool ensReady = false;
uint8_t ensAqiCached = 0;
uint16_t ensTvocCached = 0;
uint16_t ensEco2Cached = 0;

// ---- VEML7700 (ambient light, I2C) -- fixed address 0x10 ----
Adafruit_VEML7700 veml;
bool vemlReady = false;

// ---- AS7343 (14-channel spectral, I2C) -- fixed address 0x39 ----
Adafruit_AS7343 as7343;
bool as7343Ready = false;
bool as7343MeasuringStarted = false;
const char* as7343DominantName = nullptr;
int as7343DominantNm = 0;
float as7343ClearCached = 0;
// Index mapping per Adafruit_AS7343's as7343_channel_t enum (18-channel
// auto-SMUX layout). Fixed order used both for caching and for publishing,
// so the dashboard's waterfall plot gets a stable channel order every frame.
struct NamedChannel { const char* name; int nm; uint8_t rawIdx; };
static const NamedChannel AS7343_CHANNELS[] = {
  {"F1", 405, 12}, {"F2", 425, 6}, {"F3", 475, 7}, {"F4", 515, 8},
  {"FZ", 450, 0},  {"F5", 550, 15}, {"FY", 555, 1}, {"F6", 640, 9},
  {"FXL", 600, 2}, {"F7", 690, 13}, {"F8", 745, 14}, {"NIR", 855, 3},
};
const int AS7343_CHANNEL_COUNT = sizeof(AS7343_CHANNELS) / sizeof(AS7343_CHANNELS[0]);
float as7343ChannelCached[AS7343_CHANNEL_COUNT] = {0};

// ---- LSM6DS3TR-C (accel + gyro, I2C) -- default address 0x6A ----
Adafruit_LSM6DS3TRC lsm6ds3trc;
bool lsmReady = false;
// Accumulator for the 100Hz-sampled-but-~1s-logged pattern: sampleImu()
// updates these every IMU_SAMPLE_INTERVAL_MS (no radio, no SD write);
// logSensorDataToSD() reads + resets them once per SD_LOG_INTERVAL_MS.
float imuPeakMotionMag = 0;
float imuSumSqMotionMag = 0;
int imuSampleCount = 0;
float imuLastAx = 0, imuLastAy = 0, imuLastAz = 1;
float imuLastGx = 0, imuLastGy = 0, imuLastGz = 0;

// ---- MLX90632 (non-contact IR temperature, I2C) -- fixed address 0x3A ----
Adafruit_MLX90632 mlx;
bool mlxReady = false;
float mlxObjectTempCached = NAN;

// ---- SD card (onboard slot, SDMMC) ----
// The real dataset: one combined row of every sensor's current reading,
// written every SD_LOG_INTERVAL_MS (~1s). File is opened once at boot and
// kept open (append mode) rather than re-opened per write, which would be
// far slower and harder on the card.
bool sdReady = false;
File dataLogFile;

#if ENABLE_CAMERA
// Freenove ESP32-S3 WROOM camera pins
#define PWDN_GPIO_NUM   -1
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM   15
#define SIOD_GPIO_NUM   4
#define SIOC_GPIO_NUM   5

#define Y9_GPIO_NUM     16
#define Y8_GPIO_NUM     17
#define Y7_GPIO_NUM     18
#define Y6_GPIO_NUM     12
#define Y5_GPIO_NUM     10
#define Y4_GPIO_NUM     8
#define Y3_GPIO_NUM     9
#define Y2_GPIO_NUM     11

#define VSYNC_GPIO_NUM  6
#define HREF_GPIO_NUM   7
#define PCLK_GPIO_NUM   13

void setupCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  config.frame_size = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {
    Serial.println("Camera init failed");
    while (true) {
      delay(1000);
    }
  }
}
#endif

void setupBME280() {
  // SDO strapped to GND -> 0x76, strapped to VCC -> 0x77. Try both in case
  // wiring shifted while adding the other sensors.
  bmeReady = bme.begin(BME280_I2C_ADDR_PRIMARY, &Wire) || bme.begin(BME280_I2C_ADDR_ALT, &Wire);
  if (bmeReady) {
    bme.setSampling(BME280_MODE, BME280_TEMP_OVERSAMPLING, BME280_PRESSURE_OVERSAMPLING,
                     BME280_HUMIDITY_OVERSAMPLING, BME280_FILTER, BME280_STANDBY_DURATION);
  }
  Serial.println(bmeReady ? "BME280 initialized" : "BME280 not found at 0x76 or 0x77 -- check wiring/power");
}

void setupSCD41() {
  scd4x.begin(Wire, SCD41_I2C_ADDR_62);
  // Clean-state dance recommended by Sensirion: wake, stop any prior
  // measurement, reinit, then start periodic measurement.
  scd4x.wakeUp();
  scd4x.stopPeriodicMeasurement();
  scd4x.reinit();
#if SCD41_LOW_POWER_MODE
  int16_t err = scd4x.startLowPowerPeriodicMeasurement(); // ~30s/reading, lower current draw
#else
  int16_t err = scd4x.startPeriodicMeasurement(); // ~5s/reading
#endif
  scdReady = (err == 0);
  Serial.println(scdReady ? "SCD41 initialized" : "SCD41 not found/failed to start at 0x62 -- check wiring");
}

void setupENS160() {
  // ADDR strapped low -> 0x52, strapped high -> 0x53. Try both.
  const uint8_t addrsToTry[] = {ENS160_I2C_ADDR_PRIMARY, ENS160_I2C_ADDR_ALT};
  for (uint8_t addr : addrsToTry) {
    ens160.begin(&Wire, addr);
    int retries = 20;
    while (!ens160.init() && retries-- > 0) {
      delay(50);
    }
    if (retries > 0) {
      ensReady = true;
      ens160.startStandardMeasure();
      Serial.print("ENS160 initialized at 0x");
      Serial.println(addr, HEX);
      return;
    }
  }
  ensReady = false;
  Serial.println("ENS160 not found at 0x52 or 0x53 -- check wiring/power");
}

void setupVEML7700() {
  vemlReady = veml.begin();
  if (vemlReady) {
    veml.setIntegrationTime(VEML7700_INTEGRATION_TIME);
  }
  Serial.println(vemlReady ? "VEML7700 initialized" : "VEML7700 not found at 0x10 -- check wiring");
}

void setupAS7343() {
  as7343Ready = as7343.begin();
  if (as7343Ready) {
    as7343.setGain(AS7343_GAIN_SETTING);
    as7343.setATIME(AS7343_ATIME_VALUE);
    as7343.setASTEP(AS7343_ASTEP_VALUE);
  }
  Serial.println(as7343Ready ? "AS7343 initialized" : "AS7343 not found at 0x39 -- check wiring");
}

void setupLSM6DS3TRC() {
  lsmReady = lsm6ds3trc.begin_I2C();
  if (lsmReady) {
    // Was previously left at whatever Adafruit_LSM6DS defaults to (104 Hz) --
    // now explicit and tunable from sensor_config.h.
    lsm6ds3trc.setAccelDataRate(LSM6DS_ACCEL_RATE);
    lsm6ds3trc.setGyroDataRate(LSM6DS_GYRO_RATE);
  }
  Serial.println(lsmReady ? "LSM6DS3TR-C initialized" : "LSM6DS3TR-C not found at 0x6A -- check wiring");
}

void setupMLX90632() {
  mlxReady = mlx.begin();
  if (mlxReady) {
    mlx.reset();
    mlx.setMode(MLX90632_MODE_CONTINUOUS);
    mlx.setMeasurementSelect(MLX90632_MEAS_MEDICAL);
    mlx.setRefreshRate(MLX90632_REFRESH_RATE);
    mlx.resetNewData();
    Serial.println("MLX90632 initialized");
  } else {
    Serial.println("MLX90632 not found at 0x3A -- check wiring");
  }
}

void setupSD() {
  SD_MMC.setPins(SD_CLK_GPIO, SD_CMD_GPIO, SD_D0_GPIO);
  sdReady = SD_MMC.begin("/sdcard", true); // true = 1-bit mode (only D0 wired)
  if (!sdReady) {
    Serial.println("SD card not found -- check it's inserted");
    return;
  }

  // Write a header row only when creating the file for the first time, so
  // re-flashing/rebooting appends to the existing log instead of duplicating
  // headers partway through the file.
  bool logExists = SD_MMC.exists("/data_log.csv");
  dataLogFile = SD_MMC.open("/data_log.csv", FILE_APPEND);
  if (dataLogFile && !logExists) {
    dataLogFile.println("uptime_ms,"
                         "bme_temp_c,bme_humidity_pct,bme_pressure_hpa,"
                         "co2_ppm,aqi,tvoc_ppb,eco2_ppm,lux,"
                         "as7343_dominant_channel,as7343_dominant_nm,as7343_clear,"
                         "mlx_skin_temp_c,"
                         "imu_ax_g,imu_ay_g,imu_az_g,imu_gx_dps,imu_gy_dps,imu_gz_dps,"
                         "imu_motion_mag_peak,imu_motion_mag_rms,imu_sample_count");
    dataLogFile.flush();
  }

  Serial.println(dataLogFile ? "SD card initialized, logging to /data_log.csv"
                              : "SD card mounted but failed to open log file");
}

// ---- Non-blocking per-loop updates for the sensors that measure
// asynchronously, so a slow/unready sensor never stalls the main loop (and
// therefore never stalls MQTT/WiFi or every other sensor). Each just checks
// "is new data ready?" and caches the latest value if so; logSensorDataToSD()
// always logs whatever was last cached. ----

void updateSCD41() {
  if (!scdReady) return;
  bool dataReadyFlag = false;
  if (scd4x.getDataReadyStatus(dataReadyFlag) != 0 || !dataReadyFlag) return;
  uint16_t co2 = 0;
  float temp = 0, humidity = 0;
  if (scd4x.readMeasurement(co2, temp, humidity) == 0 && co2 != 0) {
    scdCo2Cached = co2;
  }
}

void updateENS160() {
  if (!ensReady) return;
  if (ens160.update() != RESULT_OK) return;
  if (!ens160.hasNewData()) return;
  ensAqiCached = (uint8_t)ens160.getAirQualityIndex_UBA();
  ensTvocCached = ens160.getTvoc();
  ensEco2Cached = ens160.getEco2();
}

void updateAS7343() {
  if (!as7343Ready) return;

  if (!as7343MeasuringStarted) {
    as7343.startMeasurement();
    as7343MeasuringStarted = true;
    return;
  }
  if (!as7343.dataReady()) return;

  uint16_t raw[18];
  as7343.readAllChannels(raw);
  as7343MeasuringStarted = false; // kick off the next measurement cycle next time

  // VIS_TL_0/VIS_BR_0 (raw indices 4/5) are this cycle's "clear" channels.
  uint16_t maxVal = 0;
  for (int i = 0; i < AS7343_CHANNEL_COUNT; i++) {
    uint16_t v = raw[AS7343_CHANNELS[i].rawIdx];
    as7343ChannelCached[i] = v;
    if (v > maxVal) {
      maxVal = v;
      as7343DominantName = AS7343_CHANNELS[i].name;
      as7343DominantNm = AS7343_CHANNELS[i].nm;
    }
  }
  as7343ClearCached = (raw[4] + raw[5]) / 2.0F;
}

void updateMLX90632() {
  if (!mlxReady) return;
  if (!mlx.isNewData()) return;
  double objectTemp = mlx.getObjectTemperature();
  if (!isnan(objectTemp)) {
    mlxObjectTempCached = objectTemp;
  }
  mlx.resetNewData();
}

void connectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Connecting to MQTT... ");

    if (mqttClient.connect("esp32_camera_client")) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.println(mqttClient.state());
      delay(2000);
    }
  }
}

#if ENABLE_CAMERA
void publishStatus() {
  if (!mqttClient.connected()) {
    connectMQTT();
  }

  String payload = "{";
  payload += "\"device\":\"esp32_camera\",";
  payload += "\"status\":\"online\",";
  payload += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  payload += "\"wifi_rssi\":" + String(WiFi.RSSI()) + ",";
  payload += "\"frames_uploaded\":" + String(framesUploaded) + ",";
  payload += "\"last_http_code\":" + String(lastHttpCode) + ",";
  payload += "\"uptime_seconds\":" + String(millis() / 1000) + ",";
  payload += "\"free_heap\":" + String(ESP.getFreeHeap());
  payload += "}";

  bool ok = mqttClient.publish(mqttTopic, payload.c_str());

  Serial.print(ok ? "MQTT published: " : "MQTT publish FAILED: ");
  Serial.println(payload);
}
#endif

// Shared envelope + publish for both the slow-sensor and IMU messages --
// `live` is just the inner `{"bme280":{...}, ...}` object each caller builds.
void publishLive(const String &live) {
  if (!mqttClient.connected()) {
    connectMQTT();
  }

  // No "ts" field -- the backend stamps arrival time server-side
  // (this board has no synced clock).
  String payload = "{";
  payload += "\"device_id\":\"esp32_01\",";
  payload += "\"device\":{";
  payload += "\"rssi\":" + String(WiFi.RSSI()) + ",";
  payload += "\"uptimeSec\":" + String(millis() / 1000);
  payload += "},";
  payload += "\"live\":" + live;
  payload += "}";

  bool ok = mqttClient.publish(sensorTopic, payload.c_str());

  Serial.print(ok ? "Published: " : "Publish FAILED (check MQTT buffer size/connection): ");
  Serial.println(payload);
}

// Runs on its own IMU_SAMPLE_INTERVAL_MS (100 Hz) timer in loop(). Pure
// local I2C read + math, no radio, no SD write -- just updates the
// accumulator that logSensorDataToSD() drains once per SD log cycle.
void sampleImu() {
  if (!lsmReady) return;

  sensors_event_t accel, gyro, temp;
  lsm6ds3trc.getEvent(&accel, &gyro, &temp);
  // Adafruit's getEvent() returns SI units (m/s^2, rad/s); the dashboard's
  // existing schema/history charts use g's and deg/s (set by simulator.py).
  const float G = 9.80665F;
  const float RAD2DEG = 180.0F / PI;
  imuLastAx = accel.acceleration.x / G;
  imuLastAy = accel.acceleration.y / G;
  imuLastAz = accel.acceleration.z / G;
  imuLastGx = gyro.gyro.x * RAD2DEG;
  imuLastGy = gyro.gyro.y * RAD2DEG;
  imuLastGz = gyro.gyro.z * RAD2DEG;

  float motionMag = sqrt(imuLastAx * imuLastAx + imuLastAy * imuLastAy + (imuLastAz - 1) * (imuLastAz - 1)) * G;
  if (motionMag > imuPeakMotionMag) imuPeakMotionMag = motionMag;
  imuSumSqMotionMag += motionMag * motionMag;
  imuSampleCount++;
  // No SD write here -- 100Hz is just local accumulation (peak/RMS tracking).
  // logSensorDataToSD() drains this into one row every SD_LOG_INTERVAL_MS.
}

// Runs on its own SD_LOG_INTERVAL_MS (~1s) timer in loop() -- this is the
// real dataset. Writes one CSV row with every sensor's current reading,
// including the IMU's peak/RMS motion summary since the last row (then
// resets that accumulator for the next ~1s window). Never touches the
// radio -- SD writes are cheap, this can run as often as the professor
// wants without a battery cost.
void logSensorDataToSD() {
  if (!sdReady || !dataLogFile) return;

  float bmeTemp = NAN, bmeHumidity = NAN, bmePressure = NAN;
  if (bmeReady) {
    bmeTemp = bme.readTemperature();
    bmeHumidity = bme.readHumidity();
    bmePressure = bme.readPressure() / 100.0F;
  }
  float vemlLux = NAN;
  if (vemlReady) {
    vemlLux = veml.readLux();
  }

  String row = String(millis()) + ",";
  row += (bmeReady ? String(bmeTemp, 2) : "") + ",";
  row += (bmeReady ? String(bmeHumidity, 2) : "") + ",";
  row += (bmeReady ? String(bmePressure, 2) : "") + ",";
  row += (scdReady ? String(scdCo2Cached) : "") + ",";
  row += (ensReady ? String(ensAqiCached) : "") + ",";
  row += (ensReady ? String(ensTvocCached) : "") + ",";
  row += (ensReady ? String(ensEco2Cached) : "") + ",";
  row += (vemlReady ? String(vemlLux, 1) : "") + ",";
  row += (as7343Ready && as7343DominantName != nullptr ? String(as7343DominantName) : "") + ",";
  row += (as7343Ready && as7343DominantName != nullptr ? String(as7343DominantNm) : "") + ",";
  row += (as7343Ready && as7343DominantName != nullptr ? String(as7343ClearCached, 1) : "") + ",";
  row += (mlxReady && !isnan(mlxObjectTempCached) ? String(mlxObjectTempCached, 2) : "") + ",";

  if (lsmReady && imuSampleCount > 0) {
    float rms = sqrt(imuSumSqMotionMag / imuSampleCount);
    row += String(imuLastAx, 3) + ",";
    row += String(imuLastAy, 3) + ",";
    row += String(imuLastAz, 3) + ",";
    row += String(imuLastGx, 2) + ",";
    row += String(imuLastGy, 2) + ",";
    row += String(imuLastGz, 2) + ",";
    row += String(imuPeakMotionMag, 3) + ",";
    row += String(rms, 3) + ",";
    row += String(imuSampleCount);

    imuPeakMotionMag = 0;
    imuSumSqMotionMag = 0;
    imuSampleCount = 0;
  } else {
    row += ",,,,,,,,"; // 9 IMU columns, all blank
  }

  dataLogFile.println(row);
  dataLogFile.flush(); // at ~1 write/sec this is cheap; guarantees nothing is lost to a sudden power cut
}

// Runs on its own MQTT_HEARTBEAT_INTERVAL_MS (30s) timer in loop() -- the
// radio only keys up once per cycle (the actual power saving), but this
// still carries every sensor's current reading so the dashboard keeps
// showing real values, just refreshed every 30s instead of continuously.
// The complete, finer-grained dataset (every 1s, full IMU peak/RMS) still
// only goes to the SD card via logSensorDataToSD().
void publishHeartbeat() {
  String live = "{";
  bool firstSensor = true;
  auto sep = [&]() {
    if (!firstSensor) live += ",";
    firstSensor = false;
  };

  if (bmeReady) {
    sep();
    live += "\"bme280\":{";
    live += "\"temp\":" + String(bme.readTemperature(), 2) + ",";
    live += "\"humidity\":" + String(bme.readHumidity(), 2) + ",";
    live += "\"pressure\":" + String(bme.readPressure() / 100.0F, 2);
    live += "}";
  }
  if (scdReady) {
    sep();
    live += "\"scd41\":{\"co2\":" + String(scdCo2Cached) + "}";
  }
  if (ensReady) {
    sep();
    live += "\"ens160\":{";
    live += "\"aqi\":" + String(ensAqiCached) + ",";
    live += "\"tvoc\":" + String(ensTvocCached) + ",";
    live += "\"eco2\":" + String(ensEco2Cached);
    live += "}";
  }
  if (vemlReady) {
    sep();
    live += "\"veml7700\":{\"lux\":" + String(veml.readLux(), 1) + "}";
  }
  if (as7343Ready && as7343DominantName != nullptr) {
    sep();
    live += "\"as7343\":{";
    live += "\"dominantChannel\":\"" + String(as7343DominantName) + "\",";
    live += "\"dominantNm\":" + String(as7343DominantNm) + ",";
    live += "\"clear\":" + String(as7343ClearCached, 1) + ",";
    live += "\"channels\":{";
    for (int i = 0; i < AS7343_CHANNEL_COUNT; i++) {
      if (i > 0) live += ",";
      live += "\"" + String(AS7343_CHANNELS[i].name) + "\":" + String(as7343ChannelCached[i], 0);
    }
    live += "}";
    live += "}";
  }
  if (lsmReady) {
    // Just the latest instantaneous sample here (not a 30s peak/RMS -- that
    // accumulator is drained every 1s by logSensorDataToSD(), so by the time
    // this fires it'd only ever reflect the last <1s anyway).
    const float G = 9.80665F;
    float motionMag = sqrt(imuLastAx * imuLastAx + imuLastAy * imuLastAy + (imuLastAz - 1) * (imuLastAz - 1)) * G;
    sep();
    live += "\"lsm6ds3tr\":{";
    live += "\"ax\":" + String(imuLastAx, 3) + ",";
    live += "\"ay\":" + String(imuLastAy, 3) + ",";
    live += "\"az\":" + String(imuLastAz, 3) + ",";
    live += "\"gx\":" + String(imuLastGx, 2) + ",";
    live += "\"gy\":" + String(imuLastGy, 2) + ",";
    live += "\"gz\":" + String(imuLastGz, 2) + ",";
    live += "\"motionMag\":" + String(motionMag, 3);
    live += "}";
  }
  if (mlxReady && !isnan(mlxObjectTempCached)) {
    sep();
    live += "\"mlx90632\":{\"skinTemp\":" + String(mlxObjectTempCached, 2) + "}";
  }
  live += "}";

  if (firstSensor) return; // nothing ready yet -- nothing to publish
  publishLive(live);
}

#if ENABLE_CAMERA
void uploadFrame() {
  camera_fb_t* fb = esp_camera_fb_get();

  if (!fb) {
    Serial.println("Camera capture failed");
    lastHttpCode = -999;
    publishStatus();
    return;
  }

  Serial.println("Captured image");

  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "image/jpeg");

  int code = http.POST(fb->buf, fb->len);
  lastHttpCode = code;

  if (code == 200) {
    framesUploaded++;
  }

  Serial.print("HTTP Response: ");
  Serial.println(code);

  http.end();
  esp_camera_fb_return(fb);

  publishStatus();
}
#endif

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("Starting...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    Serial.println(WiFi.status());
  }

  Serial.println("WiFi connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  Serial.print("Gateway: ");
  Serial.println(WiFi.gatewayIP());

  Serial.print("Subnet: ");
  Serial.println(WiFi.subnetMask());

  mqttClient.setServer(mqttBroker, mqttPort);
  // PubSubClient's default MQTT packet buffer is small enough that our
  // topic + a multi-sensor JSON payload can silently fail to publish
  // (publish() returns false, but nothing was checking it) -- force it
  // large enough for all 7 sensors at once.
  mqttClient.setBufferSize(1024);
  connectMQTT();

#if ENABLE_CAMERA
  Serial.println("Initializing camera...");
  setupCamera();
  Serial.println("Camera initialized!");
#endif

  Serial.println("Initializing I2C sensors...");
  Wire.begin(I2C_SDA_GPIO, I2C_SCL_GPIO);
  setupBME280();
  setupSCD41();
  setupENS160();
  setupVEML7700();
  setupAS7343();
  setupLSM6DS3TRC();
  setupMLX90632();

  Serial.println("Initializing SD card...");
  setupSD();
}

void loop() {
  mqttClient.loop();

#if ENABLE_CAMERA
  uploadFrame();
#endif

  // Non-blocking checks -- each returns immediately unless that sensor
  // actually has a fresh reading ready, so none of them can stall the loop.
  updateSCD41();
  updateENS160();
  updateAS7343();
  updateMLX90632();

  // Three independent millis()-based timers, not blocking delay() calls, so
  // none of them can stall each other -- in particular the 30s MQTT
  // heartbeat must never delay the 1s SD log or the 100Hz IMU sampling.
  unsigned long now = millis();

  static unsigned long lastImuSample = 0;
  if (now - lastImuSample >= IMU_SAMPLE_INTERVAL_MS) {
    lastImuSample = now;
    sampleImu(); // local only -- no SD write, no radio
  }

  static unsigned long lastSdLog = 0;
  if (now - lastSdLog >= SD_LOG_INTERVAL_MS) {
    lastSdLog = now;
    logSensorDataToSD(); // the real dataset -- no radio
  }

  static unsigned long lastHeartbeat = 0;
  if (now - lastHeartbeat >= MQTT_HEARTBEAT_INTERVAL_MS) {
    lastHeartbeat = now;
    publishHeartbeat(); // the only thing that touches the radio
  }

  delay(1); // keep the 100 Hz timer responsive without busy-spinning at full CPU
}
