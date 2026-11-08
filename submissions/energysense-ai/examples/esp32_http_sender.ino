/*
 * EnergySense AI - ESP32 telemetry HTTP bridge example
 *
 * Adapt the function arguments to the calibrated values already produced by
 * your firmware. This sketch does not calculate ADC calibration constants,
 * does not replace ZMPT101B/ACS712 calibration and does not operate the relay.
 *
 * Keep relay protection local. A failed HTTP request must never block or alter
 * the local threshold/relay code.
 */
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
// Set this to the LAN IP address of the computer running FastAPI.
const char* API_URL = "http://192.168.1.100:8000/api/v1/telemetry";

const char* EQUIPMENT_ID = "ES-01";
const char* APPLIANCE_ID = "pump-01";
const unsigned long TELEMETRY_INTERVAL_MS = 5000;
unsigned long lastTelemetryPost = 0;

String jsonNumber(float value, int decimals) {
  if (!isfinite(value)) return "null";
  return String(value, decimals);
}

void postEnergySenseTelemetry(
    float calibratedVrms,
    float calibratedIrms,
    float runtimeSeconds,
    float temperatureC,
    float vibrationRms,
    bool relayIsOn) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.setTimeout(3000);
  if (!http.begin(API_URL)) return;
  http.addHeader("Content-Type", "application/json");

  // Apparent power is expressed in VA (Vrms x Irms), not real power in W.
  const float apparentPowerVA = calibratedVrms * calibratedIrms;
  String payload = "{";
  payload += "\"equipment_id\":\"" + String(EQUIPMENT_ID) + "\",";
  payload += "\"appliance_id\":\"" + String(APPLIANCE_ID) + "\",";
  payload += "\"appliance_name\":\"Pump 01\",";
  payload += "\"vrms_v\":" + jsonNumber(calibratedVrms, 2) + ",";
  payload += "\"irms_a\":" + jsonNumber(calibratedIrms, 3) + ",";
  payload += "\"apparent_power_va\":" + jsonNumber(apparentPowerVA, 2) + ",";
  payload += "\"runtime_s\":" + jsonNumber(runtimeSeconds, 1) + ",";
  payload += "\"temperature_c\":" + jsonNumber(temperatureC, 2) + ",";
  payload += "\"vibration_rms\":" + jsonNumber(vibrationRms, 3) + ",";
  payload += "\"relay_state\":\"" + String(relayIsOn ? "ON" : "OFF") + "\",";
  payload += "\"source\":\"esp32\"}";

  const int httpCode = http.POST(payload);
  Serial.printf("EnergySense telemetry POST: HTTP %d\n", httpCode);
  http.end();
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  // Do not wait here in a way that blocks the local relay-protection routine
  // in the integrated firmware. This example waits only for this standalone demo.
  const unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(250);
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? "Wi-Fi connected" : "Wi-Fi unavailable; local control remains independent");
}

void loop() {
  // Replace these demo values with the calibrated variables from the existing
  // firmware. Do not interpret these example values as physical measurements.
  const float vrms = 230.0;
  const float irms = 1.5;
  const float runtimeSeconds = 3600.0;
  const float temperatureC = NAN;
  const float vibrationRms = NAN;
  const bool relayOn = true;

  if (millis() - lastTelemetryPost >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryPost = millis();
    postEnergySenseTelemetry(vrms, irms, runtimeSeconds, temperatureC, vibrationRms, relayOn);
  }

  // In the integrated project, keep your existing sensor scan and local relay
  // protection code running here independently of Wi-Fi and the API.
  delay(10);
}
