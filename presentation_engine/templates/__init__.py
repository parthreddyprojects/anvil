"""
Card templates for the Presentation Engine.
Each template is a function: data dict -> HTML string.
"""

from .hero import render_hero
from .timeline import render_timeline
from .kpi_card import render_kpi_card
from .verdict_panel import render_verdict_panel
from .scenario_card import render_scenario_card
from .checklist import render_checklist
from .chart_card import render_chart_card
from .map_card import render_map_card
from .quote_pair import render_quote_pair
from .act_break import render_act_break
from .closing import render_closing
from .domino_row import render_domino_row

TEMPLATE_REGISTRY = {
    "hero": render_hero,
    "timeline": render_timeline,
    "kpi_card": render_kpi_card,
    "verdict_panel": render_verdict_panel,
    "scenario_card": render_scenario_card,
    "checklist": render_checklist,
    "chart_card": render_chart_card,
    "map_card": render_map_card,
    "quote_pair": render_quote_pair,
    "act_break": render_act_break,
    "closing": render_closing,
    "domino_row": render_domino_row,
}


def get_template(card_type: str):
    """Return the render function for a card_type, or raise KeyError."""
    if card_type not in TEMPLATE_REGISTRY:
        raise KeyError(
            f"Unknown card_type '{card_type}'. "
            f"Available: {', '.join(TEMPLATE_REGISTRY.keys())}"
        )
    return TEMPLATE_REGISTRY[card_type]
