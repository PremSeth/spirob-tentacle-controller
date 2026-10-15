"""Run actual firmware with fake Arduino I/O: python3 tests/check_controller.py."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as work:
    work = Path(work)
    (work / 'Arduino.h').write_text(r'''
#pragma once
#include <cstdint>
#include <string>
#define F(x) x
#define LOW 0
#define HIGH 1
#define OUTPUT 1
#define INPUT 0
#define A4 18
#define A5 19
inline unsigned long now = 0;
inline int pwm[32] = {}, digital[32] = {};
inline unsigned long millis() { return now; }
inline void analogWrite(int p, int v) { pwm[p] = v; }
inline void digitalWrite(int p, int v) { digital[p] = v; }
inline void pinMode(int, int) {}
inline void delayMicroseconds(unsigned int) {}
inline unsigned long echoUs = 0;
inline int pingCount = 0;
inline unsigned long pulseIn(int, int, unsigned long) { ++pingCount; return echoUs; }
inline unsigned int pitch = 0;
inline void tone(int, unsigned int hz) { pitch = hz; }
inline void noTone(int) { pitch = 0; }
struct SerialMock {
  std::string input;
  void begin(int) {}
  int available() { return input.size(); }
  char read() { char c = input[0]; input.erase(0,1); return c; }
  template<class T> void print(T) {}
  template<class T> void println(T) {}
};
inline SerialMock Serial;
''')
    (work / 'check.cpp').write_text(r'''
#include <cassert>
#include "main.cpp"
void send(const std::string &s) { Serial.input += s; while (Serial.available()) loop(); }
void off() { assert(pwm[EN_A] == 0 && pwm[EN_B] == 0 && !moving); }
int main() {
  setup(); off(); assert(!armed);
  assert(rampStartPwm == 50 && sequencePwm == 80 && rampRiseMs == 100);
  send("dist\n"); assert(watching); now += 300; echoUs = 580; loop(); assert(pingCount == 1); off();
  send("quiet\n"); assert(!watching);
  send("roar\n"); loop(); assert(roaring && pitch > 0); off();
  now += 1399; loop(); assert(roaring);
  now += 1; loop(); assert(!roaring && pitch == 0); off();
  send("roar\n!\n"); assert(!roaring && pitch == 0); off();
  send("arm\nroar\n1\n"); off(); assert(roaring); // no motor during effect
  send("stop\n"); assert(!roaring && pitch == 0); off();
  for (int level=1; level<=3; ++level) {
    send(std::string("roar ") + char('0'+level) + "\n");
    assert(roaring && roarLevel == level); off();
    for(unsigned long t=0; t<roarDuration(level); ++t) { loop(); assert(roaring); ++now; }
    loop(); assert(!roaring && pitch == 0); off();
  }
  send("roar 4\n"); assert(!roaring); off();
  send("roar 3\n!\n"); assert(!roaring && pitch == 0); off();
  send("disarm\n");
  send("PACK\n"); off();
  send("ARM\nPACK\n"); assert(moving && pwm[EN_A] == 80 && pwm[EN_B] == 0);
  auto deadline = startedAt;
  send("WRAP\n"); assert(startedAt == deadline && pwm[EN_B] == 0);
  now += 39; loop(); assert(moving);
  now += 1; loop(); off();
  send("WRAP\n"); assert(digital[IN_1] == LOW && digital[IN_2] == HIGH);
  assert(pwm[EN_A] == 80 && pwm[EN_B] == 80 && digital[IN_4] == HIGH);
  send("!"); off(); assert(!armed);
  send("ARM\n"); assert(!armed); // discarded until newline
  send("SET WRAP -60 80 50\n"); off(); assert(preset("WRAP")->ms == 50);
  send("ARM\nWRAP\n"); assert(pwm[EN_A] == 60 && pwm[EN_B] == 80);
  now += 50; loop(); off();
  send("SET PACK 91 0 100\n"); assert(armed); off();
  send("ARM\nSET TYPO 80 0 100\n"); assert(armed); off();
  send("ARM\nJOG 80 0 -1\n"); assert(armed); off();
  send("ARM\nJOG 80 0 101\n"); assert(armed); off();
  send("ARM\nJOG 80 0\n"); assert(armed); off();
  send("ARM\nPACK extra\n"); assert(armed); off();
  send("ARM\nPACK\n" + std::string(80, 'X') + "\n"); assert(armed); off();
  send("ARM\nRELEASE\n"); assert(pwm[EN_A] == 80 && digital[IN_3] == HIGH);
  send("STOP\n"); off(); assert(armed);
  send("ARM\nREACH\n"); assert(pwm[EN_A] == 0 && pwm[EN_B] == 80);
  now += 100; loop(); off(); // expires with no further input
  send("disarm\n"); off(); assert(!armed);
  send("badcommand\n"); off(); assert(!armed);
  send("arm\r\npack\r\n"); assert(armed && moving);
  send("stop\n"); off(); assert(armed);
  send("pacx\bK\n"); assert(moving); // backspace editing
  send("stop\n"); off();
  send("jog\t80\t0\t20\n"); assert(moving);
  now += 20; loop(); off();
  send("jog 80 0 20\n"); assert(moving);
  send("typo\n"); off(); assert(armed); // malformed commands stop but preserve arm
  send("!\n"); off(); assert(!armed);
  send("pack\n"); off(); assert(!armed);
  send("arm\n");
  for (const auto &p : presets) { assert(abs(p.a) <= MAX_PWM && abs(p.b) <= MAX_PWM && p.ms <= static_cast<unsigned long>(longStroke(&p) ? MAX_STROKE_MS : MAX_JOG_MS)); }
  for (char key = '1'; key <= '4'; ++key) {
    send(std::string(1, key) + "\n"); assert(moving && armed);
    assert(pwm[EN_A] == (key == '1' ? 80 : key == '2' ? 80 : 0));
    assert(pwm[EN_B] == (key == '3' ? 80 : key == '4' ? 80 : 0));
    assert(digital[IN_1] == (key == '1'));
    assert(digital[IN_2] == (key == '2'));
    assert(digital[IN_3] == (key == '4'));
    assert(digital[IN_4] == (key == '3'));
    now += (key == '1' || key == '3') ? 39 : 24; loop(); assert(moving);
    now += 1; loop(); off(); assert(armed);
  }


  send("disarm\nDIR 1 1 80 200\n"); off();
  send("arm\n");
  for(int a=0;a<2;++a) for(int b=0;b<2;++b) {
    send("DIR " + std::to_string(a) + " " + std::to_string(b) + " 80 200\n");
    assert(moving && pwm[EN_A] == 80 && pwm[EN_B] == 80);
    assert(digital[IN_1] == a && digital[IN_2] == 1-a);
    assert(digital[IN_3] == b && digital[IN_4] == 1-b);
    now += 199; loop(); assert(moving);
    now += 1; loop(); off();
  }
  for(int a=0;a<3;++a) for(int b=0;b<3;++b) {
    send("DIR " + std::to_string(a) + " " + std::to_string(b) + " 40 200\n");
    assert(pwm[EN_A] == (a==2 ? 0 : 40)); assert(pwm[EN_B] == (b==2 ? 0 : 40));
    assert(digital[IN_1] == (a==1) && digital[IN_2] == (a==0));
    assert(digital[IN_3] == (b==1) && digital[IN_4] == (b==0));
    now += 200; loop(); off();
  }
  send("DIR 1 1 80 250\n"); assert(moving && pwm[EN_A] == 80 && pwm[EN_B] == 80);
  assert(digital[IN_1] == HIGH && digital[IN_3] == HIGH);
  now += 249; loop(); assert(moving);
  now += 1; loop(); off();
  for(int bit=0;bit<2;++bit) {
    send("DIR " + std::to_string(bit) + " " + std::to_string(bit) + " 80 250\n");
    now += 124; loop(); assert(pwm[EN_A] == 80 && pwm[EN_B] == 80);
    now += 1; loop(); assert(moving);
    assert(pwm[EN_A] == (bit==1 ? 80 : 0));
    assert(pwm[EN_B] == (bit==0 ? 80 : 0));
    now += 124; loop(); assert(moving);
    now += 1; loop(); off();
  }
  send("DIR 2 1 80 250\n"); now += 200; loop();
  assert(pwm[EN_B] == 80); now += 50; loop(); off(); // standalone payout unchanged
  send("DIR 1 0 80 500\n");
  assert(moving && pwm[EN_A] == 80 && pwm[EN_B] == 80);
  assert(digital[IN_1] == HIGH && digital[IN_4] == HIGH);
  now += 499; loop(); assert(moving && pwm[EN_A] == 80 && pwm[EN_B] == 80);
  now += 1; loop(); off();
  send("DIR 1 1 80 500 125\n");
  assert(moving && pwm[EN_A] == 80 && pwm[EN_B] == 80);
  assert(digital[IN_1] == HIGH && digital[IN_3] == HIGH);
  now += 124; loop(); assert(pwm[EN_A] == 80 && pwm[EN_B] == 80);
  now += 1; loop(); assert(pwm[EN_A] == 80 && pwm[EN_B] == 0);
  now += 374; loop(); assert(moving && pwm[EN_A] == 80);
  now += 1; loop(); off();
  send("DIR 1 1 80 500 501\n"); off();
  send("DIR 1 1 80 500 0\n"); off();
  send("DIR 1 0 80 501\n"); off();
  send("DIR 3 0 80 200\n"); off();
  send("DIR 1 0 91 400\n"); off();
  send("DIR 1 0 80 4001\n"); off();
  send("DIR 1 0 80 200\n!\n"); off(); assert(!armed);
  send("stop\narm\nleft\n"); assert(moving && pwm[EN_A] == 80 && pwm[EN_B] == 80);
  assert(digital[IN_1] == HIGH && digital[IN_3] == HIGH); // calibrated A wind/B payout
  now += 249; loop(); assert(moving);
  now += 1; loop(); off();
  send("set left 80 -80 251\n"); assert(preset("LEFT")->ms == 250); off();
  send("set left 60 -45 25\nset right -45 60 25\nset return_left -45 60 25\nset return_right 60 -45 25\n");
  send("ramp 40 80 100\n"); assert(rampStartPwm == 40 && sequencePwm == 80 && rampRiseMs == 100);
  assert(!autoEnabled); off();
  startJog(80, -80, 500, true, 500, 50);
  assert(pwm[EN_A] == 40 && pwm[EN_B] == 40);
  now += 25; loop(); assert(pwm[EN_A] == 50 && pwm[EN_B] == 60);
  now += 24; loop(); assert(pwm[EN_A] == 59 && pwm[EN_B] == 80);
  now += 1; loop(); assert(pwm[EN_A] == 60 && pwm[EN_B] == 0);
  now += 50; loop(); assert(pwm[EN_A] == 80 && pwm[EN_B] == 0);
  now += 399; loop(); assert(moving && pwm[EN_A] == 80);
  now += 1; loop(); off();
  startJog(-80, 0, 100, true); now += 10; loop();
  assert(digital[IN_2] == HIGH && pwm[EN_B] == 0);
  send("!\n"); off(); assert(!armed);
  send("arm\nramp 80 40 100\n"); off(); assert(rampStartPwm == 40);
  send("ramp 1 91 100\nramp 0 80 100\nramp 40 80 501\nramp 40 80 100 extra\n");
  assert(rampStartPwm == 40 && sequencePwm == 80 && rampRiseMs == 100);
  send("ramp 40 80 0\n"); startJog(80, 0, 1, true);
  assert(pwm[EN_A] == 80); ++now; loop(); off();
  send("ramp 80 80 100\n");
  send("stop\ndisarm\nauto\n"); assert(!autoEnabled);
  send("ramp 50 80 100\narm\nsteps 1 1\nauto\n"); assert(autoEnabled && completedCount == 0);
  for (int cycle=0; cycle<3; ++cycle) {
    if (cycle) {
      for(int i=0;i<5;++i) acceptRange(10);
      assert(!stage); // cooldown blocks immediate retrigger
      now = sequenceFinishedAt + 499;
      for(int i=0;i<3;++i) acceptRange(10);
      assert(!stage && !readyForVisit);
      ++now;
      for(int i=0;i<3;++i) acceptRange(-1);
      assert(!stage && readyForVisit && nearCount == 0); // invalid echo never triggers
    }
    for(int i=0;i<3;++i) acceptRange(20);
    assert(!stage); // strictly less than 20
    acceptRange(19); acceptRange(19); assert(!stage);
    acceptRange(19); assert(stage && completedCount == (unsigned long)cycle);
    const bool initiallyRoaring = true;
    assert(roaring == initiallyRoaring);
    if (roaring) assert(roarLevel == cycle + 1);
    const unsigned long triggeredAt = now;
    int pulses = 0, roarStarts = initiallyRoaring ? 1 : 0;
    bool previousMoving = false, previousRoaring = roaring;
    int previousA = 0, previousB = 0;
    unsigned long finish = now + 10000;
    while (stage && now < finish) {
      acceptRange(26); acceptRange(10); // inputs during sequence cannot advance counter
      assert(completedCount == (unsigned long)cycle);
      ++now; loop();
      assert(!(roaring && moving));
      if (roaring) { assert(pwm[EN_A] == 0 && pwm[EN_B] == 0); }
      if (moving && !previousMoving) {
        const unsigned long roarMs[] = {1400, 2100, 2800};
        assert(now - triggeredAt >= roarMs[cycle]);
        int wantACommand, wantBCommand;
        unsigned long wantA, wantB;
        if (cycle < 2) {
          const bool left = cycle == 0 ? pulses == 0 : pulses == 1;
          wantACommand = left ? 80 : -80;
          wantBCommand = -wantACommand;
          wantA = left ? 500 : 125;
          wantB = left ? 125 : 500;
        } else {
          assert(pulses < 9);
          const int commandsA[] = {80, -80, 0};
          const int commandsB[] = {0, 80, -80};
          const unsigned long timesA[] = {250, 50, 50};
          const unsigned long timesB[] = {250, 250, 50};
          wantACommand = commandsA[pulses % 3]; wantBCommand = commandsB[pulses % 3];
          wantA = timesA[pulses % 3]; wantB = timesB[pulses % 3];
        }
        assert(targetA == wantACommand && targetB == -wantBCommand);
        assert(digital[IN_1] == (wantACommand > 0) && digital[IN_2] == (wantACommand < 0));
        assert(digital[IN_4] == (wantBCommand > 0) && digital[IN_3] == (wantBCommand < 0));
        assert(jogDuration == (wantA > wantB ? wantA : wantB));
        assert(durationA == wantA && durationB == wantB);
        assert(rampEnabled);
        assert(pwm[EN_A] == (wantACommand ? 50 : 0));
        assert(pwm[EN_B] == (wantBCommand ? 50 : 0));
        previousA = previousB = 0;
        ++pulses;
      }
      if (moving) {
        const unsigned long elapsed = now - startedAt;
        if (targetA && elapsed < durationA) {
          assert(pwm[EN_A] >= 50 && pwm[EN_A] <= 80 && pwm[EN_A] >= previousA);
        } else assert(pwm[EN_A] == 0);
        if (targetB && elapsed < durationB) {
          assert(pwm[EN_B] >= 50 && pwm[EN_B] <= 80 && pwm[EN_B] >= previousB);
        } else assert(pwm[EN_B] == 0);
        previousA = pwm[EN_A]; previousB = pwm[EN_B];
      }
      if(roaring && !previousRoaring) { ++roarStarts; assert(roarLevel == cycle + 1); }
      previousMoving = moving; previousRoaring = roaring;
    }
    assert(!stage && !moving && completedCount == (unsigned long)cycle+1);
    assert(visit == (cycle+1)%3);
    assert(pulses == (cycle == 2 ? 9 : 2));
    assert(roarStarts == 1);
  }
  // Aborted sequences must not count as completed or restart later.
  now = sequenceFinishedAt + 500;
  for(int i=0;i<3;++i) acceptRange(26);
  for(int i=0;i<3;++i) acceptRange(10);
  assert(roaring); send("stop\n"); assert(!stage && !roaring && !autoEnabled);
  now += 2000; loop(); off(); assert(completedCount == 3);
  send("auto\n"); assert(completedCount == 0);
  for(int i=0;i<3;++i) acceptRange(10);
  now += 1400; loop(); assert(moving);
  now += 125; loop(); assert(moving && pwm[EN_A] == 80 && pwm[EN_B] == 0);
  now += 374; loop(); assert(moving && pwm[EN_A] == 80);
  now += 1; loop(); assert(!moving && stage);
  send("!\n"); now += 5000; loop(); off();
  assert(!autoEnabled && !armed && completedCount == 0);
  send("arm\nauto\n"); echoUs = 0; now += 100; loop(); assert(!stage);

}
''')
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-I', str(work), '-I', str(root / 'src'),
                    str(work / 'check.cpp'), '-o', str(work / 'check')], check=True)
    subprocess.run([str(work / 'check')], check=True)
print('PASS: presets, direction, deadlines, disarmed/busy rejection, stop and invalid input')
