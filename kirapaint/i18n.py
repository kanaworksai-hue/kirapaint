# SPDX-FileCopyrightText: 2026 東京AI映像合同会社 (Tokyo AI Visuals LLC)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Japanese UI.

Two ways in:
1. Automatic: Blender set to Japanese (Preferences > Interface > Translation, Language 日本語) shows KiraPaint in
   Japanese, tooltips included, through Blender's own translation system.
2. By hand: the KiraPaint panel's header menu (or the add-on preferences) picks 日本語 or English for the panel,
   whatever language Blender itself uses.

Terms follow Blender's official Japanese UI (taken from Blender 5.2's ja blender.mo): 粗さ, 薄膜, 光沢, ブルーム,
ブラシサイズ, 輪郭線の幅, コンポジター, ワールド, キーフレーム, ターンテーブル, プリンシプルBSDF, レンダー.
ストローク is avoided for the facet slider: in Blender it means a brush / Grease Pencil stroke.
"""

import re

import bpy

from . import backgrounds

# English msgid -> Japanese
JA = {
    # panels and sections
    "Style": "スタイル",
    "Background": "背景",
    "Look": "ルック",
    "Surface": "サーフェス",
    "Paint & Shine": "ペイント＆きらめき",
    "Scene & Animation": "シーンとアニメーション",
    "About": "情報",
    "Preset": "プリセット",
    "UI Language": "表示言語",
    "More KanaWorks add-ons": "KanaWorks のほかのアドオン",
    "Best in EEVEE (Make It Kira switches)": "EEVEE 推奨（「キラキラにする」で切り替わります）",
    # settings
    "2.5D": "2.5D",
    "Stroke": "砕け具合",
    "Facet Density": "面の細かさ",
    "Gloss": "光沢",
    "Iridescence": "虹色（薄膜）",
    "Brush Size": "ブラシサイズ",
    "Sparkle": "星の光",
    "Bloom": "ブルーム",
    "Outline Width": "輪郭線の幅",
    "Chalk Doodles": "チョークの落書き",
    "Steam": "湯気",
    "Reveal Frames": "切り替えのフレーム数",
    "Turn": "回転角度",
    "Turn Frames": "回転のフレーム数",
    "Keep Mine": "自分のワールドを使う",
    "Automatic (follow Blender)": "自動（Blender に合わせる）",
    "Auto": "自動",
    "Show in English": "英語で表示",
    "Selected or All": "選択中（なければすべて）",
    # tooltips
    "0 = plain render, 1 = full KiraPaint. Animate it for a reveal":
        "0 で通常のレンダー、1 で KiraPaint。キーフレームを打つと、写実から絵画風に変わる演出になります",
    "How strongly the surface breaks into painted facets": "表面を小さな面に砕く強さ（ノーマルのゆがみ）",
    "More, smaller facets (1 = about 6 across the object)": "大きいほど面が細かくなります（1 でオブジェクトの幅に約6個）",
    "How glassy the facets get": "面のツヤの強さ（粗さを下げます）",
    "Pink / cyan thin-film sheen": "薄膜によるピンク・水色の虹色",
    "Paint brush size in pixels at 1080p": "筆の大きさ（1080p でのピクセル数。解像度に合わせて自動で換算）",
    "Star glints on the brightest facets": "いちばん明るい面に入る星の光",
    "Soft glow": "ふんわりした光のにじみ",
    "0 = no outline": "0 で輪郭線なし",
    "Stars, hearts and twinkles around the object": "オブジェクトのまわりに星・ハート・キラキラを描きます",
    "Three steam lines above the object (food!)": "オブジェクトの上に湯気を3本描きます（食べ物向け）",
    "Keep your own world (reflections get less colorful)": "自分のワールドを残します（映り込みの色は控えめになります）",
    "Language of the KiraPaint panel. Automatic follows Blender's own language":
        "KiraPaint パネルの表示言語。自動では Blender の言語設定に合わせます",
    # presets
    "Kira (crushed diamond)": "キラ（砕いたダイヤ）",
    "Glossy painted facets with colored glints and star sparkles": "ツヤのある面に色つきの光と星のきらめき",
    "Soft Paint": "ソフトペイント",
    "Gentle oil-paint strokes, few sparkles": "やわらかい油絵のタッチ。きらめきは控えめ",
    "Bold Ink": "くっきりインク",
    "Thick outline, crisp strokes, a little shine": "太い輪郭線とくっきりしたタッチ。ツヤは少しだけ",
    "Dreamy": "ゆめかわ",
    "Strong rainbow sheen, lots of glow and sparkles": "強い虹色、たっぷりのブルームときらめき",
}

# operators: label, then tooltip
JA_OPS = {
    "Make It Kira": "キラキラにする",
    "Paint the selected objects (all meshes if nothing is selected) and set up the scene":
        "選択中のオブジェクト（選択がなければすべてのメッシュ）を絵画風にして、シーンを設定します",
    "Make Kira (one call)": "キラキラにする（一括）",
    "One call for scripts and AI agents (all options in one place)": "スクリプトや AI エージェント用。すべての設定を一度に指定できます",
    "Remove KiraPaint": "KiraPaint を解除",
    "Put the materials back and remove KiraPaint lights, world, compositor and doodles":
        "マテリアルを元に戻し、KiraPaint のライト・ワールド・コンポジター・落書きを削除します",
    "Redraw Doodles": "落書きを描き直す",
    "Draw the chalk doodles again around the painted objects (e.g. after moving the camera)":
        "カメラを動かしたあとなどに、オブジェクトのまわりの落書きを描き直します",
    "Re-aim Lights": "ライトを再配置",
    "Place the KiraPaint lights again for the current camera": "今のカメラに合わせて KiraPaint のライトを置き直します",
    "Add Reveal": "2.5D 切り替えを追加",
    "Keyframe 2.5D from 0 to 1, starting at the current frame": "現在のフレームから「2.5D」を 0 → 1 にするキーフレームを挿入します",
    "Add Turntable": "ターンテーブルを追加",
    "Turn the painted objects in front of the fixed lights, starting at the current frame":
        "現在のフレームから、ライトはそのままでオブジェクトを回転させます",
}

for _key, _bg in backgrounds.BACKGROUNDS.items():
    JA[_bg["label"]] = _bg["ja"]

# reports (English pattern -> Japanese template)
_REPORTS = [
    (r"KiraPaint (.+) applied to (\d+) object\(s\)\.", "KiraPaint（{0}）を {1} 個のオブジェクトに適用しました。"),
    (r"Skipped materials without a Principled BSDF: (.+)\.", "プリンシプルBSDF のないマテリアルはスキップしました：{0}"),
    (r"No mesh objects to change\.", "変更できるメッシュオブジェクトがありません。"),
    (r"KiraPaint removed from (\d+) object\(s\)\.", "{0} 個のオブジェクトから KiraPaint を解除しました。"),
    (r"No objects to draw around", "落書きを描く対象のオブジェクトがありません"),
    (r"Reveal: frames (\d+)-(\d+)", "2.5D 切り替え：{0}〜{1} フレーム"),
]

PACKAGE = __package__


def preference():
    """AUTO, JA or EN. Falls back to AUTO when the add-on preferences are not available (tests, scripts)."""
    try:
        addon = bpy.context.preferences.addons.get(PACKAGE)
        return addon.preferences.ui_language if addon and addon.preferences else "AUTO"
    except AttributeError:
        return "AUTO"


def is_japanese():
    pref = preference()
    if pref != "AUTO":
        return pref == "JA"
    view = bpy.context.preferences.view
    return bpy.app.translations.locale.startswith("ja") and view.use_translate_interface


def t(msg):
    """Text for the panel in the chosen language. Pass it with translate=False so Blender leaves it alone."""
    if not is_japanese():
        return msg
    return JA.get(msg) or JA_OPS.get(msg) or msg


def report(msg):
    if not is_japanese():
        return msg
    parts = []
    for sentence in re.split(r"(?<=\.) ", msg):
        for pattern, template in _REPORTS:
            m = re.fullmatch(pattern, sentence)
            if m:
                groups = [JA.get(g, g) for g in m.groups()]
                parts.append(template.format(*groups))
                break
        else:
            parts.append(sentence)
    return " ".join(parts)


def _dictionary():
    ja = {}
    for msg, text in JA.items():
        ja[("*", msg)] = text
    for msg, text in JA_OPS.items():
        ja[("Operator", msg)] = text
        ja[("*", msg)] = text
    return {"ja_JP": ja, "ja": ja}


def register():
    try:
        bpy.app.translations.register(PACKAGE, _dictionary())
    except ValueError:
        bpy.app.translations.unregister(PACKAGE)
        bpy.app.translations.register(PACKAGE, _dictionary())


def unregister():
    try:
        bpy.app.translations.unregister(PACKAGE)
    except ValueError:
        pass
