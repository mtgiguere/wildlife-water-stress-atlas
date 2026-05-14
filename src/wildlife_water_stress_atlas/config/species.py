# src/wildlife_water_stress_atlas/config/species.py

"""
species.py

Single source of truth for all species configuration in the atlas.

WHY THIS FILE EXISTS:
---------------------
Previously, species-specific values were scattered across multiple modules:
  - analytics/scoring.py       held water_threshold_m
  - analytics/water_access.py  held accessible_water_types and water_type_weights

That meant adding a new species required editing multiple files — a maintenance
hazard and a violation of the core architectural principle:
  "Adding a new species = adding one config entry. Nothing else should change."

This registry fixes that. Every module that needs species data imports from here.

HOW TO ADD A NEW SPECIES:
--------------------------
Add one entry to SPECIES_CONFIG below. No other file needs to change.
All values are validated at import time by the functions at the bottom of this file.

FIELD REFERENCE:
----------------
water_threshold_m       : int | float
    Maximum distance in meters at which the species is considered water-stressed.
    Used to normalize the stress score to a 0–1 range.
    Example: 300_000 means "if an elephant is 300km from water, stress = 1.0"

accessible_water_types  : set[str]
    The water source types this species can actually use.
    Must match the 'type' column values produced by the water ingestion layer.
    Example: {"river", "lake", "pan", "wetland"}

water_type_weights      : dict[str, float]
    Relative reliability/preference weight for each accessible water type.
    Keys MUST exactly match accessible_water_types.
    Values are floats in the range (0.0, 1.0].
    1.0 = fully reliable source, lower = seasonal or less preferred.
    Example: {"river": 1.0, "pan": 0.8} means pans are slightly less reliable.

daily_range_m           : int | float
    Typical maximum daily movement range in meters.
    Used for grid cell sizing and future movement modeling.
    Example: 50_000 (50km is a reasonable upper bound for elephants)

water_dependency        : str — one of "low", "moderate", "high"
    Qualitative descriptor of how tightly this species depends on
    surface water availability. Used for weighting in composite stress
    scores when multiple pressure types are combined in future phases.
"""

SPECIES_CONFIG: dict[str, dict] = {
    "Loxodonta africana": {
        "common_name": "African Elephant",
        # ---------------------------------------------------------------
        # African Elephant
        # ---------------------------------------------------------------
        # Elephants are among the most water-dependent large mammals.
        # Adults drink 150–300 litres per day and rarely stray more than
        # ~50km from water in dry conditions, though tracked individuals
        # have been recorded up to ~180km from permanent water during
        # exceptional dry-season movements.
        #
        # The 300km threshold is a conservative upper bound that ensures
        # those extreme cases score at or near 1.0 without capping too
        # aggressively in normal conditions. This is a placeholder — see
        # Section 4 of the project bible for the full gap acknowledgment.
        "water_threshold_m": 300_000,
        # Pans, wetlands, floodplains, and surface_water added here —
        # this is the config change that fixes the phantom thirst bug.
        # These types are now visible to filter_accessible_water() and
        # will be included in the distance calculation once their source
        # classes are loaded in the pipeline.
        "accessible_water_types": {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "saline_lake", "permanent_water"},
        # Permanent sources weighted at 1.0 — fully reliable year-round.
        # Seasonal sources weighted lower — less reliable in dry season.
        # These are heuristic placeholders, honest about being estimates.
        # Ecological validation from Save the Elephants / IUCN is a future step.
        "water_type_weights": {
            "river": 1.0,
            "lake": 1.0,
            "pan": 0.4,
            "wetland": 0.7,
            "floodplain": 0.7,
            "surface_water": 0.6,
            "saline_lake": 0.4,
            "permanent_water": 0.8,
        },
        # 50km is a commonly cited upper bound for elephant daily range.
        "daily_range_m": 50_000,
        # Elephants are highly water-dependent — drinking daily is
        # non-negotiable for adults.
        "water_dependency": "high",
        "icon_static_path": "app/static/Creative-Tail-Animal-elephant.svg.png",
        # Legacy CDN URL — kept for reference only.
        # icon_static_path is used for actual rendering (same-origin, no CORS).
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f418.png",
        "gbif_cache_file": "gbif_loxodonta_africana.gpkg",
        "emoji": "🐘",
    },
    "Equus quagga": {
        "common_name": "Plains Zebra",
        # ---------------------------------------------------------------
        # Plains Zebra
        # ---------------------------------------------------------------
        # Plains zebras are highly water-dependent, typically drinking
        # daily and rarely moving more than ~30km from water during the
        # dry season. They are famous for long seasonal migrations
        # (e.g. Serengeti–Masai Mara) that closely track rainfall and
        # surface water availability across the savanna.
        #
        # The 150km threshold reflects their smaller range compared to
        # elephants — zebras lack the physiological ability to endure
        # extended dry-season movements to distant water. A zebra 150km
        # from water is almost certainly in severe stress or already dead.
        # This is a heuristic placeholder pending ecological validation.
        "water_threshold_m": 150_000,
        # Zebras drink from rivers, lakes, pans and floodplains.
        # They do NOT use saline lakes — unlike elephants they cannot
        # tolerate brackish water at all. Pan reliability is slightly
        # higher than for elephants (0.5 vs 0.4) because zebras are
        # more mobile and can exploit ephemeral pans opportunistically
        # during migration.
        "accessible_water_types": {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "permanent_water"},
        # Permanent sources weighted at 1.0 — fully reliable year-round.
        # Floodplains weighted higher than for elephants (0.8 vs 0.7) —
        # zebra migrations closely track seasonal floodplain inundation.
        # All values are heuristic placeholders — ecological validation
        # from IUCN Equid Specialist Group is a future step.
        "water_type_weights": {
            "river": 1.0,
            "lake": 1.0,
            "pan": 0.5,
            "wetland": 0.7,
            "floodplain": 0.8,
            "surface_water": 0.6,
            "permanent_water": 0.9,
        },
        # 30km is a commonly cited dry-season daily range for plains zebra.
        # Migration legs can exceed this but are driven by water-seeking
        # behaviour — the daily range reflects normal foraging conditions.
        "daily_range_m": 30_000,
        # Zebras are highly water-dependent — daily drinking is essential.
        "water_dependency": "high",
        "icon_static_path": "app/static/Creative-Tail-Animal-zebra.svg.png",
        # Legacy CDN URL — kept for reference only.
        # icon_static_path is used for actual rendering (same-origin, no CORS).
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f993.png",
        "gbif_cache_file": "gbif_equus_quagga.gpkg",
        "emoji": "🦓",
    },
    "Giraffa camelopardalis": {
        "common_name": "Giraffe",
        # ---------------------------------------------------------------
        # Giraffe
        # ---------------------------------------------------------------
        # Giraffes are surprisingly vulnerable to water stress despite
        # their reputation as drought-tolerant browsers. Adults must
        # splay or bend awkwardly to drink, making them highly vulnerable
        # to predation at water points — they avoid drinking unless
        # necessary, but still require water every 2-3 days in dry season.
        #
        # The 80km threshold reflects their moderate range — giraffes
        # can cover ~15km/day but rarely venture far from permanent water
        # in the dry season. They cannot tolerate brackish or saline water.
        "water_threshold_m": 80_000,
        # Giraffes prefer permanent surface water — rivers and lakes.
        # They will use wetlands and floodplains opportunistically but
        # avoid saline sources entirely. No pan usage — their drinking
        # posture makes shallow ephemeral pans impractical.
        "accessible_water_types": {"river", "lake", "wetland", "floodplain", "surface_water", "permanent_water"},
        # Permanent sources weighted at 1.0 — fully reliable year-round.
        # Wetlands and floodplains lower — seasonal availability and
        # predation risk at dense vegetation makes them less reliable.
        "water_type_weights": {
            "river": 1.0,
            "lake": 1.0,
            "wetland": 0.6,
            "floodplain": 0.7,
            "surface_water": 0.6,
            "permanent_water": 0.9,
        },
        # 15km typical daily range — giraffes are not long-distance movers.
        "daily_range_m": 15_000,
        # Moderate water dependency — can extract moisture from browsing
        # but still requires surface water regularly.
        "water_dependency": "moderate",
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f992.png",
        "icon_static_path": "app/static/Creative-Tail-Animal-giraffe.svg.png",
        "gbif_cache_file": "gbif_giraffa_camelopardalis.gpkg",
        "emoji": "🦒",
    },
    "Panthera leo": {
        "common_name": "Lion",
        # ---------------------------------------------------------------
        # Lion
        # ---------------------------------------------------------------
        # Lions are the apex predator of the African savanna and their
        # distribution closely tracks prey availability — which in turn
        # tracks water. Lions themselves drink daily when water is
        # available but can survive 4-5 days without water by obtaining
        # moisture from prey. Their presence is a strong proxy indicator
        # of a functioning water-dependent ecosystem.
        #
        # The 200km threshold reflects their large territory size —
        # lion prides maintain ranges of 20-400km² and will follow
        # prey herds considerable distances during dry season movements.
        "water_threshold_m": 200_000,
        # Lions drink from all permanent surface water sources.
        # They avoid saline lakes but will use seasonal pans and
        # floodplains when following prey herds.
        "accessible_water_types": {"river", "lake", "pan", "wetland", "floodplain", "surface_water", "permanent_water"},
        # Permanent sources weighted at 1.0 — fully reliable year-round.
        # Pans weighted moderately — lions use them opportunistically
        # when following prey but don't depend on them exclusively.
        "water_type_weights": {
            "river": 1.0,
            "lake": 1.0,
            "pan": 0.5,
            "wetland": 0.7,
            "floodplain": 0.8,
            "surface_water": 0.6,
            "permanent_water": 0.9,
        },
        # 30km typical daily range when actively hunting or following prey.
        "daily_range_m": 30_000,
        # Moderate water dependency — can extract moisture from prey
        # but still requires surface water regularly.
        "water_dependency": "moderate",
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f981.png",
        "icon_static_path": "app/static/Creative-Tail-Animal-lion.svg.png",
        "gbif_cache_file": "gbif_panthera_leo.gpkg",
        "emoji": "🦁",
    },
    "Acinonyx jubatus": {
        "common_name": "Cheetah",
        # ---------------------------------------------------------------
        # Cheetah
        # ---------------------------------------------------------------
        # Cheetahs are the most water-independent of the large African
        # cats — they obtain most of their moisture from prey and can
        # survive without drinking for extended periods. However they
        # are not truly water-independent and will drink when water is
        # available. Their distribution is more strongly driven by prey
        # availability (which tracks water) than by direct water access.
        #
        # The 250km threshold reflects their large home ranges —
        # cheetahs are the most wide-ranging of the African cats with
        # males covering up to 800km² and following prey herds across
        # vast distances. A cheetah 250km from water is likely in a
        # truly arid system with very limited prey.
        "water_threshold_m": 250_000,
        # Cheetahs drink from permanent surface water when available
        # but are less dependent than lions. They avoid saline sources
        # and rarely use seasonal pans — they get most moisture from prey.
        "accessible_water_types": {"river", "lake", "wetland", "floodplain", "surface_water", "permanent_water"},
        # Permanent sources weighted at 1.0 — fully reliable year-round.
        # Lower weights overall reflect cheetah's reduced direct water
        # dependency compared to other species.
        "water_type_weights": {
            "river": 1.0,
            "lake": 1.0,
            "wetland": 0.5,
            "floodplain": 0.6,
            "surface_water": 0.5,
            "permanent_water": 0.9,
        },
        # 50km typical daily range — cheetahs are fast and wide-ranging.
        "daily_range_m": 50_000,
        # Low water dependency — obtains most moisture from prey.
        "water_dependency": "low",
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f406.png",
        "icon_static_path": "app/static/Creative-Tail-Animal-cheetah.svg.png",
        "gbif_cache_file": "gbif_acinonyx_jubatus.gpkg",
        "emoji": "🐆",
    },
    "Crocodylus niloticus": {
        "common_name": "Nile Crocodile",
        # ---------------------------------------------------------------
        # Nile Crocodile
        # ---------------------------------------------------------------
        # Nile crocodiles are permanent water obligates — they cannot
        # survive without direct access to water and spend the majority
        # of their lives in or immediately adjacent to rivers, lakes,
        # and wetlands. They are ectothermic and depend on water for
        # thermoregulation as well as hunting.
        #
        # The 10km threshold is extremely tight — a crocodile more than
        # 10km from permanent water is almost certainly dead or displaced
        # by catastrophic drought. They are the ultimate indicator species
        # for permanent surface water presence. If crocs are gone from a
        # river system, the river is effectively gone.
        "water_threshold_m": 10_000,
        # Crocodiles require permanent surface water exclusively.
        # They do not use seasonal pans or ephemeral water — they need
        # year-round access for thermoregulation, nesting, and hunting.
        # Saline lakes excluded — Nile crocodiles are freshwater obligates.
        "accessible_water_types": {"river", "lake", "wetland", "floodplain", "permanent_water"},
        # All sources weighted very high — crocodiles are so water-dependent
        # that any accessible water source is critical. Floodplains slightly
        # lower — seasonal inundation means temporary habitat only.
        "water_type_weights": {
            "river": 1.0,
            "lake": 1.0,
            "wetland": 0.9,
            "floodplain": 0.7,
            "permanent_water": 1.0,
        },
        # 5km typical daily range — crocodiles are ambush predators,
        # not long-distance movers. They rarely stray far from water.
        "daily_range_m": 5_000,
        # Highest possible water dependency — permanent water obligate.
        "water_dependency": "high",
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f40a.png",
        "icon_static_path": "app/static/Creative-Tail-Animal-crocodile.svg.png",
        "gbif_cache_file": "gbif_crocodylus_niloticus.gpkg",
        "emoji": "🐊",
    },
    "Phoenicopterus roseus": {
        "common_name": "Greater Flamingo",
        # ---------------------------------------------------------------
        # Greater Flamingo
        # ---------------------------------------------------------------
        # Greater flamingos are highly specialized saline lake obligates —
        # they breed almost exclusively on large shallow saline or alkaline
        # lakes (e.g. Lake Natron, Lake Bogoria, Lake Turkana) where their
        # primary food source, cyanobacteria, thrives. They are among the
        # most water-stress-sensitive species in Africa because their
        # habitat is both highly specific and highly threatened by climate
        # change — even small changes in lake levels can render entire
        # breeding colonies non-viable.
        #
        # The 50km threshold reflects their relatively limited foraging
        # range from breeding colonies — flamingos commute between feeding
        # and roosting sites but rarely venture far from their saline lake
        # habitat. A flamingo 50km from a saline lake has effectively lost
        # its habitat entirely.
        "water_threshold_m": 50_000,
        # Flamingos are saline lake specialists — this is the key
        # differentiator from all other species in the atlas. They
        # actually PREFER saline and alkaline lakes that other species
        # cannot use at all. They will also use large permanent lakes
        # and river deltas for roosting and secondary foraging.
        "accessible_water_types": {"saline_lake", "lake", "river", "permanent_water"},
        # Saline lakes weighted highest — this is the flamingo's primary
        # habitat and the source of their food (cyanobacteria blooms).
        # Regular freshwater lakes weighted lower — used for drinking
        # and secondary foraging only, not breeding habitat.
        "water_type_weights": {
            "saline_lake": 1.0,
            "lake": 0.6,
            "river": 0.4,
            "permanent_water": 0.5,
        },
        # 30km typical foraging range from breeding colony.
        "daily_range_m": 30_000,
        # High water dependency — completely tied to specific water body
        # types for breeding, feeding, and survival.
        "water_dependency": "high",
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f9a9.png",
        "icon_static_path": "app/static/Creative-Tail-Animal-flamingo.svg.png",
        "gbif_cache_file": "gbif_phoenicopterus_roseus.gpkg",
        "emoji": "🦩",
    },
    "Hyperolius marmoratus": {
        "common_name": "Painted Reed Frog",
        # ---------------------------------------------------------------
        # Painted Reed Frog
        # ---------------------------------------------------------------
        # Painted reed frogs are among the most water-stress-sensitive
        # vertebrates in Africa and serve as a critical early warning
        # indicator species for wetland degradation. As amphibians they
        # require water at every stage of their lifecycle — eggs and
        # tadpoles are fully aquatic, adults require high humidity and
        # proximity to water for reproduction and skin respiration.
        #
        # They are the "canary in the coal mine" for this atlas —
        # where elephants can survive 300km from water, reed frogs
        # cannot survive more than ~2km from a wetland or water body.
        # Their disappearance from a region signals ecosystem collapse
        # well before megafauna are affected.
        #
        # The 2km threshold reflects their extremely limited dispersal
        # ability — reed frogs are small, slow, and desiccation-prone.
        # A reed frog 2km from water in dry season is functionally dead.
        "water_threshold_m": 2_000,
        # Reed frogs require seasonal and permanent wetlands for breeding.
        # They are found in reed beds, marshes, and vegetation adjacent
        # to water. Critically they depend on SEASONAL water — they breed
        # in response to rainfall and seasonal flooding, making them
        # sensitive to changes in seasonal water availability as well
        # as permanent water loss.
        "accessible_water_types": {"wetland", "floodplain", "river", "lake", "surface_water", "permanent_water"},
        # Wetlands and floodplains weighted highest — reed beds and
        # emergent vegetation are essential breeding habitat.
        # Rivers and lakes used for dispersal corridors between wetlands.
        # All values are heuristic placeholders — amphibian ecological
        # validation is a future step with herpetology collaborators.
        "water_type_weights": {
            "wetland": 1.0,
            "floodplain": 0.9,
            "river": 0.6,
            "lake": 0.5,
            "surface_water": 0.8,
            "permanent_water": 0.7,
        },
        # 2km typical dispersal range — reed frogs are extremely
        # sedentary compared to megafauna. This tight range means
        # grid cell sizing needs to be much finer for amphibians
        # than for elephants — a future Phase 2 consideration.
        "daily_range_m": 2_000,
        # Highest water dependency of any species in the atlas —
        # amphibians require water for respiration, reproduction,
        # and temperature regulation. No water = no reed frogs.
        "water_dependency": "high",
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f438.png",
        "icon_static_path": "app/static/Creative-Tail-Animal-frog.svg.png",
        "gbif_cache_file": "gbif_hyperolius_marmoratus.gpkg",
        "emoji": "🐸",
    },
    "Xenopus laevis": {
        "common_name": "African Clawed Frog",
        # ---------------------------------------------------------------
        # African Clawed Frog
        # ---------------------------------------------------------------
        # The African clawed frog is the most scientifically studied
        # amphibian in the world — it was the first vertebrate cloned
        # and has been used in laboratories globally since the 1930s.
        # This gives it an exceptionally large and well-documented GBIF
        # dataset, making it an ideal indicator species for the atlas.
        #
        # Unlike the painted reed frog which lives IN vegetation adjacent
        # to water, Xenopus laevis is fully aquatic — it spends its entire
        # life in water, only leaving during drought to aestivate in mud
        # or disperse to new water bodies. It is a permanent water obligate
        # in the truest sense.
        #
        # The 5km threshold reflects its limited overland dispersal ability
        # during drought-driven migration. A Xenopus more than 5km from
        # permanent water during dry season is in severe stress — it will
        # desiccate rapidly without water for skin respiration.
        #
        # NOTE: Xenopus laevis is also an invasive species outside Africa —
        # GBIF records include European and American populations from
        # escaped laboratory specimens. These are intentionally preserved
        # in the dataset — they are a data quality story, not noise.
        # The Prescribe layer will flag non-African records as low-confidence.
        "water_threshold_m": 5_000,
        # Xenopus is fully aquatic — it requires permanent standing water.
        # Unlike reed frogs it does not use seasonal floodplains for
        # breeding — it needs year-round water bodies deep enough to
        # remain after seasonal drying. Highly tolerant of turbid,
        # low-oxygen water but not saline sources.
        "accessible_water_types": {"lake", "river", "wetland", "surface_water", "permanent_water"},
        # Permanent deep water bodies weighted highest — Xenopus needs
        # water that persists through the dry season. Rivers weighted
        # lower than lakes — Xenopus prefers still or slow-moving water.
        # All values are heuristic placeholders pending herpetology review.
        "water_type_weights": {
            "lake": 1.0,
            "river": 0.5,
            "wetland": 0.8,
            "surface_water": 0.7,
            "permanent_water": 1.0,
        },
        # 5km overland dispersal range during drought aestivation.
        # In water Xenopus can travel much further but overland movement
        # is slow and dangerous — desiccation risk limits dispersal.
        "daily_range_m": 5_000,
        # Highest water dependency — fully aquatic obligate.
        # Cannot survive outside water except during brief drought
        # dispersal events.
        "water_dependency": "high",
        "icon_url": "https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f438.png",
        "icon_static_path": "app/static/Creative-Tail-Animal-frog.svg.png",
        "gbif_cache_file": "gbif_xenopus_laevis.gpkg",
        "emoji": "🐸",
    },
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
# These checks run once at import time — if someone adds a malformed species
# entry, the error surfaces immediately rather than causing a silent failure
# deep inside the scoring pipeline at runtime.


def _validate_species_config(config: dict[str, dict]) -> None:
    """
    Validate the structure and constraints of SPECIES_CONFIG at import time.

    Raises:
        ValueError: If any species entry is missing required keys, has
                    wrong types, or violates field constraints.
    """
    required_keys = {
        "water_threshold_m",
        "accessible_water_types",
        "water_type_weights",
        "daily_range_m",
        "water_dependency",
        "icon_url",
    }
    valid_dependency_values = {"low", "moderate", "high"}

    for species, cfg in config.items():
        # Every required key must be present
        missing = required_keys - cfg.keys()
        if missing:
            raise ValueError(f"{species} is missing required keys: {missing}")

        # water_threshold_m must be a positive number
        if not isinstance(cfg["water_threshold_m"], (int, float)) or cfg["water_threshold_m"] <= 0:
            raise ValueError(f"{species}: water_threshold_m must be a positive number")

        # accessible_water_types must be a non-empty set
        if not isinstance(cfg["accessible_water_types"], set) or not cfg["accessible_water_types"]:
            raise ValueError(f"{species}: accessible_water_types must be a non-empty set")

        # water_type_weights keys must exactly match accessible_water_types
        if cfg["water_type_weights"].keys() != cfg["accessible_water_types"]:
            raise ValueError(f"{species}: water_type_weights keys must exactly match accessible_water_types. Got {set(cfg['water_type_weights'].keys())} vs {cfg['accessible_water_types']}")

        # All weights must be floats in (0.0, 1.0]
        for water_type, weight in cfg["water_type_weights"].items():
            if not isinstance(weight, float) or not (0.0 < weight <= 1.0):
                raise ValueError(f"{species}/{water_type}: weight must be a float between 0 (exclusive) and 1 (inclusive)")

        # daily_range_m must be a positive number
        if not isinstance(cfg["daily_range_m"], (int, float)) or cfg["daily_range_m"] <= 0:
            raise ValueError(f"{species}: daily_range_m must be a positive number")

        # water_dependency must be one of the allowed values
        if cfg["water_dependency"] not in valid_dependency_values:
            raise ValueError(f"{species}: water_dependency must be one of {valid_dependency_values}, got '{cfg['water_dependency']}'")

        # icon_url must be a non-empty string starting with https://
        if not isinstance(cfg["icon_url"], str) or not cfg["icon_url"].startswith("https://"):
            raise ValueError(f"{species}: icon_url must be a valid https:// URL")

        # icon_static_path must point to Streamlit's static folder —
        # same-origin serving avoids CORS issues with PyDeck IconLayer.
        if not isinstance(cfg["icon_static_path"], str) or not cfg["icon_static_path"].startswith("app/static/"):
            raise ValueError(f"{species}: icon_static_path must start with 'app/static/'")

        # gbif_cache_file must be a .gpkg filename — GeoPackage is the
        # standard cache format throughout the pipeline.
        if not isinstance(cfg["gbif_cache_file"], str) or not cfg["gbif_cache_file"].endswith(".gpkg"):
            raise ValueError(f"{species}: gbif_cache_file must be a .gpkg filename")

        # emoji must be a string — used in UI labels and chart headers.
        if not isinstance(cfg["emoji"], str):
            raise ValueError(f"{species}: emoji must be a string")


# Run validation immediately when this module is imported.
# This means any misconfigured entry fails loudly at startup,
# not silently at scoring time.
_validate_species_config(SPECIES_CONFIG)
