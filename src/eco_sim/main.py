"""Textual application entry point."""

from eco_sim.content.scenarios import default_scenario
from eco_sim.tui.app import EcoSimApp


def main() -> None:
    state = default_scenario()
    app = EcoSimApp(state)
    app.run()


if __name__ == "__main__":
    main()
