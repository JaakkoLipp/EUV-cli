"""Textual application and event handlers."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Input, Static

from eco_sim.content.scenarios import default_scenario
from eco_sim.sim.engine import tick
from eco_sim.sim.state import GameState, add_event
from eco_sim.tui.commands import execute_command
from eco_sim.tui.render import footer_text, header_text, log_text, market_rows, regions_text, trade_text


class EcoSimApp(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "tick_one", "Tick 1"),
        ("T", "tick_ten", "Tick 10"),
        ("tab", "cycle_market", "Cycle market"),
    ]

    selected_country_id = reactive("")
    selected_market_id = reactive("")
    last_error = reactive("")
    status_message = reactive("")
    revision = reactive(0)

    def __init__(self, state: GameState | None = None) -> None:
        super().__init__()
        self.state: GameState = state or default_scenario()

    def compose(self) -> ComposeResult:
        with Container(id="root"):
            yield Static(id="header")
            with Horizontal(id="main"):
                with Vertical(id="left"):
                    yield DataTable(id="market_table")
                    yield Static(id="regions_panel")
                with Vertical(id="right"):
                    yield Static(id="trade_panel")
                    yield Static(id="log_panel")
            yield Static(id="footer")
            yield Input(placeholder="Enter command...", id="command_input")

    def on_mount(self) -> None:
        table = self.query_one("#market_table", DataTable)
        table.add_columns(
            "Good",
            "Price",
            "Stock",
            "Produced",
            "Demanded",
            "Bought",
            "Trade Net",
            "Satisfaction",
        )
        self._ensure_selection()
        self._refresh_all()

    def action_tick_one(self) -> None:
        tick(self.state, 1)
        add_event(self.state, "tick", "Advanced 1 tick")
        self._bump_revision("Advanced 1 tick")

    def action_tick_ten(self) -> None:
        tick(self.state, 10)
        add_event(self.state, "tick", "Advanced 10 ticks")
        self._bump_revision("Advanced 10 ticks")

    def action_cycle_market(self) -> None:
        market_ids = sorted(self.state.markets.keys())
        if not market_ids:
            return
        if self.selected_market_id not in market_ids:
            self.selected_market_id = market_ids[0]
            self.selected_country_id = self.state.markets[self.selected_market_id].country_id
            return
        index = market_ids.index(self.selected_market_id)
        next_id = market_ids[(index + 1) % len(market_ids)]
        self.selected_market_id = next_id
        self.selected_country_id = self.state.markets[next_id].country_id

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command_text = event.value.strip()
        event.input.value = ""
        if not command_text:
            return
        result = execute_command(
            self.state,
            command_text,
            self.selected_country_id,
            self.selected_market_id,
        )
        if result.quit_app:
            self.exit()
            return
        if result.selected_country_id:
            self.selected_country_id = result.selected_country_id
        if result.selected_market_id:
            self.selected_market_id = result.selected_market_id
        self.last_error = result.message if result.error else ""
        self._bump_revision(result.message if not result.error else "")

    def watch_revision(self, _old: int, _new: int) -> None:
        self._refresh_all()

    def watch_selected_market_id(self, _old: str, _new: str) -> None:
        self._refresh_all()

    def watch_selected_country_id(self, _old: str, _new: str) -> None:
        self._refresh_all()

    def _refresh_all(self) -> None:
        header = self.query_one("#header", Static)
        footer = self.query_one("#footer", Static)
        regions_panel = self.query_one("#regions_panel", Static)
        trade_panel = self.query_one("#trade_panel", Static)
        log_panel = self.query_one("#log_panel", Static)
        table = self.query_one("#market_table", DataTable)

        if self.selected_country_id:
            header.update(header_text(self.state, self.selected_country_id))
            regions_panel.update(regions_text(self.state, self.selected_country_id))
        if self.selected_market_id:
            table.clear(columns=False)
            table.add_rows(market_rows(self.state, self.selected_market_id))
        trade_panel.update(trade_text(self.state))
        log_panel.update(log_text(self.state))
        footer.update(footer_text(self.status_message, self.last_error))

    def _ensure_selection(self) -> None:
        if not self.state.markets:
            return
        first_market_id = sorted(self.state.markets.keys())[0]
        self.selected_market_id = first_market_id
        self.selected_country_id = self.state.markets[first_market_id].country_id

    def _bump_revision(self, message: str) -> None:
        if message:
            self.status_message = message
        self.revision += 1
