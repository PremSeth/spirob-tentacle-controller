# SpiRob tentacle controller

Arduino Nano (ATmega328P), L298N, two TT motors, HC-SR04 and a passive piezo.

## Wiring

| Nano | Connection |
|---|---|
| D2 / D3 | L298N IN1 / IN2, motor A |
| D4 / D5 | L298N IN3 / IN4, motor B |
| D9 / D10 | ENA / ENB; remove enable jumpers |
| A4 / A5 | HC-SR04 ECHO / TRIG |
| 5V | HC-SR04 VCC |
| D6 | Piezo positive; negative to GND |
| GND | Driver, motor supply negative, sensor and piezo ground |

Motor A connects to OUT1/OUT2; B to OUT3/OUT4. USB powers the Nano;
the separate 12 V supply powers the driver's motor input. The driver's 5V
regulator connection is not established by this diagram.

[Wiring diagram](output/pdf/tentacle-circuit.pdf) · [State diagram](output/pdf/tentacle-state-diagram.pdf)

## Run

```sh
pio run -e nano_new
pio run -e nano_new -t upload --upload-port /dev/ttyUSB0
pio device monitor --port /dev/ttyUSB0 --baud 115200 --echo
```

The board starts disarmed. Enter `arm`, then `auto`. Three consecutive valid
readings below 20 cm trigger the next behavior. The sensor measures proximity,
not motion. A 500 ms cooldown follows completion; a nearby target can trigger
again without moving away. No triggers are queued during a behavior.

| Behavior | Roar | Motion |
|---|---|---|
| 1 | 1.4 s | A tug 500 ms + B release 125 ms; then B tug 500 ms + A release 125 ms |
| 2 | 2.1 s | B tug 500 ms + A release 125 ms; then A tug 500 ms + B release 125 ms |
| 3 | 2.8 s | A tug 250 ms; A release 50 ms with B tug 250 ms; B release 50 ms. Repeat three times. |

Every roar finishes before the motors start. Behaviors 1 and 2 have two 250 ms
stage pauses between strokes and a 250 ms final pause. Behavior 3 has 80 ms
between strokes and after its final release. Each motor stops at its own deadline.

The completed counter increments once per finished behavior. The next behavior
cycles 1, 2, 3, 1. An interrupted behavior adds no count. `auto` resets the counter;
it does not physically home the tentacle.

## PWM ramp

`ramp START PEAK RISE_MS` configures the automatic movements and turns AUTO off.
Use `arm` and `auto` to restart. Values must satisfy `1 <= START <= PEAK <= 90`
and `0 <= RISE_MS <= 500`. Settings reset on reboot.

Each active motor ramps independently, then holds the peak until its deadline.
A rise longer than the stroke is shortened so the peak is reached on the last
millisecond before stopping. A zero rise applies the peak immediately. Inactive
motors remain off. Manual `dir`, `jog` and bench presets use constant PWM.

Defaults are **PWM 50 to 80 over 100 ms**, for both tugs and releases.
For a 50 ms release, the ramp reaches 80 at 49 ms and turns off at 50 ms.
Default values are near the top of `src/main.cpp`. Equal start and peak values
select constant PWM. PWM is drive duty cycle, not
measured motor speed; this hardware has no speed or tension feedback. Low PWM
may stall the motors. Timed releases do not guarantee a physical return to home.

## Commands

| Command | Action |
|---|---|
| `arm` | Enable manual motion; cancel AUTO |
| `auto` | Start automatic proximity detection from behavior 1 |
| `stop` | Stop motors and sound; cancel AUTO |
| `disarm` or `!` | Stop and disarm; send Enter after `!` |
| `status` | Show arm state, counter and behavior |
| `dist` / `quiet` | Show / hide distance readings; `dist` cancels AUTO |
| `roar 1` / `roar 2` / `roar 3` | Play a roar with motors stopped |
| `dir A B PWM MS_A [MS_B]` | Raw direction test; 0/1 direction, 2 off; maximum 500 ms |
| `jog A B MS` | Logical signed PWM; positive tugs, negative releases; maximum 100 ms |
| `presets` / `set NAME A B MS` | List / edit RAM-only bench presets |

Raw A=1 tugs; raw B=0 tugs. With one duration, a paired tug/release test halves
the release time. Supplying both durations uses them exactly. Bench presets do
not change the automatic sequence. `direction_test.py` provides an interactive
constant-PWM tester with visible input.

## Verify

```sh
python3 tests/check_controller.py
pio run -e nano_new -e nano_old
```

The host tests use simulated Arduino I/O to check ramps, direction, per-motor
stops, roar ordering, counters, proximity filtering and cancellation. They do not
verify physical motor speed or tendon tension.

## References

Inspired by [SpiRobs](https://arxiv.org/pdf/2303.09861) and
[Open-Spiral-Robots](https://github.com/ZhanchiWang/Open-Spiral-Robots).
This is an original simplified controller, not a port of firmware from that repository.
