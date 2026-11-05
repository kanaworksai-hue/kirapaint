# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""KiraPaint: painterly 2.5D look with crushed-diamond sparkle, for EEVEE, in one click."""

from . import ops, ui


def register():
    ops.register()
    ui.register()


def unregister():
    ui.unregister()
    ops.unregister()
