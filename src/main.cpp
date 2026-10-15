#include <Arduino.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "effects.h"

constexpr uint8_t EN_A = 9, IN_1 = 2, IN_2 = 3;
constexpr uint8_t EN_B = 10, IN_3 = 4, IN_4 = 5;
constexpr int MAX_PWM = 90;
int rampStartPwm = 50, sequencePwm = 80;
unsigned long rampRiseMs = 100;
constexpr long MAX_JOG_MS = 100;
constexpr long MAX_STROKE_MS = 250;
constexpr int MOTOR_A_SIGN = 1, MOTOR_B_SIGN = -1;
bool armed = false, moving = false;
unsigned long startedAt = 0, jogDuration = 0;
int targetA = 0, targetB = 0;
unsigned long durationA = 0, durationB = 0;
bool rampEnabled = true;
char line[64];
uint8_t used = 0;
bool discardLine = false;
struct Preset { const char *name; int a; int b; unsigned long ms; };
Preset presets[] = {
  {"PACK", 80, 0, 40},
  {"REACH", 0, 80, 40},
  {"WRAP", -80, 80, 25},
  {"RELEASE", -80, -80, 25},
  {"1", 80, 0, 40},
  {"2", -80, 0, 25},
  {"3", 0, 80, 40},
  {"4", 0, -80, 25},
  {"LEFT", 80, -80, 250},
  {"RIGHT", -80, 80, 250},
  {"RETURN_LEFT", -80, 80, 250},
  {"RETURN_RIGHT", 80, -80, 250},
  {"WIGGLE_LEFT", 80, -80, 100},
  {"WIGGLE_RIGHT", -80, 80, 100}
};

Preset *preset(const char *name) {
  if (name) for (auto &p : presets) if (!strcmp(name, p.name)) return &p;
  return nullptr;
}

void haltOutputs() {
  analogWrite(EN_A, 0);
  analogWrite(EN_B, 0);
  digitalWrite(IN_1, LOW); digitalWrite(IN_2, LOW);
  digitalWrite(IN_3, LOW); digitalWrite(IN_4, LOW);
  moving = false;
}

bool autoEnabled = false, watching = false, readyForVisit = false;
uint8_t visit = 0, stage = 0, step = 0;
uint8_t nearCount = 0, farCount = 0, slowSteps = 1, returnSteps = 1;
unsigned long lastRange = 0, lastReport = 0, pauseStarted = 0;
constexpr uint8_t ECHO_PIN = A4, TRIG_PIN = A5;
constexpr int NEAR_CM = 20, FAR_CM = 25;
unsigned long completedCount = 0, sequenceFinishedAt = 0;

void stopMotors() {
  haltOutputs(); stopEffects(); autoEnabled = false; stage = 0;
  nearCount = farCount = 0; readyForVisit = false;
}

void drive(uint8_t enable, uint8_t in1, uint8_t in2, int pwm) {
  digitalWrite(in1, pwm > 0 ? HIGH : LOW);
  digitalWrite(in2, pwm < 0 ? HIGH : LOW);
  analogWrite(enable, abs(pwm));
}

bool longStroke(const Preset *p) {
  return p && (!strcmp(p->name, "LEFT") || !strcmp(p->name, "RIGHT") ||
               !strcmp(p->name, "RETURN_LEFT") || !strcmp(p->name, "RETURN_RIGHT"));
}

int motionPwm(int target, unsigned long elapsed, unsigned long duration) {
  if (!target || elapsed >= duration) return 0;
  int magnitude = abs(target);
  if (rampEnabled && rampRiseMs && duration > 1) {
    const int initial = rampStartPwm < magnitude ? rampStartPwm : magnitude;
    const unsigned long rise = rampRiseMs < duration ? rampRiseMs : duration - 1;
    if (elapsed < rise) magnitude = initial + (magnitude - initial) * elapsed / rise;
  }
  return target > 0 ? magnitude : -magnitude;
}

void applyMotion() {
  const unsigned long elapsed = millis() - startedAt;
  drive(EN_A, IN_1, IN_2, motionPwm(targetA, elapsed, durationA));
  drive(EN_B, IN_3, IN_4, motionPwm(targetB, elapsed, durationB));
}

void help() {
  Serial.println(F("ARM | JOG a b ms | STOP | DISARM | STATUS | HELP"));
  Serial.println(F("DIR a b pwm msA [msB]: direction 0/1, 2=off, PWM 1..90, duration 1..500ms"));
  Serial.println(F("PACK | REACH | WRAP | RELEASE | PRESETS | SET name a b ms"));
  Serial.println(F("a,b: -90..90 PWM; ms: 1..100. Example: JOG 60 0 40"));
  Serial.println(F("STOP stops; DISARM or ! stops/disarms. Commands end with newline."));
  Serial.println(F("Upper/lowercase accepted. ARM once after startup."));
  Serial.println(F("Fine jog: 1=A wind, 2=A unwind, 3=B wind, 4=B unwind"));
  Serial.println(F("Wind: PWM80/40ms; unwind: PWM80/25ms. Tune with SET 2 -80 0 15"));
  Serial.println(F("DIST = live HC-SR04 cm; QUIET = hide readings; ROAR 1/2/3 = escalating piezo growls"));
  Serial.println(F("SET LEFT/RIGHT/RETURN_LEFT/RETURN_RIGHT a b ms: max 250ms"));
  Serial.println(F("RAMP start peak rise_ms: PWM 1..90, rise 0..500ms; AUTO off"));
  Serial.println(F("AUTO = ARM then enable 3-visit sequence; STOP cancels AUTO"));
}

bool number(char *token, long &value) {
  if (!token || !*token) return false;
  if (strlen(token) > 6) return false;
  char *end;
  value = strtol(token, &end, 10);
  return *end == '\0';
}

void startJog(int a, int b, unsigned long ms, bool ramp = false, unsigned long exactA = 0, unsigned long exactB = 0) {
  if (!armed) {
    Serial.println(F("DISARMED: type ARM then Enter once to enable motion"));
    return;
  }
  if (moving) {
    Serial.println(F("BUSY: wait for DONE; new motion was not queued"));
    return;
  }
  if (roaring) {
    Serial.println(F("BUSY: wait for ROAR DONE, or STOP"));
    return;
  }
  durationA = exactA ? exactA : a < 0 && b > 0 ? ms / 2 : ms;
  durationB = exactB ? exactB : b < 0 && a > 0 ? ms / 2 : ms;
  rampEnabled = ramp;
  targetA = a * MOTOR_A_SIGN; targetB = b * MOTOR_B_SIGN;
  startedAt = millis(); jogDuration = ms; moving = true;
  applyMotion();
  Serial.println(F("JOG started"));
}

void finishSequence() {
  stage = 0; ++completedCount; visit = (visit + 1) % 3;
  sequenceFinishedAt = millis();
  nearCount = farCount = 0; readyForVisit = false;
  Serial.print(F("SEQUENCE DONE; completed count=")); Serial.print(completedCount);
  Serial.print(F("; next sequence=")); Serial.println(visit + 1);
  Serial.println(F("Next trigger enabled after 500ms; keep target below 20cm"));
}

void serviceSequence() {
  if (!autoEnabled || !stage || roaring || moving) return;
  if (stage == 1) { stage = visit == 2 ? 5 : 2; step = 0; }
  else if (millis() - pauseStarted < (stage == 5 ? 80UL : 250UL)) return;
  const uint8_t count = stage == 5 ? 9 : 1;
  if (step >= count) {
    if (stage == 2) {
      step = 0; pauseStarted = millis();
      stage = 4;
      return;
    }
    finishSequence(); return;
  }
  int a, b;
  unsigned long timeA, timeB;
  if (stage == 5) {
    const uint8_t phase = step % 3;
    a = phase == 0 ? sequencePwm : phase == 1 ? -sequencePwm : 0;
    b = phase == 0 ? 0 : phase == 1 ? sequencePwm : -sequencePwm;
    timeA = phase == 0 ? 250 : 50;
    timeB = phase < 2 ? 250 : 50;
  } else {
    const bool left = (visit == 0) != (stage == 4);
    a = left ? sequencePwm : -sequencePwm; b = -a;
    timeA = left ? 500 : 125;
    timeB = left ? 125 : 500;
  }
  startJog(a, b, timeA > timeB ? timeA : timeB, true, timeA, timeB); ++step;
}

void acceptRange(int cm) {
  if (!autoEnabled || stage) return;
  if (!readyForVisit) {
    if (millis() - sequenceFinishedAt < 500UL) { nearCount = 0; return; }
    readyForVisit = true;
  }
  if (cm < 2 || cm > 400) { nearCount = farCount = 0; return; }
  if (cm >= FAR_CM) {
    nearCount = 0;
    if (farCount < 3) ++farCount;

  } else if (cm < NEAR_CM && readyForVisit) {
    farCount = 0;
    if (++nearCount >= 3) {
      readyForVisit = false; nearCount = farCount = 0; step = 0;
      stage = 1;
      pauseStarted = millis() - 250;
      Serial.print(F("SEQUENCE START ")); Serial.println(visit + 1);
      startRoar(visit + 1);
    }
  } else { nearCount = farCount = 0; }
}

void serviceRange() {
  if ((!watching && !autoEnabled) || moving || roaring || stage || Serial.available()) return;
  if (millis() - lastRange < 70) return;
  lastRange = millis();
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10); digitalWrite(TRIG_PIN, LOW);
  const unsigned long us = pulseIn(ECHO_PIN, HIGH, 25000UL);
  const int cm = us >= 116 && us <= 23200 ? us / 58 : -1;
  if (watching && millis() - lastReport >= 300) {
    lastReport = millis();
    if (cm < 0) Serial.println(F("DIST: no valid echo (not zero distance)"));
    else { Serial.print(F("DIST cm: ")); Serial.println(cm); }
  }
  acceptRange(cm);
}

void command() {
  for (uint8_t i = 0; line[i]; ++i) line[i] = toupper((unsigned char)line[i]);
  char *op = strtok(line, " \t");
  if (!op) return;
  if (!strcmp(op, "RAMP")) {
    long initial = 0, peak = 0, rise = 0;
    bool valid = number(strtok(nullptr, " \t"), initial);
    valid = number(strtok(nullptr, " \t"), peak) && valid;
    valid = number(strtok(nullptr, " \t"), rise) && valid;
    stopMotors();
    if (!valid || strtok(nullptr, " \t") || initial < 1 || peak < initial ||
        peak > MAX_PWM || rise < 0 || rise > 500) {
      Serial.println(F("Use RAMP start peak rise_ms: 1 <= start <= peak <= 90; ms0..500")); return;
    }
    rampStartPwm = initial; sequencePwm = peak; rampRiseMs = rise;
    Serial.println(F("RAMP set; AUTO off; settings reset on reboot"));
    return;
  }
  if (!strcmp(op, "DIR")) {
    long a = 0, b = 0, pwm = 0, ms = 0, msB = 0;
    bool valid = number(strtok(nullptr, " \t"), a);
    valid = number(strtok(nullptr, " \t"), b) && valid;
    valid = number(strtok(nullptr, " \t"), pwm) && valid;
    valid = number(strtok(nullptr, " \t"), ms) && valid;
    char *durationBToken = strtok(nullptr, " \t");
    if (durationBToken) valid = number(durationBToken, msB) && msB >= 1 && msB <= 500 && valid;
    if (!valid || strtok(nullptr, " \t") || a < 0 || a > 2 || b < 0 || b > 2 ||
        pwm < 1 || pwm > MAX_PWM || ms < 1 || ms > 500) {
      stopMotors(); Serial.println(F("Use DIR a b pwm msA [msB]: 0/1 direction, 2=off, PWM1..90, ms1..500")); return;
    }
    if (autoEnabled) { Serial.println(F("STOP AUTO before direction test")); return; }
    startJog((a == 2 ? 0 : a ? pwm : -pwm) * MOTOR_A_SIGN, (b == 2 ? 0 : b ? pwm : -pwm) * MOTOR_B_SIGN, msB > ms ? msB : ms, false, durationBToken ? ms : 0, msB);
    return;
  }
  if (!strcmp(op, "ROAR")) {
    char *arg = strtok(nullptr, " \t");
    long level = 1;
    const bool valid = !arg || number(arg, level);
    stopMotors();
    if (!valid || strtok(nullptr, " \t") || level < 1 || level > 3) {
      Serial.println(F("Use ROAR 1, ROAR 2 or ROAR 3")); return;
    }
    startRoar(level); return;
  }
  if (!strcmp(op, "STEPS")) {
    long slow = 0, back = 0;
    bool valid = number(strtok(nullptr, " \t"), slow);
    valid = number(strtok(nullptr, " \t"), back) && valid;
    if (!valid || strtok(nullptr, " \t") || slow != 1 || back != 1) {
      stopMotors(); Serial.println(F("Continuous mode uses one stroke; tune duration with SET LEFT/RIGHT/RETURN_LEFT/RETURN_RIGHT")); return;
    }
    stopMotors(); slowSteps = slow; returnSteps = back;
    Serial.println(F("STEPS set; AUTO off")); return;
  }
  const bool setting = !strcmp(op, "SET");
  if (!strcmp(op, "JOG") || setting) {
    Preset *p = setting ? preset(strtok(nullptr, " \t")) : nullptr;
    long a = 0, b = 0, ms = 0;
    bool valid = number(strtok(nullptr, " \t"), a);
    valid = number(strtok(nullptr, " \t"), b) && valid;
    valid = number(strtok(nullptr, " \t"), ms) && valid;
    valid = !strtok(nullptr, " \t") && valid;
    if (!valid || (setting && !p) || a < -MAX_PWM || a > MAX_PWM || b < -MAX_PWM ||
        b > MAX_PWM || ms < 1 || ms > (longStroke(p) ? MAX_STROKE_MS : MAX_JOG_MS)) {
      stopMotors();
      Serial.println(F("ERR PWM -90..90; JOG/short presets max100ms, LEFT/RIGHT/returns max250ms"));
      return;
    }
    if (setting) {
      if (moving) { Serial.println(F("ERR wait for DONE before SET")); return; }
      stopMotors();
      p->a = a; p->b = b; p->ms = ms;
      Serial.println(F("SET OK (RAM only; resets on reboot)"));
      return;
    }
    if (autoEnabled) { Serial.println(F("STOP AUTO before manual jog")); return; }
    startJog(a, b, ms);
    return;
  }
  if (strtok(nullptr, " \t")) {
    stopMotors();
    Serial.println(F("ERR extra arguments; stopped, arm state unchanged"));
  } else if (!strcmp(op, "STOP")) {
    stopMotors(); Serial.println(F("STOPPED; arm state unchanged"));
  } else if (!strcmp(op, "DISARM")) {
    stopMotors(); armed = false; Serial.println(F("STOPPED/DISARMED"));
  } else if (!strcmp(op, "ARM")) {
    stopMotors(); armed = true; Serial.println(F("ARMED"));
  } else if (!strcmp(op, "STATUS")) {
    Serial.print(armed ? F("ARMED ") : F("DISARMED "));
    Serial.println(moving ? F("MOVING") : F("STOPPED"));
    Serial.print(F("AUTO=")); Serial.print(autoEnabled);
    Serial.print(F(" completed=")); Serial.print(completedCount);
    Serial.print(F(" sequence=")); Serial.print(visit + 1);
    Serial.print(F(" busy=")); Serial.println(stage != 0);
  } else if (!strcmp(op, "DIAG")) {
    Serial.print(F("targetA=")); Serial.print(targetA);
    Serial.print(F(" targetB=")); Serial.print(targetB);
    Serial.print(F(" moving=")); Serial.println(moving);
#ifdef __AVR_ATmega328P__
    Serial.print(F("TCCR1A=")); Serial.print(TCCR1A);
    Serial.print(F(" TCCR1B=")); Serial.print(TCCR1B);
    Serial.print(F(" OCR1A=")); Serial.print(OCR1A);
    Serial.print(F(" OCR1B=")); Serial.println(OCR1B);
    Serial.print(F("DDRB=")); Serial.print(DDRB);
    Serial.print(F(" PORTB=")); Serial.print(PORTB);
    Serial.print(F(" DDRD=")); Serial.print(DDRD);
    Serial.print(F(" PORTD=")); Serial.println(PORTD);
#endif
  } else if (!strcmp(op, "HELP")) {
    help();
  } else if (!strcmp(op, "DIST") || !strcmp(op, "SCAN")) {
    stopMotors(); watching = true;
    Serial.println(F("HC-SR04: ECHO=A4, TRIG=A5. Live distance on; AUTO off"));
  } else if (!strcmp(op, "QUIET")) {
    watching = false;
  } else if (!strcmp(op, "AUTO")) {
    stopMotors();
    if (!armed) { Serial.println(F("Type ARM first")); return; }
    autoEnabled = true; visit = 0; completedCount = 0; readyForVisit = true;
    Serial.println(F("AUTO on: current pose is upright/start; trigger BELOW 20cm. Counter=0"));

  } else if (!strcmp(op, "PRESETS")) {
    for (const auto &p : presets) {
      Serial.print(p.name); Serial.print(' '); Serial.print(p.a);
      Serial.print(' '); Serial.print(p.b); Serial.print(' '); Serial.println(p.ms);
    }
  } else if (preset(op)) {
    if (autoEnabled) { Serial.println(F("STOP AUTO before manual jog")); return; }
    const auto &p = *preset(op);
    startJog(p.a, p.b, p.ms);
  } else {
    stopMotors();
    Serial.println(F("ERR unknown command; type HELP. Arm state unchanged"));
  }
}

void setup() {
  digitalWrite(TRIG_PIN, LOW); pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);
  digitalWrite(BUZZER_PIN, LOW); pinMode(BUZZER_PIN, OUTPUT);
  const uint8_t pins[] = {EN_A, EN_B, IN_1, IN_2, IN_3, IN_4};
  for (uint8_t pin : pins) { digitalWrite(pin, LOW); pinMode(pin, OUTPUT); }
  stopMotors();
  Serial.begin(115200);
  Serial.println(F("BOOT v28 TIMED RAMP: DISARMED; DIST / ROAR / ARM"));
  help();
}

void loop() {
  serviceEffects();
  if (moving && millis() - startedAt >= jogDuration) {
    haltOutputs(); pauseStarted = millis();
    Serial.println(F("DONE"));
  }
  if (moving) applyMotion();
  serviceSequence();
  serviceRange();
  if (!Serial.available()) return;
  const char c = Serial.read();
  if (c == '!') {
    stopMotors(); armed = false; used = 0; discardLine = true;
    Serial.println(F("STOPPED/DISARMED; send newline before next command"));
  } else if (c == '\n' || c == '\r') {
    if (!discardLine && used) { line[used] = '\0'; command(); }
    used = 0; discardLine = false;
  } else if (!discardLine) {
    if (c == '\b' || c == 127) { if (used) --used; }
    else if (used < sizeof(line) - 1 && ((c >= 32 && c <= 126) || c == '\t')) line[used++] = c;
    else {
      stopMotors(); used = 0; discardLine = true;
      Serial.println(F("ERR bad/long line; stopped. Send Enter to clear; arm state unchanged"));
    }
  }
}
