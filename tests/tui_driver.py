"""Drive the curses UI in a pty and render screens with pyte.

Usage: python3 tests/tui_driver.py [script]
Feeds a scripted key sequence to the game, dumping the screen at
checkpoints, and fails loudly on any crash/traceback.
"""
import os
import pty
import select
import struct
import sys
import termios
import fcntl
import time

import pyte

COLS, ROWS = 110, 32


class Driver:
    def __init__(self, args=("-m", "euv", "--seed", "7")):
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.ByteStream(self.screen)
        env = dict(os.environ, TERM="xterm-256color",
                   LINES=str(ROWS), COLUMNS=str(COLS))
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe(sys.executable, [sys.executable, *args], env)
        self.pid, self.fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", ROWS, COLS, 0, 0))

    def pump(self, timeout=0.35):
        """Read all available output for `timeout` seconds."""
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if r:
                try:
                    data = os.read(self.fd, 65536)
                except OSError:
                    break
                if not data:
                    break
                self.stream.feed(data)

    def send(self, keys: str, settle=0.25):
        for ch in keys:
            os.write(self.fd, ch.encode())
            self.pump(0.06)
        self.pump(settle)

    def send_key(self, code: bytes, settle=0.25):
        os.write(self.fd, code)
        self.pump(settle)

    def text(self) -> str:
        return "\n".join(self.screen.display)

    def dump(self, label=""):
        print(f"=== screen: {label} " + "=" * max(0, 60 - len(label)))
        for line in self.screen.display:
            print(line.rstrip())
        print("=" * 75)

    def alive(self) -> bool:
        if getattr(self, "_dead", False):
            return False
        try:
            pid, _ = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            self._dead = True
            return False
        if pid != 0:
            self._dead = True
        return pid == 0

    def quit(self):
        try:
            os.kill(self.pid, 9)
            os.waitpid(self.pid, 0)
        except OSError:
            pass


def expect(d: Driver, needle: str, label: str):
    if needle not in d.text():
        d.dump(f"FAILED expecting '{needle}' ({label})")
        d.quit()
        sys.exit(f"FAIL: '{needle}' not on screen at: {label}")
    print(f"ok: {label}")


KEY_DOWN = b"\x1b[B"
KEY_UP = b"\x1b[A"
KEY_RIGHT = b"\x1b[C"
KEY_LEFT = b"\x1b[D"
ENTER = b"\r"
ESC = b"\x1b"


def main():
    d = Driver()
    d.pump(1.2)
    expect(d, "New Game", "title screen")
    d.send_key(ENTER, 0.6)                 # new game
    expect(d, "Choose Your Nation", "nation select")
    d.send_key(ENTER, 0.8)                 # pick top nation (biggest)
    expect(d, "Eryndor", "main screen map")
    expect(d, "Gold", "top bar")
    d.dump("main view (political)")
    d.send("2", 0.3)
    expect(d, "TERRAIN", "terrain mapmode")
    d.send("3", 0.3)
    expect(d, "DEVELOPMENT", "dev mapmode")
    d.send("1", 0.3)
    d.send("?", 0.4)
    expect(d, "GOAL", "help screen")
    d.send_key(ENTER, 0.3)
    d.send("o", 0.4)
    expect(d, "Ledger of Nations", "ledger")
    d.send(" ", 0.3)                       # close ledger
    d.send("\t", 0.3)                      # select army
    expect(d, "regiments", "army selected")
    d.dump("army selected")
    d.send(" ", 0.8)                       # end turn
    if not d.alive():
        d.dump("CRASHED after end turn")
        sys.exit("FAIL: process died after end turn")
    # advance a year
    d.send(">", 2.0)
    for _ in range(6):       # dismiss any queued popups
        d.send_key(ENTER, 0.3)
    if not d.alive():
        d.dump("CRASHED after year advance")
        sys.exit("FAIL: process died after year advance")
    d.dump("after ~1 year")
    # diplomacy menu from list
    d.send("D", 0.5)
    d.dump("diplomacy")
    d.send_key(ESC, 0.3)
    # save and quit
    d.send("S", 0.4)
    expect(d, "Saved", "save")
    d.send("q", 0.4)
    expect(d, "Quit", "quit menu")
    d.send_key(ENTER, 0.6)                 # save and quit -> title
    expect(d, "New Game", "back to title")
    d.send_key(KEY_DOWN, 0.2)
    d.send_key(ENTER, 0.8)                 # load game
    expect(d, "Eryndor", "loaded game map")
    print("ALL TUI CHECKS PASSED")
    d.quit()


if __name__ == "__main__":
    main()
