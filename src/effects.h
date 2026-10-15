#pragma once
#include <Arduino.h>

constexpr uint8_t BUZZER_PIN = 6;
bool roaring = false;
uint8_t roarLevel = 1;
unsigned long roarStarted = 0, roarUpdated = 0;
uint16_t roarNoise = 0xACE1u;

unsigned long roarDuration(uint8_t level) {
  return level == 1 ? 1400UL : level == 2 ? 2100UL : 2800UL;
}

void stopEffects() {
  noTone(BUZZER_PIN);
  roaring = false;
}

void startRoar(uint8_t level = 1) {
  roarLevel = level < 1 ? 1 : level > 3 ? 3 : level;
  roaring = true;
  roarStarted = millis();
  roarUpdated = roarStarted - 6;
  roarNoise = 0xACE1u;
  Serial.print(F("ROAR level ")); Serial.println(roarLevel);
}

void serviceEffects() {
  if (!roaring) return;
  const unsigned long now = millis(), age = now - roarStarted;
  const unsigned long duration = roarDuration(roarLevel);
  if (age >= duration) {
    stopEffects(); Serial.println(F("ROAR DONE")); return;
  }
  if (now - roarUpdated < 6) return;
  roarUpdated = now;
  roarNoise = (roarNoise >> 1) ^ ((roarNoise & 1u) ? 0xB400u : 0u);
  const unsigned long cycle = roarLevel == 1 ? 470 : roarLevel == 2 ? 610 : 760;
  const unsigned long phase = age % cycle;
  const unsigned long voiced = cycle * (roarLevel == 1 ? 70 : roarLevel == 2 ? 88 : 97) / 100;
  if (phase >= voiced) { noTone(BUZZER_PIN); return; }
  int throat = 190 - int(phase * 95 / cycle) - int(age * 25 / duration);
  throat += int(roarNoise % (10 + roarLevel * 8)) - (5 + roarLevel * 4);
  const uint8_t flutter = (age / 6) % 8;
  int hz = throat;
  if (flutter == 0 || (roarLevel >= 2 && flutter == 3) || (roarLevel == 3 && flutter == 6)) {
    hz = throat * (roarLevel + 2) + int(roarNoise % (60 * roarLevel));
  }
  if (age < 100) hz += (100 - age) * roarLevel * 3;
  if (hz < 65) hz = 65;
  tone(BUZZER_PIN, hz);
}
