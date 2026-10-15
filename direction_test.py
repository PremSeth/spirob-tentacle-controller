#!/usr/bin/env python3
"""Interactive raw direction test. Run with PlatformIO's Python (has pyserial)."""
import argparse
import time
import serial


def receive_until(link, marker, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = link.readline().decode(errors="replace").strip()
        if not line:
            continue
        print("  " + line)
        if marker in line:
            return
        if line.startswith(("ERR", "BUSY", "DISARMED:")):
            raise RuntimeError(line)
    raise RuntimeError("No expected response: " + marker)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--pwm", type=int, default=80)
    parser.add_argument("--ms", type=int, default=250)
    args = parser.parse_args()
    if not (1 <= args.pwm <= 90 and 1 <= args.ms <= 250):
        parser.error("PWM must be 1..90 and ms must be 1..250 for this gentle tester")
    print("Close other serial monitors first. Keep line loose for direction testing.")
    print("0/1 choose direction. 2 (or x) means OFF. First digit=A, second=B.")
    with serial.Serial(args.port, 115200, timeout=0.1, exclusive=True) as link:
        try:
            time.sleep(2)
            link.write(b"\ndisarm\nquiet\n")
            receive_until(link, "STOPPED/DISARMED")
            link.write(b"arm\n")
            receive_until(link, "ARMED")
            print("Constant PWM; paired tug/payout runs the payout motor for HALF the duration.")
            print(f"Tug/standalone: PWM {args.pwm}, {args.ms} ms per test, then stop.")
            print("Both: 00/01/10/11. A only: 02/12. B only: 20/21. 22=stop. q quits.")
            while True:
                choice = input("A B direction > ").replace(" ", "").strip().lower()
                if choice in ("q", "quit", "exit"):
                    break
                choice = choice.replace("x", "2")
                if len(choice) != 2 or any(c not in "012" for c in choice):
                    print("Use two digits: 0/1=direction, 2=off. Example: 12 runs A only.")
                    continue
                a, b = map(int, choice)
                if choice == "22":
                    link.write(b"stop\n")
                    receive_until(link, "STOPPED;")
                    continue
                for name, bit, pin1, pin2 in (("A", a, 2, 3), ("B", b, 4, 5)):
                    print(f"{name}: OFF" if bit == 2 else f"{name}: D{pin1}={bit}, D{pin2}={1-bit}")
                link.write(f"DIR {a} {b} {args.pwm} {args.ms}\n".encode())
                receive_until(link, "DONE", timeout=args.ms / 1000 + 2)
        finally:
            link.write(b"!\ndisarm\n")
            link.flush()
            time.sleep(0.15)
            print("Stopped/disarm command sent; automation remains off.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        pass
    except (serial.SerialException, RuntimeError) as exc:
        raise SystemExit(str(exc))
