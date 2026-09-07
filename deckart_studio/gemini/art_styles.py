WESTERN_ANIME = "Western Anime"
PHOTOREALISTIC = "Photorealistic cinematic"
PAINTERLY_OIL = "Painterly oil"
DARK_FANTASY = "Dark fantasy illustration"
COMIC_INK = "Comic book ink"
WATERCOLOR = "Watercolor"
ANIME = "Anime"
RETRO_PULP = "Retro pulp magazine"
STAINED_GLASS = "Stained glass"

DEFAULT_ART_STYLES = [
    WESTERN_ANIME,
    PHOTOREALISTIC,
    PAINTERLY_OIL,
    DARK_FANTASY,
    COMIC_INK,
    WATERCOLOR,
    ANIME,
    RETRO_PULP,
    STAINED_GLASS,
]


def art_only_layout() -> str:
    return (
        "IMPORTANT: Render as a clean, full-bleed vertical illustration. "
        "Output pure character and background art only. Do not include card frames, text, labels, "
        "UI elements, boxes, or borders. NEVER show any card frames or text."
    )


def composition_rules() -> str:
    return (
        "Portrait orientation matching a trading card (about 2:3). "
        "Leave some sky or empty space at the top and in the lower third so Clear Art text can sit on the picture."
    )


def subject_rules() -> str:
    return (
        "If the card names a person, paint that person or creature. "
        "If it is a theme, recast it as a character or scene that fits."
    )


def safety_rules() -> str:
    return "No nudity and no explicit sexual content."


def general_instructions() -> str:
    return " ".join([art_only_layout(), composition_rules(), subject_rules(), safety_rules()])


STYLE_INSTRUCTIONS = {
    WESTERN_ANIME: (
        "Execute as a high-quality, professional comic book illustration in a bold Western Anime "
        "(cel-shaded) style, completely free of photorealistic textures. All edges must feature crisp, "
        "defined line art. The character design follows a classic pin-up and ecchi aesthetic, featuring "
        "revealing, highly alluring attire (such as low-rise cutoffs, micro-shorts, unbuttoned layers, "
        "or cropped dynamic outfits) that maximizes visible midriff and legs while remaining non-explicit. "
        "For female characters, skip undershirts and keep significant cleavage visible, but never fully "
        "exposed. For male characters, show a strong structured chest. Use smooth, clean cel-shading with "
        "distinct color blocks and sharp contrast. Lighting must be dramatic, warm, and directional, "
        "emphasizing muscle tone and character contours like a dynamic manga cover. Mood is cinematic and "
        "lewd but not NSFW: revealing futuristic or period clothing, cleavage or midriff or tight coats."
    ),
    PHOTOREALISTIC: (
        "Execute as a high-quality photorealistic cinematic still, like a prestige-film frame or concept "
        "photograph, not a drawing and not cel-shading. Materials must read as real: skin, metal, cloth, "
        "weather, and shallow depth of field. Lighting is cinematic and motivated — strong key, controlled "
        "rim, practical glow — with atmospheric haze where it helps. Costume and setting match the card: "
        "period, futuristic, or contemporary, tailored and camera-ready, alluring through cut and fabric "
        "rather than cartoon pin-up. Keep the figure readable as a vertical 2:3 portrait."
    ),
    PAINTERLY_OIL: (
        "Execute as a high-quality traditional oil painting, with visible brushwork, blended flesh, and "
        "impasto highlights. Color is rich and glazed, in the manner of a salon portrait or painted fantasy "
        "cover, never photoreal photography and never hard cel edges. Lighting is warm and painterly — "
        "Rembrandt or golden-hour — modeling form with soft transitions. Costume is heavy fabric, armor, or "
        "period dress with tactile folds and jewelry catching thick paint. Keep an easel-like vertical "
        "portrait with breathing room for later text."
    ),
    DARK_FANTASY: (
        "Execute as a high-quality dark-fantasy illustration for a deluxe book or card cover: ornate, "
        "ominous, and fully painted. Forms are solid and dramatic, with gothic architecture, cursed metal, "
        "and shadowed landscapes — not photoreal pores and not Western-anime cel-shade. Lighting is "
        "chiaroscuro: moonlight, embers, or a single supernatural source carving silhouettes and metal "
        "edges. Costume leans to ritual armor, tattered cloaks, and regal menace. Keep the figure "
        "monumental, with empty gloom reserved at the top and lower third."
    ),
    COMIC_INK: (
        "Execute as a high-quality American comic-book cover: bold inked contours, confident anatomy, and "
        "graphic color holds. Line weight varies; interiors stay readable at card size. Do not use "
        "photoreal texture or muddy painterly blend. Lighting is punchy and staged, with hard shadows and "
        "saturated pop like a modern variant cover. Costume is heroic and dynamic — capes, armor, street "
        "gear — designed to silhouette. Keep a vertical action portrait with an open sky or color field "
        "where text can sit."
    ),
    WATERCOLOR: (
        "Execute as a high-quality watercolor illustration on paper: transparent washes, granulation, and "
        "soft blooms, not digital cel-shading and not photography. Edges fade into the sheet; reserved "
        "whites catch the light. Lighting is gentle and natural, as if painted beside a window, with cool "
        "shadows and warm accents. Costume and setting are suggested with fluid pigment — flowing cloth, "
        "foliage, mist. Keep a vertical portrait with pale open wash at the top and in the lower third."
    ),
    ANIME: (
        "Execute as a high-quality Japanese anime key visual (sakuga / end-card quality), not Western comics "
        "and not photorealism. Clean character line art, stylized anatomy, expressive eyes, and crisp hair "
        "highlights. Shading is anime cel or soft-cel with a planned color script and luminous accents. "
        "Costume is stylish anime fashion or fantasy kit that reads at a glance. Keep a vertical "
        "character-focused poster with open sky or a simple backdrop reserved for later text."
    ),
    RETRO_PULP: (
        "Execute as a high-quality 1930s–1950s pulp-magazine cover painting: bold figures, a limited "
        "adventure palette, and slightly exaggerated drama. Paint handling is opaque and poster-like, not "
        "photoreal and not modern cel-anime. Lighting is a theatrical spotlight against a lurid sky. "
        "Costume is period pulp — trench coats, flight jackets, jungle kit, or sci-fi chrome — alluring in "
        "the classic painted-cover way without explicit nudity. Keep a vertical cover portrait with open "
        "painted sky at the top and room in the lower third."
    ),
    STAINED_GLASS: (
        "Execute as a high-quality stained-glass window panel: thick lead came lines, jewel-tone glass, and "
        "luminous backlit color. Shapes are faceted and graphic; no photoreal skin and no painterly blend. "
        "Lighting is the glow of light through glass, with interior faces brighter and a hint of cathedral "
        "atmosphere. Figures read as iconic saints, heroes, or creatures in glass, costume reduced to strong "
        "color fields. Keep a tall vertical lancet with simpler glass or sky at the top and lower third."
    ),
}


def instruction_for_style(style: str) -> str:
    name = style.strip()
    if not name:
        return ""
    return STYLE_INSTRUCTIONS.get(name, f"Art style: {name}.")


def merge_default_art_styles(current: list[str]) -> list[str]:
    extras = [name for name in current if name not in DEFAULT_ART_STYLES]
    return list(DEFAULT_ART_STYLES) + extras
