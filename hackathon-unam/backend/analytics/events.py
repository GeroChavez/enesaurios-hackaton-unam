"""Nombres de eventos del tracking (sin dependencias; los usa también la herramienta de auditoría)."""
THROW_EVENTS = {"pass_forward", "autoevent_passforward", "pass_shovel"}
SNAP_EVENTS = {"ball_snap", "autoevent_ballsnap"}
ARRIVAL_EVENTS = {"pass_arrived", "pass_outcome_caught", "pass_outcome_incomplete", "dropped_pass",
                  "pass_outcome_interception", "pass_outcome_touchdown"}
