"""Plato risk-based regression agent — shared core + two flows.

flow1_defect_history : score risk from past defects, test what broke.
flow2_change_driven  : score components from the release delta, test what changed.
"""
