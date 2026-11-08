# ESP32 HTTP bridge example

`examples/esp32_http_sender.ino` is an integration example for the existing firmware, not a claim that physical hardware has been connected or validated.

1. Replace the Wi-Fi credentials and `API_URL` with your local values.
2. Replace the example `vrms`, `irms`, `runtimeSeconds` and `relayOn` variables with the corresponding values already produced by your firmware.
3. Connect only after the local sensor/threshold loop is running. Never wait for the API before executing the local relay protection path.
4. Keep the `source` field as `esp32` only when values genuinely come from the ESP32. Use `wokwi_simulated` or `synthetic` for simulated/demo data.
5. Confirm the POST response and verify the row in `ESAI_TELEMETRY` using the Db2 SQL editor.

The code calculates apparent power as `Vrms x Irms` and labels it VA. It does not calculate real power, power factor or kWh. Temperature and vibration are optional; the sample uses JSON `null` if their values are not available.

The example uses plain HTTP for a trusted local lab network. Do not expose the unauthenticated demo API to the public internet. A production deployment needs authentication, TLS, rate limiting and appropriate network controls.
