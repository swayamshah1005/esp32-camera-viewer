#include <Arduino.h>
#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <PubSubClient.h>

const char* ssid = "Ministry Of Coffee";
const char* password = "Australia";

const char* serverUrl = "http://192.168.27.103:8000/upload";

// MQTT
const char* mqttBroker = "192.168.27.103";
const int mqttPort = 1883;
const char* mqttTopic = "esp32/status";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

int framesUploaded = 0;
int lastHttpCode = 0;

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

  mqttClient.publish(mqttTopic, payload.c_str());

  Serial.print("MQTT published: ");
  Serial.println(payload);
}

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
  connectMQTT();

  Serial.println("Initializing camera...");
  setupCamera();
  Serial.println("Camera initialized!");
}

void loop() {
  mqttClient.loop();
  uploadFrame();
  delay(1000);
}