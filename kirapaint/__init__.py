# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
# Additional term (GPLv3 section 7(b)), see NOTICE.md: if you convey this add-on or a work based on it,
# keep this attribution in its description and documentation:
#   KiraPaint by KanaWorks_AI (@KanaWorks_AI) — https://github.com/kanaworksai-hue/kirapaint
"""KiraPaint: painterly 2.5D look with crushed-diamond sparkle, for EEVEE, in one click."""

from . import i18n, ops, ui


def register():
    i18n.register()
    ops.register()
    ui.register()


def unregister():
    ui.unregister()
    ops.unregister()
    i18n.unregister()
