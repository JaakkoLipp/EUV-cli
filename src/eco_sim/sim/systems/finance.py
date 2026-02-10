"""Finance system for income, taxes, and upkeep."""

from __future__ import annotations

from eco_sim.sim.state import GameState, add_event


def apply_finance(state: GameState) -> None:
    for country_id in sorted(state.countries.keys()):
        country = state.countries[country_id]
        for pop_id in country.pop_ids:
            pop = state.pops[pop_id]
            income = pop.income_per_capita * pop.size
            tax = income * country.tax_rate
            pop.cash += income - tax
            country.treasury += tax

        upkeep_total = 0.0
        for region_id in country.region_ids:
            region = state.regions[region_id]
            for building_id in region.building_ids:
                building = state.buildings[building_id]
                building_type = state.building_types[building.type_id]
                upkeep_total += building_type.upkeep * building.level

        if upkeep_total > 0.0:
            if country.treasury >= upkeep_total:
                country.treasury -= upkeep_total
            else:
                country.treasury = 0.0
                add_event(
                    state,
                    "finance",
                    f"{country.name} could not cover building upkeep",
                    {"country_id": country.id},
                )
